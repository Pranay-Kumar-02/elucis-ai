"""API schemas for the ingestion module.

``FileInfoOut`` and ``FilePreviewOut`` follow D09 ``SourceFileOut`` minus the fields that
need the database (``id``, ``duplicate_of_file_id``); those arrive with API-14. Record
schemas follow D07 ``feedback_records`` / ``metric_observations`` names. Pages follow the
D09 convention ``{items, next_cursor}``.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from elucis.modules.ingestion.adapters.base import SourceType

DetectedFormat = Literal["csv", "json", "txt"]
TranscriptMode = Literal["speaker_turns", "paragraphs"]


class FileInfoOut(BaseModel):
    input: Literal["file", "pasted_text"]
    original_filename: str
    size_bytes: int
    sha256: str
    detected_format: DetectedFormat
    detected_encoding: str
    csv_delimiter: str | None = None
    transcript_mode: TranscriptMode | None = None
    record_count: int = Field(description="Source records; a transcript counts once")


class FilePreviewOut(FileInfoOut):
    columns: list[str]
    preview_rows: list[list[str]] = Field(max_length=200)
    total_rows: int = Field(description="Rows, or transcript segments, in the file")
    warnings: list[str]
    source_type: SourceType
    required_fields: list[str]
    suggested_mapping: dict[str, str] = Field(
        description="Proposed column for each standard field, from header names; "
        "the person confirms it before validating or importing"
    )


class RowErrorOut(BaseModel):
    row_number: int
    segment_index: int
    field: str | None
    code: str
    message: str


class NormalizedRecordOut(BaseModel):
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
    flags: list[str]


class MetricObservationOut(BaseModel):
    row_number: int
    metric_name: str
    observed_on: date
    value: float
    dimension: str
    metadata: dict[str, str]


class DateOrderOut(BaseModel):
    order: Literal["dmy", "mdy"]
    assumed: bool = Field(description="True when every date was ambiguous (e.g. 03/04/2026)")


class ValidationSummaryOut(BaseModel):
    received: int
    valid: int
    rejected: int
    rejected_by_code: dict[str, int]
    flags_by_code: dict[str, int]
    reconciled: bool = Field(description="received = valid + rejected (DR-40 at this stage)")


class ValidationReportOut(BaseModel):
    file: FileInfoOut
    source_type: SourceType
    column_mapping: dict[str, str]
    date_order: DateOrderOut | None
    summary: ValidationSummaryOut
    errors: list[RowErrorOut]
    errors_truncated: bool
    sample_records: list[NormalizedRecordOut]
    sample_metrics: list[MetricObservationOut]
    warnings: list[str]


class FetchPageOut(BaseModel):
    source_type: SourceType
    total_items: int
    items: list[NormalizedRecordOut]
    metrics: list[MetricObservationOut]
    rejected: list[RowErrorOut]
    next_cursor: str | None


class SourceInfoOut(BaseModel):
    kind: str
    label: str
    status: Literal["implemented", "designed"]
    formats: list[str]
    auth: str | None
    requirement: str | None
    notes: str | None
