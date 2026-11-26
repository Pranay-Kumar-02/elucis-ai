"""Cursor pagination shared by list endpoints (D09 §1, IR-07).

``?limit=50&cursor=<opaque>``; responses are ``{"items": [...], "next_cursor": ... | null}``.
The cursor encodes the sort key of the last item (``created_at`` and ``id``), so pages are
stable while rows are added.
"""

from __future__ import annotations

import base64
import json
import uuid
from datetime import datetime
from typing import Annotated

from fastapi import Query
from pydantic import BaseModel

from elucis.core.errors import ValidationFailedError

LimitQuery = Annotated[int, Query(ge=1, le=200)]
CursorQuery = Annotated[str | None, Query(max_length=200)]
DEFAULT_LIMIT = 50


class Page[T](BaseModel):
    items: list[T]
    next_cursor: str | None


def encode_cursor(created_at: datetime, row_id: uuid.UUID) -> str:
    raw = json.dumps([created_at.isoformat(), str(row_id)]).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii")


def decode_cursor(cursor: str | None) -> tuple[datetime, uuid.UUID] | None:
    if cursor is None:
        return None
    try:
        created_at, row_id = json.loads(base64.urlsafe_b64decode(cursor.encode("ascii")))
        return datetime.fromisoformat(created_at), uuid.UUID(row_id)
    except (ValueError, TypeError) as exc:
        raise ValidationFailedError(
            "The cursor is not valid.", details=[{"field": "cursor", "issue": "invalid"}]
        ) from exc
