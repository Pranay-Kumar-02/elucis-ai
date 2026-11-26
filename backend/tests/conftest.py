"""Shared fixtures.

Unit tests need nothing external. Tests marked ``db`` use TEST_DATABASE_URL (role app_owner
on the separate ``elucis_test`` database, never the dev database); each test session works
in its own throwaway schema, removed afterwards. Without TEST_DATABASE_URL they are reported
as skipped with the reason, never silently passed.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.pool import NullPool

from elucis.core.config import BACKEND_ROOT, REPO_ROOT, Settings, get_settings
from elucis.core.logging import redact_text
from elucis.db.engine import dispose_engines, normalise_url
from elucis.main import create_app

UNREACHABLE_OLLAMA = "http://127.0.0.1:9"  # discard port: connection refused immediately


class SecretURL(str):
    """A database URL whose repr hides the password, so failing tests never print it."""

    __slots__ = ()

    def __repr__(self) -> str:
        return repr(redact_text(str(self)))


def _env_value(name: str) -> SecretURL | None:
    """A test database URL from the environment, else from the project's .env file."""
    url = os.environ.get(name)
    env_file = REPO_ROOT / ".env"
    if not url and env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.startswith(f"{name}="):
                url = line.split("=", 1)[1].strip()
    return SecretURL(url) if url else None


TEST_DATABASE_URL = _env_value("TEST_DATABASE_URL")  # app_owner on elucis_test
TEST_DATABASE_API_URL = _env_value("TEST_DATABASE_API_URL")  # app_api on elucis_test
TEST_DATABASE_WORKER_URL = _env_value("TEST_DATABASE_WORKER_URL")  # app_worker on elucis_test


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


# ---------------------------------------------------------------- migrated schema (0002+)
def schema_url(url: str, schema: str) -> str:
    """The URL with ``search_path`` pinned to a throwaway schema (then public for pgvector)."""
    return url + ("&" if "?" in url else "?") + f"options=-csearch_path%3D{schema},public"


def upgrade_schema(url: str, schema: str, revision: str = "head") -> None:
    """Run Alembic against one throwaway schema; settings are restored afterwards."""
    previous = os.environ.get("DATABASE_MIGRATION_URL")
    os.environ["DATABASE_MIGRATION_URL"] = schema_url(url, schema)
    get_settings.cache_clear()
    try:
        command.upgrade(Config(str(BACKEND_ROOT / "alembic.ini")), revision)
    finally:
        if previous is None:
            os.environ.pop("DATABASE_MIGRATION_URL", None)
        else:
            os.environ["DATABASE_MIGRATION_URL"] = previous
        get_settings.cache_clear()


def _role_engine(url: str | None, schema: str, env_name: str) -> Engine:
    if not url:
        pytest.skip(f"{env_name} is not set (see .env.example)")
    return create_engine(
        normalise_url(url),
        poolclass=NullPool,
        connect_args={"options": f"-c search_path={schema},public"},
    )


@pytest.fixture(scope="session")
def migrated_schema(database_url: str) -> Iterator[str]:
    """A throwaway schema at migration head, usable by app_api and app_worker."""
    schema = f"mig_{uuid.uuid4().hex[:12]}"
    admin = create_engine(normalise_url(database_url), poolclass=NullPool)
    with admin.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))
        conn.execute(text(f'GRANT USAGE ON SCHEMA "{schema}" TO app_api, app_worker'))
    try:
        upgrade_schema(database_url, schema)
        yield schema
    finally:
        with admin.begin() as conn:
            conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


@pytest.fixture(scope="session")
def owner_engine(database_url: str, migrated_schema: str) -> Iterator[Engine]:
    engine = _role_engine(database_url, migrated_schema, "TEST_DATABASE_URL")
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def api_engine(migrated_schema: str) -> Iterator[Engine]:
    engine = _role_engine(TEST_DATABASE_API_URL, migrated_schema, "TEST_DATABASE_API_URL")
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def worker_engine(migrated_schema: str) -> Iterator[Engine]:
    engine = _role_engine(TEST_DATABASE_WORKER_URL, migrated_schema, "TEST_DATABASE_WORKER_URL")
    yield engine
    engine.dispose()
