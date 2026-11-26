"""Shared column types and constraint helpers for the D07 models.

Constraint names are explicit (``conv``) and identical to migration 0002, so the drift test
can compare the models with the live schema object by object.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import VECTOR
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql.elements import conv

EMBEDDING_DIMENSION = 1024  # D07 section 1; measured for qwen3-embedding:0.6b (F-02)
CURRENT_EMBEDDING_MODEL = "qwen3-embedding:0.6b"

Json = JSONB
UuidArray = ARRAY(Uuid)
Embedding = VECTOR(EMBEDDING_DIMENSION)
Timestamp = DateTime(timezone=True)
EMPTY_OBJECT = text("'{}'::jsonb")
EMPTY_ARRAY = text("'{}'::uuid[]")
NOW = func.now()

SOURCE_TYPES = ("review", "ticket", "feature_request", "transcript", "other", "metrics")


class StdColumns:
    """D07 STD columns: ``id``, ``workspace_id`` and ``created_at``."""

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    created_at: Mapped[datetime] = mapped_column(Timestamp, server_default=NOW)


def std_args(table: str, *constraints: Any) -> tuple[Any, ...]:
    """The STD tenant key and workspace FK, followed by the table's own constraints."""
    return (
        UniqueConstraint("workspace_id", "id", name=conv(f"uq_{table}_workspace_id_id")),
        workspace_fk(table),
        *constraints,
    )


def workspace_fk(table: str) -> ForeignKeyConstraint:
    return ForeignKeyConstraint(
        ["workspace_id"],
        ["workspaces.id"],
        ondelete="CASCADE",
        name=conv(f"fk_{table}_workspace_id"),
    )


def tenant_fk(
    table: str, column: str, target: str, ondelete: str | None = None
) -> ForeignKeyConstraint:
    """Composite tenant FK ``(workspace_id, column) -> target (workspace_id, id)``.

    ``ondelete="SET NULL"`` becomes ``SET NULL (column)``: only the reference is cleared,
    never the ``workspace_id`` it shares with the tenant key.
    """
    if ondelete == "SET NULL":
        ondelete = f"SET NULL ({column})"
    return ForeignKeyConstraint(
        ["workspace_id", column],
        [f"{target}.workspace_id", f"{target}.id"],
        ondelete=ondelete,
        name=conv(f"fk_{table}_{column}"),
    )


def user_fk(table: str, column: str, ondelete: str | None = None) -> ForeignKeyConstraint:
    return ForeignKeyConstraint(
        [column], ["users.id"], ondelete=ondelete, name=conv(f"fk_{table}_{column}")
    )


def check(table: str, name: str, sql: str) -> CheckConstraint:
    return CheckConstraint(sql, name=conv(f"ck_{table}_{name}"))


def check_in(table: str, column: str, *values: str) -> CheckConstraint:
    listed = ", ".join(f"'{v}'" for v in values)
    return check(table, column, f"{column} IN ({listed})")


def unique(table: str, name: str, *columns: str) -> UniqueConstraint:
    return UniqueConstraint(*columns, name=conv(f"uq_{table}_{name}"))


__all__ = [
    "EMPTY_ARRAY",
    "EMPTY_OBJECT",
    "NOW",
    "SOURCE_TYPES",
    "Embedding",
    "Json",
    "StdColumns",
    "Timestamp",
    "UuidArray",
    "check",
    "check_in",
    "std_args",
    "tenant_fk",
    "unique",
    "user_fk",
    "workspace_fk",
]
