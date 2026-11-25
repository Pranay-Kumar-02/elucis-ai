"""Ingestion service: the source-fetching layer (SVC-02 + SVC-04, no storage yet).

Functions the API (and later the ingest job) call:

* ``read_source_input`` - stream an upload with a hard size cap and SHA-256 (DR-10 needs
  the hash), or take pasted text (FR-ING-10);
* ``preview_source`` - format, encoding, columns, first rows, suggested mapping (API-14);
* ``validate_source`` - map and validate every row; counts, row errors, a normalised
  sample (D06 step 4, UI-03 validation summary);
* ``fetch_source`` - one page of normalised records and rejected rows, resumable with an
  opaque cursor bound to the file's hash.

Nothing here writes to disk or the database. API-14/API-15 will add storage, workspaces
and the background job around these same functions.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Literal

from fastapi import UploadFile

from copilot.core.errors import FileTooLargeError, ValidationFailedError
from copilot.modules.ingestion.adapters.base import (
    MAX_RECORDS_PER_IMPORT,
    ColumnMapping,
    SourceType,
)
from copilot.modules.ingestion.adapters.file_adapter import PASTED_FILENAME, FileAdapter
from copilot.modules.ingestion.adapters.registry import list_sources
from copilot.modules.ingestion.mapping import check_mapping, required_fields, suggest_mapping
from copilot.modules.ingestion.schemas import (
    DateOrderOut,
    FetchPageOut,
    FileInfoOut,
    FilePreviewOut,
    MetricObservationOut,
    NormalizedRecordOut,
    RowErrorOut,
    SourceInfoOut,
    ValidationReportOut,
    ValidationSummaryOut,
)
from copilot.modules.ingestion.validation import (
    MetricObservation,
    NormalizedRecord,
    RowError,
    RowValidator,
    ValidationTally,
)

_CHUNK = 1024 * 1024
MAX_PASTED_CHARS = 1_000_000
MAX_ERRORS_RETURNED = 200
SAMPLE_SIZE = 20


@dataclass(frozen=True, slots=True)
class SourceInput:
    kind: Literal["file", "pasted_text"]
    data: bytes
    filename: str
    sha256: str


async def read_source_input(
    upload: UploadFile | None, pasted_text: str | None, max_bytes: int
) -> SourceInput:
    """Exactly one of a file upload or pasted text."""
    has_text = pasted_text is not None and pasted_text.strip() != ""
    if (upload is None) == (not has_text):
        raise ValidationFailedError(
            "Provide either a file or pasted text (exactly one).",
            details=[{"field": "file", "issue": "exactly_one_of_file_or_pasted_text"}],
        )
    if upload is None:
        assert pasted_text is not None  # noqa: S101 - checked above
        if len(pasted_text) > MAX_PASTED_CHARS:
            raise FileTooLargeError("Pasted text is limited to 1,000,000 characters.")
        data = pasted_text.encode("utf-8")
        return SourceInput("pasted_text", data, PASTED_FILENAME, hashlib.sha256(data).hexdigest())
    digest = hashlib.sha256()
    chunks: list[bytes] = []
    size = 0
    while chunk := await upload.read(_CHUNK):
        size += len(chunk)
        if size > max_bytes:
            raise FileTooLargeError(f"The upload is larger than {max_bytes // (1024 * 1024)} MB.")
        digest.update(chunk)
        chunks.append(chunk)
    return SourceInput("file", b"".join(chunks), upload.filename or "upload", digest.hexdigest())


def parse_mapping(raw: str | None) -> ColumnMapping | None:
    if raw is None or not raw.strip():
        return None
    try:
        return ColumnMapping.model_validate(json.loads(raw))
    except (json.JSONDecodeError, ValueError) as exc:
        raise ValidationFailedError(
            'mapping must be a JSON object such as {"text": "review"}.',
            details=[{"field": "mapping", "issue": "invalid"}],
        ) from exc


def _file_info(src: SourceInput, adapter: FileAdapter) -> FileInfoOut:
    p = adapter.parsed
    return FileInfoOut(
        input=src.kind,
        original_filename=src.filename,
        size_bytes=len(src.data),
        sha256=src.sha256,
        detected_format=p.format,
        detected_encoding=p.encoding,
        csv_delimiter=p.csv_delimiter,
        transcript_mode=p.transcript_mode,
        record_count=p.record_count,
    )


def _open(src: SourceInput, mapping: ColumnMapping | None = None) -> FileAdapter:
    if src.kind == "pasted_text":
        return FileAdapter.from_pasted_text(src.data.decode("utf-8"), mapping)
    return FileAdapter(src.data, src.filename, mapping)


def _open_for_rows(
    src: SourceInput, source_type: SourceType, mapping: ColumnMapping | None
) -> FileAdapter:
    adapter = _open(src, mapping)
    if adapter.mapping is None:
        raise ValidationFailedError(
            "Choose which columns hold the standard fields before checking records.",
            details=[{"field": "column_mapping", "issue": "required"}],
        )
    check_mapping(adapter.mapping, source_type, adapter.parsed.format)
    if adapter.parsed.exceeds_record_limit:
        raise ValidationFailedError(
            f"The file has {adapter.parsed.record_count:,} records; one import can hold at most "
            f"{MAX_RECORDS_PER_IMPORT:,}. Split it into smaller files.",
            details=[{"field": "file", "issue": "too_many_records"}],
        )
    return adapter


def _record_out(record: NormalizedRecord) -> NormalizedRecordOut:
    data = asdict(record)
    data["flags"] = list(record.flags)
    return NormalizedRecordOut(**data)


def _metric_out(metric: MetricObservation) -> MetricObservationOut:
    return MetricObservationOut(**asdict(metric))


def _error_out(error: RowError) -> RowErrorOut:
    return RowErrorOut(
        row_number=error.row_number,
        segment_index=error.segment_index,
        field=error.field,
        code=error.code,
        message=error.message,
    )


def _date_order_out(validator: RowValidator) -> DateOrderOut | None:
    if validator.date_order is None:
        return None
    return DateOrderOut(
        order=validator.date_order.order.value, assumed=validator.date_order.assumed
    )


# ---------------------------------------------------------------------- operations
def preview_source(src: SourceInput, source_type: SourceType, rows: int) -> FilePreviewOut:
    adapter = _open(src)
    parsed = adapter.parsed
    suggestion = (
        adapter.default_mapping().mapped_columns()  # type: ignore[union-attr]
        if parsed.format == "txt"
        else suggest_mapping(parsed.columns, source_type)
    )
    return FilePreviewOut(
        **_file_info(src, adapter).model_dump(),
        columns=parsed.columns,
        preview_rows=adapter.preview(rows),
        total_rows=adapter.item_count,
        warnings=parsed.warnings,
        source_type=source_type,
        required_fields=list(required_fields(source_type)),
        suggested_mapping=suggestion,
    )


def validate_source(
    src: SourceInput, source_type: SourceType, mapping: ColumnMapping | None
) -> ValidationReportOut:
    adapter = _open_for_rows(src, source_type, mapping)
    validator = RowValidator(adapter, source_type)
    tally = ValidationTally()
    errors: list[RowErrorOut] = []
    records: list[NormalizedRecordOut] = []
    metrics: list[MetricObservationOut] = []
    for batch, _cursor in adapter.fetch():
        for item in batch:
            result = validator.validate(item, tally)
            if isinstance(result, RowError):
                if len(errors) < MAX_ERRORS_RETURNED:
                    errors.append(_error_out(result))
            elif isinstance(result, MetricObservation):
                if len(metrics) < SAMPLE_SIZE:
                    metrics.append(_metric_out(result))
            elif len(records) < SAMPLE_SIZE:
                records.append(_record_out(result))
    warnings = list(adapter.parsed.warnings)
    if (
        validator.date_order is not None
        and validator.date_order.assumed
        and source_type is not SourceType.METRICS
    ):
        warnings.append(
            "Some dates could be read either way (for example 03/04/2026); they were read as "
            "day/month/year."
        )
    assert adapter.mapping is not None  # noqa: S101 - _open_for_rows guarantees it
    return ValidationReportOut(
        file=_file_info(src, adapter),
        source_type=source_type,
        column_mapping=adapter.mapping.mapped_columns(),
        date_order=_date_order_out(validator) if source_type is not SourceType.METRICS else None,
        summary=ValidationSummaryOut(
            received=tally.received,
            valid=tally.valid,
            rejected=tally.rejected,
            rejected_by_code=dict(tally.rejected_by_code),
            flags_by_code=dict(tally.flags_by_code),
            reconciled=tally.reconciled,
        ),
        errors=errors,
        errors_truncated=tally.rejected > len(errors),
        sample_records=records,
        sample_metrics=metrics,
        warnings=warnings,
    )


def _encode_cursor(position: int, sha256: str) -> str:
    raw = json.dumps({"p": position, "f": sha256[:16]}, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _decode_cursor(cursor: str | None, sha256: str) -> int:
    if not cursor:
        return 0
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        data = json.loads(base64.urlsafe_b64decode(padded))
        position = int(data["p"])
        file_ok = data["f"] == sha256[:16]
    except (binascii.Error, ValueError, KeyError, TypeError) as exc:
        raise ValidationFailedError(
            "The cursor is not valid.", details=[{"field": "cursor", "issue": "invalid"}]
        ) from exc
    if not file_ok or position < 0:
        raise ValidationFailedError(
            "The cursor belongs to a different file.",
            details=[{"field": "cursor", "issue": "file_mismatch"}],
        )
    return position


def fetch_source(
    src: SourceInput,
    source_type: SourceType,
    mapping: ColumnMapping | None,
    cursor: str | None,
    limit: int,
) -> FetchPageOut:
    adapter = _open_for_rows(src, source_type, mapping)
    start = _decode_cursor(cursor, src.sha256)
    stop = min(start + limit, adapter.item_count)
    validator = RowValidator(adapter, source_type)
    items: list[NormalizedRecordOut] = []
    metrics: list[MetricObservationOut] = []
    rejected: list[RowErrorOut] = []
    for batch, _ in adapter.fetch_range(start, stop):
        for item in batch:
            result = validator.validate(item)
            if isinstance(result, RowError):
                rejected.append(_error_out(result))
            elif isinstance(result, MetricObservation):
                metrics.append(_metric_out(result))
            else:
                items.append(_record_out(result))
    return FetchPageOut(
        source_type=source_type,
        total_items=adapter.item_count,
        items=items,
        metrics=metrics,
        rejected=rejected,
        next_cursor=_encode_cursor(stop, src.sha256) if stop < adapter.item_count else None,
    )


def source_catalogue() -> list[SourceInfoOut]:
    return [
        SourceInfoOut(
            **{**asdict(info), "status": info.status.value, "formats": list(info.formats)}
        )
        for info in list_sources()
    ]
