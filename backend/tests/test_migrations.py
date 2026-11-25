"""Alembic upgrade on the test database (marker ``db``)."""

from __future__ import annotations

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

from elucis.core.config import BACKEND_ROOT, get_settings
from elucis.db.engine import normalise_url

pytestmark = pytest.mark.db


def test_upgrade_head_is_idempotent_and_requires_pgvector(
    database_url: str, test_schema: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Run against the throwaway schema so the test never touches real migration state.
    url = (
        database_url
        + ("&" if "?" in database_url else "?")
        + f"options=-csearch_path%3D{test_schema}"
    )
    monkeypatch.setenv("DATABASE_MIGRATION_URL", url)
    get_settings.cache_clear()
    try:
        cfg = Config(str(BACKEND_ROOT / "alembic.ini"))
        command.upgrade(cfg, "head")
        command.upgrade(cfg, "head")  # second run is a no-op
    finally:
        get_settings.cache_clear()
    engine = create_engine(normalise_url(database_url), poolclass=NullPool)
    with engine.connect() as conn:
        version = conn.execute(
            text(f'SELECT version_num FROM "{test_schema}".alembic_version')
        ).scalar_one()
        ext = conn.execute(
            text("SELECT extversion FROM pg_extension WHERE extname='vector'")
        ).scalar_one()
    engine.dispose()
    assert version == "0001"
    assert ext == "0.8.7"
