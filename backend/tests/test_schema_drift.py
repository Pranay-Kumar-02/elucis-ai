"""The ORM models and the migrated schema describe the same database (marker ``db``).

Alembic's comparison covers tables, columns (type and nullability), keys, foreign keys,
unique constraints and indexes. CHECK constraints and row-level security are not compared
by Alembic, so they are checked against the catalogue here.
"""

from __future__ import annotations

from typing import Any

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import CheckConstraint, Engine, text

from elucis.db import models
from elucis.db.base import Base
from tests.test_migrations import d07_table_names

pytestmark = pytest.mark.db

TABLES = Base.metadata.tables


def test_models_define_exactly_the_d07_tables() -> None:
    assert set(TABLES) == d07_table_names()
    assert len(TABLES) == 54


def test_models_match_the_migrated_schema(owner_engine: Engine) -> None:
    with owner_engine.connect() as conn:
        context = MigrationContext.configure(
            conn, opts={"compare_type": True, "target_metadata": Base.metadata}
        )
        diff: list[Any] = compare_metadata(context, Base.metadata)
    assert diff == []


def test_check_constraints_match(owner_engine: Engine, migrated_schema: str) -> None:
    expected = {
        str(c.name)
        for table in TABLES.values()
        for c in table.constraints
        if isinstance(c, CheckConstraint)
    }
    with owner_engine.connect() as conn:
        live = set(
            conn.execute(
                text(
                    "SELECT c.conname FROM pg_constraint c"
                    " JOIN pg_namespace n ON n.oid = c.connamespace"
                    " WHERE n.nspname = :s AND c.contype = 'c'"
                ),
                {"s": migrated_schema},
            ).scalars()
        )
    assert live == expected


def test_row_level_security_is_forced_on_every_tenant_table(
    owner_engine: Engine, migrated_schema: str
) -> None:
    with owner_engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity FROM pg_class c"
                " JOIN pg_namespace n ON n.oid = c.relnamespace"
                " WHERE n.nspname = :s AND c.relkind = 'r' AND c.relname <> 'alembic_version'"
            ),
            {"s": migrated_schema},
        ).all()
    protected = {name for name, enabled, forced in rows if enabled and forced}
    assert protected == set(TABLES) - models.UNSCOPED_TABLES
    assert len(protected) == 48
    assert not {name for name, enabled, _ in rows if enabled} & models.UNSCOPED_TABLES


def test_policies_compare_workspace_with_the_transaction_setting(
    owner_engine: Engine, migrated_schema: str
) -> None:
    with owner_engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT tablename, policyname, cmd, roles::text[], qual, with_check"
                " FROM pg_policies WHERE schemaname = :s"
            ),
            {"s": migrated_schema},
        ).all()
    by_table: dict[str, set[str]] = {}
    for table, policy, *_ in rows:
        by_table.setdefault(table, set()).add(policy)
    tenant = set(TABLES) - models.UNSCOPED_TABLES - {"audit_logs"}
    assert all("tenant_isolation" in by_table.get(t, set()) for t in tenant)
    assert by_table["jobs"] == {"tenant_isolation", "worker_queue_read", "worker_queue_update"}
    assert by_table["audit_logs"] == {"audit_read", "audit_insert", "audit_global_read"}
    for table, policy, cmd, roles, qual, with_check in rows:
        if policy == "tenant_isolation":
            assert cmd == "ALL" and roles == ["public"], table
            for expression in (qual, with_check):
                assert "current_setting('app.workspace_id'::text, true)" in expression, table
        if policy.startswith("worker_queue"):
            assert roles == ["app_worker"]
        if policy == "audit_global_read":
            assert roles == ["app_owner"] and qual == "(workspace_id IS NULL)"
