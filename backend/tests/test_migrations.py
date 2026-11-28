"""Alembic migrations on the test database (marker ``db``).

Every test works in its own throwaway schema, so real migration state is never touched.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Iterator

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.pool import NullPool

from elucis.core.config import BACKEND_ROOT, REPO_ROOT, get_settings
from elucis.db.engine import normalise_url
from tests.conftest import schema_url, upgrade_schema

pytestmark = pytest.mark.db

D07 = REPO_ROOT / "docs" / "design" / "07_DATABASE_SCHEMA.md"


def d07_table_names() -> set[str]:
    """Table names as written in the D07 data dictionary (bold headings such as **users**)."""
    return set(re.findall(r"^\*\*([a-z_]+)\*\*", D07.read_text(encoding="utf-8"), re.MULTILINE))


@pytest.fixture
def scratch_schema(database_url: str) -> Iterator[tuple[str, Engine]]:
    schema = f"mig_{uuid.uuid4().hex[:12]}"
    engine = create_engine(normalise_url(database_url), poolclass=NullPool)
    with engine.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    try:
        yield schema, engine
    finally:
        with engine.begin() as conn:
            conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        engine.dispose()


def _tables(engine: Engine, schema: str) -> set[str]:
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT table_name FROM information_schema.tables"
                " WHERE table_schema = :s AND table_type = 'BASE TABLE'"
            ),
            {"s": schema},
        )
        return {r[0] for r in rows} - {"alembic_version"}


def _version(engine: Engine, schema: str) -> str:
    with engine.connect() as conn:
        return str(
            conn.execute(text(f'SELECT version_num FROM "{schema}".alembic_version')).scalar_one()
        )


def test_d07_defines_54_tables() -> None:
    assert len(d07_table_names()) == 54


def test_upgrade_head_is_idempotent_and_creates_the_d07_tables(
    database_url: str, scratch_schema: tuple[str, Engine]
) -> None:
    schema, engine = scratch_schema
    upgrade_schema(database_url, schema)
    upgrade_schema(database_url, schema)  # second run is a no-op
    assert _version(engine, schema) == "0004"
    assert _tables(engine, schema) == d07_table_names()
    with engine.connect() as conn:
        ext = conn.execute(text("SELECT extversion FROM pg_extension WHERE extname='vector'"))
        assert ext.scalar_one() == "0.8.7"


def test_upgrade_downgrade_upgrade_is_clean(
    database_url: str, scratch_schema: tuple[str, Engine], monkeypatch: pytest.MonkeyPatch
) -> None:
    schema, engine = scratch_schema
    upgrade_schema(database_url, schema)
    assert len(_tables(engine, schema)) == 54

    monkeypatch.setenv("DATABASE_MIGRATION_URL", schema_url(database_url, schema))
    get_settings.cache_clear()
    try:
        command.downgrade(Config(str(BACKEND_ROOT / "alembic.ini")), "0001")
    finally:
        get_settings.cache_clear()
    assert _tables(engine, schema) == set()
    assert _version(engine, schema) == "0001"
    with engine.connect() as conn:
        leftovers = conn.execute(
            text(
                "SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace"
                " WHERE n.nspname = :s"
            ),
            {"s": schema},
        ).scalar_one()
    assert leftovers == 0

    monkeypatch.delenv("DATABASE_MIGRATION_URL")
    upgrade_schema(database_url, schema)
    assert _tables(engine, schema) == d07_table_names()
