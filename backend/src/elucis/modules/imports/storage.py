"""Uploaded files on disk: ``<upload_dir>/<workspace>/<uuid>`` (D03 SVC-03).

The stored path is relative to ``upload_dir`` and built only from UUIDs, never from the
uploaded file name, so it cannot point outside the directory. Files are written once and
never changed (``source_files`` is immutable); they are removed with their workspace.
"""

from __future__ import annotations

import os
import shutil
import uuid
from pathlib import Path


def relative_path(workspace_id: uuid.UUID, file_id: uuid.UUID) -> str:
    return f"{workspace_id}/{file_id}"


def write_file(upload_dir: Path, relative: str, data: bytes) -> None:
    """Write atomically: a crash never leaves a half-written file under the final name."""
    target = upload_dir / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(target.name + ".partial")
    with partial.open("wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    partial.replace(target)


def read_file(upload_dir: Path, relative: str) -> bytes:
    return (upload_dir / relative).read_bytes()


def remove_file(upload_dir: Path, relative: str) -> None:
    (upload_dir / relative).unlink(missing_ok=True)


def remove_workspace_files(upload_dir: Path, workspace_id: uuid.UUID) -> None:
    """Delete a workspace's upload directory (after the workspace itself is deleted)."""
    shutil.rmtree(upload_dir / str(workspace_id), ignore_errors=True)
