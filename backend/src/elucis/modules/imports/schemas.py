"""API schemas for stored files and imports (D09 ``SourceFileOut``, ``ImportIn``,
``ImportOut``, ``RowErrorOut``)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from elucis.modules.ingestion.adapters.base import ColumnMapping, SourceType
from elucis.modules.ingestion.schemas import FilePreviewOut

ImportStatus = Literal[
    "queued", "processing", "completed", "completed_with_errors", "failed", "cancelled"
]


class DuplicateFileOut(BaseModel):
    """An earlier upload with identical content (DR-10)."""

    id: uuid.UUID
    original_filename: str
    uploaded_at: datetime


class SourceFileOut(FilePreviewOut):
    id: uuid.UUID
    duplicate_of_file: DuplicateFileOut | None = Field(
        description="Set when the workspace already has a file with the same content (DR-10); "
        "the import can still go ahead"
    )


class CheckIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_type: SourceType
    column_mapping: ColumnMapping | None = None


class ImportIn(CheckIn):
    source_file_id: uuid.UUID


class ImportProgressOut(BaseModel):
    processed: int
    total: int


class ImportOut(BaseModel):
    id: uuid.UUID
    source_type: SourceType
    status: ImportStatus
    original_filename: str | None
    source_file_id: uuid.UUID | None
    submitted_by: uuid.UUID
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    job_id: uuid.UUID | None
    progress: ImportProgressOut | None
    error: str | None = Field(description="Why the import failed, when it did")
    report: dict[str, Any] | None = Field(
        description="Reconciliation snapshot at completion (D06 §10.1)"
    )


class StoredRowErrorOut(BaseModel):
    id: uuid.UUID
    row_number: int
    kind: Literal["rejected", "failed"]
    stage: str
    field: str | None
    code: str
    message: str
