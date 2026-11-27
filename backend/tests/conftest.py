"""Shared fixtures.

Unit tests need nothing external. Tests marked ``db`` use TEST_DATABASE_URL (role app_owner
on the separate ``elucis_test`` database, never the dev database); each test session works
in its own throwaway schema, removed afterwards. Without TEST_DATABASE_URL they are reported
as skipped with the reason, never silently passed.
"""

from __future__ import annotations

import base64
import ipaddress
import os
import secrets
import uuid
from collections.abc import Callable, Iterator
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.pool import NullPool

from elucis.api.auth import current_principal
from elucis.core.config import BACKEND_ROOT, REPO_ROOT, Settings, get_settings
from elucis.core.logging import redact_text
from elucis.db.engine import dispose_engines, normalise_url
from elucis.main import create_app
from elucis.modules.identity.context import Principal

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


SIGNED_IN = Principal(
    user_id=uuid.UUID(int=1), session_id=uuid.UUID(int=2), session_token="unit-test", ip=None
)


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    """An app without a database, for unit tests of routes that are not about sign-in.

    Sign-in is replaced by a fixed principal. Real sessions, CSRF and roles are tested
    against the database in ``test_auth_api.py`` and ``test_workspaces_api.py``.
    """
    app = create_app(settings)
    app.dependency_overrides[current_principal] = lambda: SIGNED_IN
    with TestClient(app, raise_server_exceptions=False) as c:
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


# ---------------------------------------------------------------- the API on the real schema
TEST_ENCRYPTION_KEY = base64.urlsafe_b64encode(os.urandom(32)).decode()


@pytest.fixture(scope="session")
def api_settings(migrated_schema: str, tmp_path_factory: pytest.TempPathFactory) -> Settings:
    """Settings for an app that runs as app_api on the migrated test schema. Uploads go to a
    temporary directory, never to the project's ``data/``."""
    if not TEST_DATABASE_API_URL:
        pytest.skip("TEST_DATABASE_API_URL is not set (see .env.example)")
    return make_settings(
        database_url=schema_url(TEST_DATABASE_API_URL, migrated_schema),
        session_secret=secrets.token_urlsafe(48),
        app_encryption_key=TEST_ENCRYPTION_KEY,
        upload_dir=tmp_path_factory.mktemp("uploads"),
    )


TEST_PASSWORD = "correct horse battery"  # 21 characters, not on the common list


class ApiClient:
    """A browser: its own cookie jar and IP address, and the CSRF token from sign-in."""

    def __init__(self, client: TestClient) -> None:
        self.http = client
        self.csrf: str | None = None

    def call(self, method: str, path: str, **kwargs: object) -> Any:
        headers = dict(kwargs.pop("headers", None) or {})  # type: ignore[call-overload]
        if self.csrf and method.upper() in {"POST", "PUT", "PATCH", "DELETE"}:
            headers.setdefault("X-CSRF-Token", self.csrf)
        return self.http.request(method, f"/api/v1{path}", headers=headers, **kwargs)

    def sign_up(self, email: str | None = None, password: str = TEST_PASSWORD) -> str:
        email = email or f"{uuid.uuid4().hex[:12]}@example.test"
        registered = self.call(
            "POST", "/auth/register", json={"email": email, "password": password}
        )
        assert registered.status_code == 201, registered.text
        self.sign_in(email, password)
        return email

    def sign_in(self, email: str, password: str = TEST_PASSWORD) -> Any:
        response = self.call("POST", "/auth/login", json={"email": email, "password": password})
        if response.status_code == 200:
            self.csrf = response.json()["csrf_token"]
        return response


@pytest.fixture
def browser(api_settings: Settings) -> Iterator[Callable[[], ApiClient]]:
    """Factory for independent browsers against one app instance."""
    app = create_app(api_settings)
    opened: list[TestClient] = []

    def open_browser() -> ApiClient:
        # A fresh address in the IPv6 documentation range (2001:db8::/32) per browser, so the
        # per-IP sign-in limit of one test never affects another.
        ip = str(ipaddress.IPv6Address((0x20010DB8 << 96) | secrets.randbits(96)))
        client = TestClient(app, raise_server_exceptions=False, client=(ip, 50000))
        client.__enter__()
        opened.append(client)
        return ApiClient(client)

    yield open_browser
    for client in opened:
        client.__exit__(None, None, None)
