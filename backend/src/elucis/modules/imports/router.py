"""API-14 to API-18: stored files and imports (D09 §3.2), all under ``/workspaces/{ws}``."""

from __future__ import annotations

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, File, Form, Header, Query, UploadFile, status
from starlette.concurrency import run_in_threadpool

from elucis.api.auth import DbDep, EditorDep, ViewerDep
from elucis.api.deps import SettingsDep
from elucis.api.pagination import DEFAULT_LIMIT, CursorQuery, LimitQuery, Page
from elucis.modules.identity.schemas import JobRef
from elucis.modules.imports import service
from elucis.modules.imports.schemas import (
    CheckIn,
    ImportIn,
    ImportOut,
    ImportStatus,
    SourceFileOut,
    StoredRowErrorOut,
)
from elucis.modules.ingestion.adapters.base import SourceType
from elucis.modules.ingestion.schemas import ValidationReportOut
from elucis.modules.ingestion.service import read_source_input

router = APIRouter(prefix="/workspaces/{ws}", tags=["imports"])

ErrorStage = Literal[
    "validation", "cleaning", "noise", "standardisation", "pii", "language", "duplicate", "spam",
    "other",
]  # fmt: skip


@router.post("/files", status_code=status.HTTP_201_CREATED, summary="API-14 Upload a file")
async def upload_file(
    *,
    ctx: EditorDep,
    db: DbDep,
    settings: SettingsDep,
    file: Annotated[UploadFile | None, File(description="CSV, JSON or TXT, up to 20 MB")] = None,
    pasted_text: Annotated[str | None, Form(description="Pasted feedback (FR-ING-10)")] = None,
    source_type: Annotated[SourceType, Form()] = SourceType.REVIEW,
) -> SourceFileOut:
    """Detect format and encoding, store the file, and return a preview with suggested
    column matches. An identical earlier file is reported in ``duplicate_of_file`` (DR-10)."""
    src = await read_source_input(file, pasted_text, settings.upload_max_bytes)
    return await run_in_threadpool(service.store_upload, db, settings, ctx, src, source_type)


@router.post("/files/{file_id}/check", summary="Check every row of a stored file (IMP-30)")
def check_file(
    file_id: uuid.UUID, data: CheckIn, ctx: EditorDep, db: DbDep, settings: SettingsDep
) -> ValidationReportOut:
    return service.check_file(db, settings, ctx, file_id, data)


@router.post("/imports", status_code=status.HTTP_202_ACCEPTED, summary="API-15 Start an import")
def start_import(
    data: ImportIn,
    ctx: EditorDep,
    db: DbDep,
    settings: SettingsDep,
    idempotency_key: Annotated[str | None, Header(max_length=64)] = None,
) -> JobRef:
    return service.start_import(db, settings, ctx, data, idempotency_key)


@router.get("/imports", summary="API-16 List imports")
def list_imports(
    ctx: ViewerDep,
    db: DbDep,
    status: ImportStatus | None = None,
    limit: LimitQuery = DEFAULT_LIMIT,
    cursor: CursorQuery = None,
) -> Page[ImportOut]:
    return service.list_imports(db, ctx, status=status, limit=limit, cursor=cursor)


@router.get("/imports/{import_id}", summary="API-17 Import status and report")
def get_import(import_id: uuid.UUID, ctx: ViewerDep, db: DbDep) -> ImportOut:
    return service.get_import(db, ctx, import_id)


@router.get("/imports/{import_id}/errors", summary="API-18 Rejected and failed rows")
def list_row_errors(
    *,
    import_id: uuid.UUID,
    ctx: ViewerDep,
    db: DbDep,
    kind: Literal["rejected", "failed"] | None = None,
    stage: Annotated[ErrorStage | None, Query()] = None,
    limit: LimitQuery = DEFAULT_LIMIT,
    cursor: CursorQuery = None,
) -> Page[StoredRowErrorOut]:
    return service.list_row_errors(
        db, ctx, import_id, kind=kind, stage=stage, limit=limit, cursor=cursor
    )
