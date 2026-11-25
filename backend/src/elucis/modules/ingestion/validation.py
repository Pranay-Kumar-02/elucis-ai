"""Row validation and normalisation (D03 SVC-04, D06 step 4; DR-06 to DR-09, DR-41).

Turns adapter ``RawItem``s into one common record structure (DR-20) or a ``RowError``:

Feedback rows (review, ticket, feature request, transcript, other)
    * rejected: text empty after trimming (DR-07); structural defects from the reader
      (extra CSV values, non-object JSON elements);
    * kept and flagged: unparseable or missing timestamp -> ``occurred_at`` null and
      ``occurred_at_missing`` (DR-08); text over 20,000 characters (processing uses the
      first 20,000, the original is kept); rating that is not a number; source record ID
      repeated in the file.

Metric rows (DR-41)
    * rejected: missing metric name, date that is not ISO ``YYYY-MM-DD``, value that is not
      a number, and a repeated (metric, date, dimension), which the database would refuse.

Everything later in the pipeline (cleaning, PII masking, UTC/rating/version
standardisation, customer keys, duplicates, spam) belongs to SVC-05 onwards and is
deliberately not done here. Values are never invented: anything uncertain is flagged.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Literal

from elucis.modules.ingestion.adapters.base import RawItem, SourceType
from elucis.modules.ingestion.adapters.file_adapter import FileAdapter
from elucis.modules.ingestion.parsing import (
    DateOrder,
    DateOrderInference,
    infer_date_order,
    parse_iso_date,
    parse_number,
    parse_rating,
    parse_timestamp,
)

MAX_TEXT_CHARS = 20_000  # SVC-04: longer text is truncated for processing, original kept

# Flags on kept records. Codes are stable API values; messages are for people.
FLAG_MESSAGES = {
    "occurred_at_missing": "No date given",
    "occurred_at_unparseable": "Date could not be read",
    "text_truncated": "Text longer than 20,000 characters; analysis uses the first 20,000",
    "rating_invalid": "Rating is not a number",
    "duplicate_source_record_id": "Record ID appears more than once in the file",
}


@dataclass(frozen=True, slots=True)
class RowError:
    """SVC-04 ``RowError{row_number, field, code, message}``; ``kind`` per D07."""

    row_number: int
    segment_index: int
    field: str | None
    code: str
    message: str
    kind: Literal["rejected"] = "rejected"


@dataclass(frozen=True, slots=True)
class NormalizedRecord:
    """SVC-04 ``ValidRow`` for feedback. Field names follow D07 ``feedback_records``."""

    row_number: int
    segment_index: int
    source_type: SourceType
    raw_text: str
    text_truncated: bool
    source_record_id: str | None
    occurred_at: datetime | None
    occurred_at_raw: str | None
    occurred_at_missing: bool
    customer_ref: str | None
    rating_raw: str | None
    rating_value: float | None
    rating_out_of: float | None
    product_version_raw: str | None
    speaker: str | None
    metadata: dict[str, str]
    flags: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MetricObservation:
    """SVC-04 ``ValidRow`` for metric files (D07 ``metric_observations``)."""

    row_number: int
    metric_name: str
    observed_on: date
    value: float
    dimension: str
    metadata: dict[str, str]


@dataclass(slots=True)
class ValidationTally:
    """Counts for one validation pass. ``received = valid + rejected`` must hold (DR-40)."""

    received: int = 0
    valid: int = 0
    rejected: int = 0
    rejected_by_code: Counter[str] = field(default_factory=Counter)
    flags_by_code: Counter[str] = field(default_factory=Counter)

    @property
    def reconciled(self) -> bool:
        return self.received == self.valid + self.rejected


class RowValidator:
    """Validates the rows of one adapter. Column-level facts (date order, repeated record
    IDs) are computed once from the whole file, so results do not depend on paging."""

    def __init__(self, adapter: FileAdapter, source_type: SourceType) -> None:
        self.adapter = adapter
        self.source_type = source_type
        mapping = adapter.mapping.mapped_columns() if adapter.mapping else {}
        time_column = mapping.get("occurred_at")
        self.date_order: DateOrderInference | None = (
            infer_date_order(adapter.column_values(time_column)) if time_column else None
        )  # None: no numeric day/month dates in the column, nothing to decide
        id_column = mapping.get("source_record_id")
        self._repeated_ids: set[str] = set()
        if id_column and source_type is not SourceType.METRICS:
            counts = Counter(v.strip() for v in adapter.column_values(id_column) if v.strip())
            self._repeated_ids = {k for k, n in counts.items() if n > 1}
        # First row of each (metric, date, dimension), computed over the whole file.
        self._first_metric_row: dict[tuple[str, date, str], int] = {}
        if source_type is SourceType.METRICS and adapter.mapping is not None:
            for batch, _ in adapter.fetch():
                for raw in batch:
                    observed = parse_iso_date(raw.occurred_at_raw or "")
                    if raw.metric_name_raw and observed:
                        key = (raw.metric_name_raw, observed, raw.dimension_raw or "")
                        self._first_metric_row.setdefault(key, raw.row_number)

    @property
    def order(self) -> DateOrder:
        return self.date_order.order if self.date_order else DateOrder.DMY

    # ------------------------------------------------------------------ entry point
    def validate(
        self, item: RawItem, tally: ValidationTally | None = None
    ) -> NormalizedRecord | MetricObservation | RowError:
        if self.source_type is SourceType.METRICS:
            result: NormalizedRecord | MetricObservation | RowError = self._metric(item)
        else:
            result = self._feedback(item)
        if tally is not None:
            tally.received += 1
            if isinstance(result, RowError):
                tally.rejected += 1
                tally.rejected_by_code[result.code] += 1
            else:
                tally.valid += 1
                if isinstance(result, NormalizedRecord):
                    tally.flags_by_code.update(result.flags)
        return result

    # ------------------------------------------------------------------ feedback
    def _feedback(self, item: RawItem) -> NormalizedRecord | RowError:
        if item.defect is not None:
            return RowError(
                item.row_number, item.segment_index, None, item.defect.code, item.defect.message
            )
        text = item.text
        if not text.strip():
            return RowError(
                item.row_number, item.segment_index, "text", "text_missing", "Text is empty."
            )

        flags: list[str] = []
        occurred_at = None
        if item.occurred_at_raw is None:
            flags.append("occurred_at_missing")
        else:
            occurred_at = parse_timestamp(item.occurred_at_raw, self.order)
            if occurred_at is None:
                flags.append("occurred_at_unparseable")

        rating = parse_rating(item.rating_raw) if item.rating_raw is not None else None
        if item.rating_raw is not None and rating is None:
            flags.append("rating_invalid")

        truncated = len(text) > MAX_TEXT_CHARS
        if truncated:
            flags.append("text_truncated")
        if item.source_record_id is not None and item.source_record_id in self._repeated_ids:
            flags.append("duplicate_source_record_id")

        return NormalizedRecord(
            row_number=item.row_number,
            segment_index=item.segment_index,
            source_type=self.source_type,
            raw_text=text,
            text_truncated=truncated,
            source_record_id=item.source_record_id,
            occurred_at=occurred_at,
            occurred_at_raw=item.occurred_at_raw,
            occurred_at_missing=occurred_at is None,
            customer_ref=item.customer_ref,
            rating_raw=item.rating_raw,
            rating_value=rating.value if rating else None,
            rating_out_of=rating.out_of if rating else None,
            product_version_raw=item.version_raw,
            speaker=item.speaker,
            metadata=item.metadata,
            flags=tuple(flags),
        )

    # ------------------------------------------------------------------ metrics
    def _metric(self, item: RawItem) -> MetricObservation | RowError:  # noqa: PLR0911 - one exit per DR-41 rule
        def reject(fld: str | None, code: str, message: str) -> RowError:
            return RowError(item.row_number, 0, fld, code, message)

        if item.defect is not None:
            return reject(None, item.defect.code, item.defect.message)
        if not item.metric_name_raw:
            return reject("metric_name", "metric_name_missing", "Metric name is empty.")
        if not item.occurred_at_raw:
            return reject("occurred_at", "metric_date_missing", "Date is empty.")
        observed_on = parse_iso_date(item.occurred_at_raw)
        if observed_on is None:
            return reject(
                "occurred_at", "metric_date_invalid", "Date must be in YYYY-MM-DD format."
            )
        if not item.metric_value_raw:
            return reject("metric_value", "metric_value_missing", "Value is empty.")
        value = parse_number(item.metric_value_raw)
        if value is None:
            return reject("metric_value", "metric_value_invalid", "Value is not a number.")
        dimension = item.dimension_raw or ""
        first_row = self._first_metric_row.get((item.metric_name_raw, observed_on, dimension))
        if first_row is not None and first_row != item.row_number:
            return reject(
                None,
                "duplicate_metric_observation",
                f"The same metric, date and dimension already appear in row {first_row}.",
            )
        return MetricObservation(
            row_number=item.row_number,
            metric_name=item.metric_name_raw,
            observed_on=observed_on,
            value=value,
            dimension=dimension,
            metadata=item.metadata,
        )
