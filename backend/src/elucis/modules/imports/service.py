"""Stored files and imports (SVC-03): what API-14 to API-18 do.

Every function takes the request's session, already bound to the workspace by
``WorkspaceAccess``; queries also filter by ``workspace_id`` (D09 §8 defence in depth).
"""

from __future__ import annotations

import base64
import binascii
import json
import uuid
from typing import Any

from sqlalchemy import and_, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from elucis.api.pagination import Page, decode_cursor, encode_cursor
from elucis.core.config import Settings
from elucis.core.errors import NotFoundError, ValidationFailedError
from elucis.db.models import DataSource, ImportJob, ImportRowError, Job, SourceFile
from elucis.modules.audit.recorder import record
from elucis.modules.identity.context import WorkspaceContext
from elucis.modules.identity.repository import enqueue_job
from elucis.modules.identity.schemas import JobRef
from elucis.modules.imports import storage
from elucis.modules.imports.schemas import (
    CheckIn,
    DuplicateFileOut,
    ImportIn,
    ImportOut,
    ImportProgressOut,
    SourceFileOut,
    StoredRowErrorOut,
)
from elucis.modules.ingestion.adapters.base import SourceType
from elucis.modules.ingestion.schemas import ValidationReportOut
from elucis.modules.ingestion.service import (
    SourceInput,
    open_for_rows,
    preview_source,
    stored_source,
    validate_source,
)

FILE_SOURCE_NAME = "File uploads"


# ---------------------------------------------------------------- helpers
def _idempotency_key(value: str | None) -> str | None:
    if value is None:
        return None
    try:
        return str(uuid.UUID(value))
    except ValueError as exc:
        raise ValidationFailedError(
            details=[{"field": "Idempotency-Key", "issue": "must be a UUID"}]
        ) from exc


def _file_source_id(db: Session, workspace_id: uuid.UUID) -> uuid.UUID:
    """The workspace's "File uploads" data source, created on first use."""
    db.execute(
        pg_insert(DataSource)
        .values(workspace_id=workspace_id, kind="file", name=FILE_SOURCE_NAME)
        .on_conflict_do_nothing(index_elements=["workspace_id", "name"])
    )
    return db.execute(
        select(DataSource.id).where(
            DataSource.workspace_id == workspace_id, DataSource.name == FILE_SOURCE_NAME
        )
    ).scalar_one()


