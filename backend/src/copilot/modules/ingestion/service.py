"""Ingestion service functions used by the API (no database yet).

``read_upload`` streams an upload with a hard size cap and computes SHA-256 (DR-10 needs the
hash for duplicate-file warnings). ``preview_file`` and ``preview_mapping`` are the
data-fetching functions behind the development preview endpoints and, later, API-14/API-15.
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict

from fastapi import UploadFile

from copilot.core.errors import FileTooLargeError
from copilot.modules.ingestion.adapters.base import ColumnMapping
from copilot.modules.ingestion.adapters.file_adapter import FileAdapter
from copilot.modules.ingestion.adapters.registry import list_sources
from copilot.modules.ingestion.schemas import (
    FilePreviewOut,
    MappedPreviewOut,
    RawItemOut,
    SourceInfoOut,
)

_CHUNK = 1024 * 1024


async def read_upload(upload: UploadFile, max_bytes: int) -> tuple[bytes, str]:
    digest = hashlib.sha256()
    chunks: list[bytes] = []
    size = 0
    while chunk := await upload.read(_CHUNK):
        size += len(chunk)
        if size > max_bytes:
            raise FileTooLargeError(f"The upload is larger than {max_bytes // (1024 * 1024)} MB.")
        digest.update(chunk)
        chunks.append(chunk)
    return b"".join(chunks), digest.hexdigest()


def preview_file(data: bytes, sha256: str, filename: str, rows: int) -> FilePreviewOut:
    adapter = FileAdapter(data, filename)
    parsed = adapter.parsed
    return FilePreviewOut(
        original_filename=filename,
        size_bytes=len(data),
        sha256=sha256,
        detected_format=parsed.format,
        detected_encoding=parsed.encoding,
        csv_delimiter=parsed.csv_delimiter,
        transcript_mode=parsed.transcript_mode,
        columns=parsed.columns,
        preview_rows=adapter.preview(rows),
        total_rows=adapter.item_count,
        warnings=parsed.warnings,
    )


def preview_mapping(
    data: bytes, filename: str, mapping: ColumnMapping | None, rows: int
) -> MappedPreviewOut:
    adapter = FileAdapter(data, filename, mapping)
    items: list[RawItemOut] = []
    for batch, _cursor in adapter.fetch():
        items.extend(RawItemOut(**item.as_dict()) for item in batch[: rows - len(items)])
        if len(items) >= rows:
            break
    return MappedPreviewOut(
        total_items=adapter.item_count, items=items, warnings=adapter.parsed.warnings
    )


def source_catalogue() -> list[SourceInfoOut]:
    return [
        SourceInfoOut(
            **{**asdict(info), "status": info.status.value, "formats": list(info.formats)}
        )
        for info in list_sources()
    ]
