"""API schemas for the ingestion module.

``FilePreviewOut`` mirrors D09 ``SourceFileOut`` minus the fields that need the database
(``id``, ``duplicate_of_file_id``); those arrive with API-14 in the schema/auth task.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class FilePreviewOut(BaseModel):
    original_filename: str
    size_bytes: int
    sha256: str
    detected_format: Literal["csv", "json", "txt"]
    detected_encoding: str
    csv_delimiter: str | None = None
    transcript_mode: Literal["speaker_turns", "paragraphs"] | None = None
    columns: list[str]
    preview_rows: list[list[str]] = Field(max_length=200)
    total_rows: int
    warnings: list[str]


class RawItemOut(BaseModel):
    row_number: int
    segment_index: int
    text: str
    source_record_id: str | None
    occurred_at_raw: str | None
    customer_ref: str | None
    rating_raw: str | None
    version_raw: str | None
    speaker: str | None
    metadata: dict[str, str]


class MappedPreviewOut(BaseModel):
    total_items: int
    items: list[RawItemOut]
    warnings: list[str]


class SourceInfoOut(BaseModel):
    kind: str
    label: str
    status: Literal["implemented", "designed"]
    formats: list[str]
    auth: str | None
    requirement: str | None
    notes: str | None
