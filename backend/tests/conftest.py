"""Shared fixtures.

Unit tests need nothing external. Tests marked ``db`` use TEST_DATABASE_URL (role app_owner
on the separate ``copilot_test`` database, never the dev database); each test session works
in its own throwaway schema, removed afterwards. Without TEST_DATABASE_URL they are reported
as skipped with the reason, never silently passed.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.pool import NullPool

from copilot.core.config import REPO_ROOT, Settings
from copilot.core.logging import redact_text
from copilot.db.engine import dispose_engines, normalise_url
from copilot.main import create_app

UNREACHABLE_OLLAMA = "http://127.0.0.1:9"  # discard port: connection refused immediately


class SecretURL(str):
    """A database URL whose repr hides the password, so failing tests never print it."""

    __slots__ = ()

    def __repr__(self) -> str:
        return repr(redact_text(str(self)))


def _test_database_url() -> str | None:
    url = os.environ.get("TEST_DATABASE_URL")
    if url:
        return url
    env_file = REPO_ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.startswith("TEST_DATABASE_URL="):
                return line.split("=", 1)[1].strip() or None
    return None


_raw_url = _test_database_url()
TEST_DATABASE_URL = SecretURL(_raw_url) if _raw_url else None


def make_settings(**overrides: object) -> Settings:
    base: dict[str, object] = {
        "app_env": "test",
        "log_level": "WARNING",
        "enable_dev_endpoints": True,
        "database_url": None,
        "database_worker_url": None,
        "database_migration_url": None,
        "ollama_base_url": UNREACHABLE_OLLAMA,
    }
    base.update(overrides)
    return Settings(_env_file=None, **base)  # type: ignore[call-arg]


@pytest.fixture(autouse=True)
def _isolate_engines() -> Iterator[None]:
    dispose_engines()
    yield
    dispose_engines()


@pytest.fixture
def settings() -> Settings:
    return make_settings()


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(settings), raise_server_exceptions=False) as c:
        yield c


@pytest.fixture(scope="session")
def database_url() -> str:
    if not TEST_DATABASE_URL:
        pytest.skip("TEST_DATABASE_URL is not set (see .env.example)")
    return TEST_DATABASE_URL


@pytest.fixture(scope="session")
def test_schema(database_url: str) -> Iterator[str]:
    """A private schema for this test session; dropped at the end (only this schema)."""
    schema = f"test_{uuid.uuid4().hex[:12]}"
    admin = create_engine(normalise_url(database_url), poolclass=NullPool)
    with admin.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    try:
        yield schema
    finally:
        with admin.begin() as conn:
            conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


@pytest.fixture
def schema_engine(database_url: str, test_schema: str) -> Iterator[Engine]:
    engine = create_engine(
        normalise_url(database_url),
        poolclass=NullPool,
        connect_args={"options": f"-c search_path={test_schema},public"},
    )
    yield engine
    engine.dispose()