def _stored_file(db: Session, workspace_id: uuid.UUID, file_id: uuid.UUID) -> SourceFile:
    row = db.execute(
        select(SourceFile).where(SourceFile.workspace_id == workspace_id, SourceFile.id == file_id)
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError("The file was not found.")
    return row


def load_source(settings: Settings, row: SourceFile) -> SourceInput:
    data = storage.read_file(settings.upload_dir, row.storage_path)
    return stored_source(data, row.original_filename, bytes(row.sha256).hex())


# ---------------------------------------------------------------- API-14
def store_upload(
    db: Session,
    settings: Settings,
    ctx: WorkspaceContext,
    src: SourceInput,
    source_type: SourceType,
) -> SourceFileOut:
    """Check the file is readable (else 415/422, nothing stored), write it to disk and record
    it. An identical earlier file is reported (DR-10), not refused."""
    preview = preview_source(src, source_type, settings.preview_rows)
    sha = bytes.fromhex(src.sha256)
    earlier = db.execute(
        select(SourceFile)
        .where(SourceFile.workspace_id == ctx.workspace_id, SourceFile.sha256 == sha)
        .order_by(SourceFile.created_at)
        .limit(1)
    ).scalar_one_or_none()
    duplicate = (
        DuplicateFileOut(
            id=earlier.id,
            original_filename=earlier.original_filename,
            uploaded_at=earlier.created_at,
        )
        if earlier is not None
        else None
    )
    file_id = uuid.uuid4()
    relative = storage.relative_path(ctx.workspace_id, file_id)
    storage.write_file(settings.upload_dir, relative, src.data)
    try:
        row = SourceFile(
            id=file_id,
            workspace_id=ctx.workspace_id,
            data_source_id=_file_source_id(db, ctx.workspace_id),
            original_filename=src.filename[:255],
            storage_path=relative,
            size_bytes=len(src.data),
            sha256=sha,
            detected_format=preview.detected_format,
            detected_encoding=preview.detected_encoding,
            uploaded_by=ctx.principal.user_id,
        )
        db.add(row)
        db.flush()
    except Exception:
        storage.remove_file(settings.upload_dir, relative)
        raise
    return SourceFileOut(**preview.model_dump(), id=file_id, duplicate_of_file=duplicate)


# ---------------------------------------------------------------- file check, IMP-30
def check_file(
    db: Session, settings: Settings, ctx: WorkspaceContext, file_id: uuid.UUID, data: CheckIn
) -> ValidationReportOut:
    """The validation report for a stored file, exactly as an import would see it."""
    row = _stored_file(db, ctx.workspace_id, file_id)
    return validate_source(load_source(settings, row), data.source_type, data.column_mapping)


# ---------------------------------------------------------------- API-15
def start_import(
    db: Session,
    settings: Settings,
    ctx: WorkspaceContext,
    data: ImportIn,
    idempotency_key: str | None,
) -> JobRef:
    key = _idempotency_key(idempotency_key)
    if data.source_type is SourceType.METRICS:
        raise ValidationFailedError(
            "Importing product metrics is not available yet; choose a feedback source type.",
            details=[{"field": "source_type", "issue": "not_supported_yet"}],
        )
    row = _stored_file(db, ctx.workspace_id, data.source_file_id)
    # The same checks the job will apply: mapping fits the file, record limit (A-05).
    adapter = open_for_rows(load_source(settings, row), data.source_type, data.column_mapping)
    assert adapter.mapping is not None  # noqa: S101 - open_for_rows guarantees it

    import_id = uuid.uuid4()
    job_id = enqueue_job(
        db,
        workspace_id=ctx.workspace_id,
        job_type="ingest",
        payload={"import_job_id": str(import_id)},
        created_by=ctx.principal.user_id,
        idempotency_key=key,
    )
    existing = db.execute(
        select(ImportJob.id).where(
            ImportJob.workspace_id == ctx.workspace_id, ImportJob.job_id == job_id
        )
    ).scalar_one_or_none()
    if existing is not None:  # a repeated Idempotency-Key: the original import
        return JobRef(job_id=job_id, resource_id=existing)

    db.add(
        ImportJob(
            id=import_id,
            workspace_id=ctx.workspace_id,
            data_source_id=row.data_source_id,
            source_file_id=row.id,
            source_type=data.source_type.value,
            column_mapping=adapter.mapping.mapped_columns(),
            job_id=job_id,
            submitted_by=ctx.principal.user_id,
        )
    )
    db.flush()
    record(
        db,
        action="import.started",
        workspace_id=ctx.workspace_id,
        actor_user_id=ctx.principal.user_id,
        target_type="import_job",
        target_id=import_id,
        details={"job_id": str(job_id)},
        ip=ctx.principal.ip,
    )
    return JobRef(job_id=job_id, resource_id=import_id)


# ---------------------------------------------------------------- API-16, API-17
def _import_query(workspace_id: uuid.UUID) -> Any:
    return (
        select(ImportJob, SourceFile.original_filename, Job.progress, Job.error)
        .outerjoin(
            SourceFile,
            and_(
                SourceFile.workspace_id == ImportJob.workspace_id,
                SourceFile.id == ImportJob.source_file_id,
            ),
        )
        .outerjoin(
            Job, and_(Job.workspace_id == ImportJob.workspace_id, Job.id == ImportJob.job_id)
        )
        .where(ImportJob.workspace_id == workspace_id)
    )


def _import_out(
    imp: ImportJob, filename: str | None, progress: Any, error: str | None
) -> ImportOut:
    prog = None
    if isinstance(progress, dict) and "total" in progress:
        prog = ImportProgressOut(processed=int(progress["processed"]), total=int(progress["total"]))
    failure = (imp.report or {}).get("error") if imp.status == "failed" else None
    return ImportOut(
        id=imp.id,
        source_type=SourceType(imp.source_type),
        status=imp.status,  # type: ignore[arg-type]
        original_filename=filename,
        source_file_id=imp.source_file_id,
        submitted_by=imp.submitted_by,
        created_at=imp.created_at,
        started_at=imp.started_at,
        finished_at=imp.finished_at,
        job_id=imp.job_id,
        progress=prog,
        error=failure or (error if imp.status == "failed" else None),
        report=imp.report,
    )


def list_imports(
    db: Session, ctx: WorkspaceContext, *, status: str | None, limit: int, cursor: str | None
) -> Page[ImportOut]:
    query = _import_query(ctx.workspace_id)
    if status is not None:
        query = query.where(ImportJob.status == status)
    after = decode_cursor(cursor)
    if after is not None:  # newest first
        query = query.where(
            or_(
                ImportJob.created_at < after[0],
                and_(ImportJob.created_at == after[0], ImportJob.id < after[1]),
            )
        )
    rows = db.execute(
        query.order_by(ImportJob.created_at.desc(), ImportJob.id.desc()).limit(limit + 1)
    ).all()
    page, more = rows[:limit], len(rows) > limit
    return Page(
        items=[_import_out(*r) for r in page],
        next_cursor=encode_cursor(page[-1][0].created_at, page[-1][0].id) if more else None,
    )


def get_import(db: Session, ctx: WorkspaceContext, import_id: uuid.UUID) -> ImportOut:
    row = db.execute(_import_query(ctx.workspace_id).where(ImportJob.id == import_id)).one_or_none()
    if row is None:
        raise NotFoundError("The import was not found.")
    return _import_out(*row)


# ---------------------------------------------------------------- API-18
def list_row_errors(
    db: Session,
    ctx: WorkspaceContext,
    import_id: uuid.UUID,
    *,
    kind: str | None,
    stage: str | None,
    limit: int,
    cursor: str | None,
) -> Page[StoredRowErrorOut]:
    get_import(db, ctx, import_id)  # 404 for an unknown import
    query = select(ImportRowError).where(
        ImportRowError.workspace_id == ctx.workspace_id,
        ImportRowError.import_job_id == import_id,
    )
    if kind is not None:
        query = query.where(ImportRowError.kind == kind)
    if stage is not None:
        query = query.where(ImportRowError.stage == stage)
    after = _decode_row_cursor(cursor)
    if after is not None:  # file order
        query = query.where(
            or_(
                ImportRowError.row_number > after[0],
                and_(ImportRowError.row_number == after[0], ImportRowError.id > after[1]),
            )
        )
    rows = list(
        db.execute(
            query.order_by(ImportRowError.row_number, ImportRowError.id).limit(limit + 1)
        ).scalars()
    )
    page, more = rows[:limit], len(rows) > limit
    return Page(
        items=[
            StoredRowErrorOut(
                id=e.id,
                row_number=e.row_number,
                kind=e.kind,  # type: ignore[arg-type]
                stage=e.stage,
                field=e.field,
                code=e.code,
                message=e.message,
            )
            for e in page
        ],
        next_cursor=_encode_row_cursor(page[-1].row_number, page[-1].id) if more else None,
    )


def _encode_row_cursor(row_number: int, row_id: uuid.UUID) -> str:
    return base64.urlsafe_b64encode(json.dumps([row_number, str(row_id)]).encode()).decode()


def _decode_row_cursor(cursor: str | None) -> tuple[int, uuid.UUID] | None:
    if cursor is None:
        return None
    try:
        row_number, row_id = json.loads(base64.urlsafe_b64decode(cursor.encode("ascii")))
        return int(row_number), uuid.UUID(row_id)
    except (ValueError, TypeError, binascii.Error) as exc:
        raise ValidationFailedError(
            "The cursor is not valid.", details=[{"field": "cursor", "issue": "invalid"}]
        ) from exc
