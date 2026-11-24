"""Development-only ingestion endpoints.

Mounted only when ``ENABLE_DEV_ENDPOINTS=true`` and never in production (settings validator).
They exercise the real file adapter without authentication or storage, so the team and the
mentor can try data fetching before the auth and schema tasks. The production equivalents
are API-14 (``POST /workspaces/{ws}/files``) and API-15 (imports), which require a session,
a workspace role and the database. Nothing is written to disk by these endpoints.
"""

from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter, File, Form, Query, UploadFile
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool

from copilot.api.deps import SettingsDep
from copilot.core.errors import ValidationFailedError
from copilot.modules.ingestion.adapters.base import ColumnMapping
from copilot.modules.ingestion.schemas import FilePreviewOut, MappedPreviewOut, SourceInfoOut
from copilot.modules.ingestion.service import (
    preview_file,
    preview_mapping,
    read_upload,
    source_catalogue,
)

UPLOAD_PATH_PREFIX = "/api/v1/dev/sources/"

router = APIRouter(prefix="/dev/sources", tags=["dev: data sources"])


@router.get("/adapters", response_model=list[SourceInfoOut], summary="Source adapter catalogue")
def adapters() -> list[SourceInfoOut]:
    """Which sources are implemented and which are designed only (no live connector exists)."""
    return source_catalogue()


@router.post("/preview", response_model=FilePreviewOut, summary="Detect and preview a file")
async def preview(
    settings: SettingsDep,
    file: Annotated[UploadFile, File(description="CSV, JSON (array of objects) or TXT")],
    rows: Annotated[int | None, Query(ge=1, le=200)] = None,
) -> FilePreviewOut:
    data, sha256 = await read_upload(file, settings.upload_max_bytes)
    # Parsing is CPU-bound; keep it off the event loop.
    return await run_in_threadpool(
        preview_file, data, sha256, file.filename or "upload", rows or settings.preview_rows
    )


@router.post("/map", response_model=MappedPreviewOut, summary="Apply a column mapping")
async def map_columns(
    settings: SettingsDep,
    file: Annotated[UploadFile, File()],
    mapping: Annotated[str | None, Form(description='JSON, e.g. {"text": "review"}')] = None,
    rows: Annotated[int | None, Query(ge=1, le=200)] = None,
) -> MappedPreviewOut:
    column_mapping: ColumnMapping | None = None
    if mapping:
        try:
            column_mapping = ColumnMapping.model_validate(json.loads(mapping))
        except (json.JSONDecodeError, ValidationError) as exc:
            raise ValidationFailedError(
                "mapping must be a JSON object with at least a text column.",
                details=[{"field": "mapping", "issue": "invalid"}],
            ) from exc
    data, _ = await read_upload(file, settings.upload_max_bytes)
    return await run_in_threadpool(
        preview_mapping,
        data,
        file.filename or "upload",
        column_mapping,
        rows or settings.preview_rows,
    )
