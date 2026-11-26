"""Seed helpers for tests on the migrated schema.

Every helper takes an open connection inside a transaction. Tenant rows need the
transaction bound to their workspace first (``bind``), because row-level security is
forced even for the owner role.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass

import pytest
from sqlalchemy import Connection, text
from sqlalchemy.exc import DBAPIError


def bind(conn: Connection, workspace_id: uuid.UUID | None) -> None:
    """``SET LOCAL app.workspace_id`` for this transaction (D07 §5)."""
    conn.execute(
        text("SELECT set_config('app.workspace_id', :ws, true)"),
        {"ws": str(workspace_id) if workspace_id else ""},
    )


def new_user(conn: Connection) -> uuid.UUID:
    return uuid.UUID(
        str(
            conn.execute(
                text(
                    "INSERT INTO users (email, password_hash) VALUES (:e, 'argon2id-hash')"
                    " RETURNING id"
                ),
                {"e": f"{uuid.uuid4().hex[:10]}@example.test"},
            ).scalar_one()
        )
    )


def new_workspace(conn: Connection, owner: uuid.UUID, name: str = "Workspace") -> uuid.UUID:
    return uuid.UUID(
        str(
            conn.execute(
                text(
                    "INSERT INTO workspaces (name, customer_key_secret, created_by)"
                    " VALUES (:n, '\\x00'::bytea, :u) RETURNING id"
                ),
                {"n": name, "u": owner},
            ).scalar_one()
        )
    )


@dataclass(frozen=True, slots=True)
class Tenant:
    workspace_id: uuid.UUID
    user_id: uuid.UUID
    data_source_id: uuid.UUID
    import_job_id: uuid.UUID
    record_id: uuid.UUID


def new_tenant(conn: Connection, name: str = "Workspace") -> Tenant:
    """A user, a workspace, a data source, an import job and one feedback record."""
    user = new_user(conn)
    ws = new_workspace(conn, user, name)
    bind(conn, ws)
    source = conn.execute(
        text("INSERT INTO data_sources (workspace_id, name) VALUES (:ws, 'Uploads') RETURNING id"),
        {"ws": ws},
    ).scalar_one()
    import_job = conn.execute(
        text(
            "INSERT INTO import_jobs (workspace_id, data_source_id, source_type, column_mapping,"
            " submitted_by) VALUES (:ws, :src, 'review', '{}', :u) RETURNING id"
        ),
        {"ws": ws, "src": source, "u": user},
    ).scalar_one()
    record = add_record(conn, ws, import_job, 1, "Checkout spins forever after I tap Pay.")
    return Tenant(ws, user, source, import_job, record)


def add_record(
    conn: Connection, ws: uuid.UUID, import_job: uuid.UUID, row: int, raw_text: str
) -> uuid.UUID:
    return uuid.UUID(
        str(
            conn.execute(
                text(
                    "INSERT INTO feedback_records (workspace_id, import_job_id, row_number,"
                    " source_type, raw_text, processed_text)"
                    " VALUES (:ws, :ij, :row, 'review', :t, :t) RETURNING id"
                ),
                {"ws": ws, "ij": import_job, "row": row, "t": raw_text},
            ).scalar_one()
        )
    )


def vector(first: float, dims: int = 1024) -> str:
    return "[" + ",".join([str(first)] + ["0.01"] * (dims - 1)) + "]"


@contextmanager
def expect_sqlstate(code: str) -> Iterator[None]:
    """Expect a database error with one SQLSTATE (for example 23514 check_violation)."""
    with pytest.raises(DBAPIError) as caught:
        yield
    assert getattr(caught.value.orig, "sqlstate", None) == code, caught.value.orig


CHECK_VIOLATION = "23514"
UNIQUE_VIOLATION = "23505"
FOREIGN_KEY_VIOLATION = "23503"
INSUFFICIENT_PRIVILEGE = "42501"  # also raised for a row-level security WITH CHECK failure
DATA_EXCEPTION = "22000"
