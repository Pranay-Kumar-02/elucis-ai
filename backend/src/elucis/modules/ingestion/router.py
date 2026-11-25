"""Development-only source endpoints: check, validate and fetch feedback files.

Mounted only when ``ENABLE_DEV_ENDPOINTS=true`` and never in production (settings
validator). They run the real source-fetching layer (file adapter, mapping rules, row
validation) without authentication or storage, so files can be checked before workspaces
and the database exist. Nothing is written to disk.

Production equivalents (need a session, a workspace role and the database):
``POST /workspaces/{ws}/files`` (API-14) and ``POST /workspaces/{ws}/imports`` (API-15).

Every endpoint takes multipart form data with exactly one of ``file`` or ``pasted_text``.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, File, Form, Query, UploadFile
from starlette.concurrency import run_in_threadpool

from elucis.api.deps import SettingsDep
from elucis.modules.ingestion.adapters.base import SourceType
from elucis.modules.ingestion.schemas import (
    FetchPageOut,
    FilePreviewOut,
    SourceInfoOut,
    ValidationReportOut,
)
from elucis.modules.ingestion.service import (
    fetch_source,
    parse_mapping,
    preview_source,
    read_source_input,
    source_catalogue,
    validate_source,
)

UPLOAD_PATH_PREFIX = "/api/v1/dev/sources/"

router = APIRouter(prefix="/dev/sources", tags=["dev: data sources"])

FileField = Annotated[UploadFile | None, File(description="CSV, JSON (array of records) or TXT")]
PastedField = Annotated[str | None, Form(description="Pasted feedback text (FR-ING-10)")]
MappingField = Annotated[
    str | None,
    Form(description='Column mapping as JSON, e.g. {"text": "review", "rating": "stars"}'),
]


@router.get("/adapters", response_model=list[SourceInfoOut], summary="Source adapter catalogue")
def adapters() -> list[SourceInfoOut]:
    """Which sources are implemented and which are designed only (no live connector exists)."""
    return source_catalogue()


@router.post("/preview", response_model=FilePreviewOut, summary="Detect and preview a source")
async def preview(
    settings: SettingsDep,
    file: FileField = None,
    pasted_text: PastedField = None,
    source_type: Annotated[SourceType, Form()] = SourceType.REVIEW,
    rows: Annotated[int | None, Query(ge=1, le=200)] = None,
) -> FilePreviewOut:
    """Format, encoding, columns, the first rows and a suggested column mapping."""
    src = await read_source_input(file, pasted_text, settings.upload_max_bytes)
    # Parsing is CPU-bound; keep it off the event loop.
    return await run_in_threadpool(preview_source, src, source_type, rows or settings.preview_rows)


@router.post("/validate", response_model=ValidationReportOut, summary="Validate every row")
async def validate(
    settings: SettingsDep,
    source_type: Annotated[SourceType, Form()],
    file: FileField = None,
    pasted_text: PastedField = None,
    mapping: MappingField = None,
) -> ValidationReportOut:
    """Apply the mapping and the SVC-04 rules to every row: counts, row errors with reasons
    (DR-09) and a normalised sample. Text files may omit the mapping."""
    column_mapping = parse_mapping(mapping)
    src = await read_source_input(file, pasted_text, settings.upload_max_bytes)
    return await run_in_threadpool(validate_source, src, source_type, column_mapping)


@router.post("/fetch", response_model=FetchPageOut, summary="Fetch normalised records")
async def fetch(
    *,
    settings: SettingsDep,
    source_type: Annotated[SourceType, Form()],
    file: FileField = None,
    pasted_text: PastedField = None,
    mapping: MappingField = None,
    cursor: Annotated[str | None, Query(max_length=200)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> FetchPageOut:
    """One page of normalised records and rejected rows; pass ``next_cursor`` (with the same
    file) for the next page (D09 cursor pagination)."""
    column_mapping = parse_mapping(mapping)
    src = await read_source_input(file, pasted_text, settings.upload_max_bytes)
    return await run_in_threadpool(fetch_source, src, source_type, column_mapping, cursor, limit)
