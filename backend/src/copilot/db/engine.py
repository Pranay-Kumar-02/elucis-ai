"""SQLAlchemy 2 engine and session foundation (psycopg 3 driver).

* One engine per database role (``api``, ``worker``, ``migration``), created lazily.
* ``session_scope()`` gives one transaction per unit of work: commit on success,
  rollback on error, always closed.
* ``workspace_scope()`` applies ``SET LOCAL app.workspace_id`` for row-level security
  (D07 section 5). It is used from the first tenant table onwards.
"""

from __future__ import annotations

import threading
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from copilot.core.config import Settings, get_settings
from copilot.core.errors import DatabaseUnavailableError

_engines: dict[str, Engine] = {}
_factories: dict[str, sessionmaker[Session]] = {}
_lock = threading.Lock()


def normalise_url(raw: str) -> str:
    """Accept ``postgresql://`` or ``postgres://`` and force the psycopg 3 driver."""
    url = make_url(raw.replace("postgres://", "postgresql://", 1))
    if url.drivername in {"postgresql", "postgresql+psycopg2"}:
        url = url.set(drivername="postgresql+psycopg")
    if url.drivername != "postgresql+psycopg":
        raise ValueError(f"Unsupported database driver {url.drivername!r}; use postgresql://")
    return url.render_as_string(hide_password=False)


def build_engine(
    raw_url: str, settings: Settings, *, application_name: str, pooled: bool = True
) -> Engine:
    """Create an engine. ``pooled=False`` (NullPool) suits one-off processes such as
    migrations and the setup verifier."""
    pool_args: dict[str, Any] = (
        {
            "pool_size": settings.database_pool_size,
            "max_overflow": settings.database_max_overflow,
            "pool_pre_ping": True,
            "pool_recycle": 1800,
        }
        if pooled
        else {"poolclass": NullPool}
    )
    url = make_url(normalise_url(raw_url))
    # Server-side guards against runaway queries and forgotten transactions, appended to any
    # ``options`` already present in the URL (for example a search_path).
    options = (
        f"-c statement_timeout={settings.database_statement_timeout_ms}"
        " -c idle_in_transaction_session_timeout=60000"
    )
    existing = url.query.get("options")
    if existing:
        options = f"{existing if isinstance(existing, str) else ' '.join(existing)} {options}"
    return create_engine(
        url.difference_update_query(["options"]),
        **pool_args,
        connect_args={
            "connect_timeout": settings.database_connect_timeout_s,
            "application_name": application_name,
            "options": options,
        },
    )


def get_engine(role: str = "api", settings: Settings | None = None) -> Engine:
    """Return the shared engine for a role (cached per role and URL)."""
    settings = settings or get_settings()
    raw = settings.dsn(role)
    if not raw:
        raise DatabaseUnavailableError("The database is not configured (DATABASE_URL).")
    key = f"{role}|{raw}"
    with _lock:
        engine = _engines.get(key)
        if engine is None:
            engine = build_engine(raw, settings, application_name=f"copilot-{role}")
            _engines[key] = engine
            _factories[key] = sessionmaker(bind=engine, expire_on_commit=False)
            _factories[role] = _factories[key]
        return engine


@contextmanager
def session_scope(role: str = "api", settings: Settings | None = None) -> Iterator[Session]:
    get_engine(role, settings)
    session = _factories[role]()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def workspace_scope(session: Session, workspace_id: uuid.UUID) -> None:
    """Bind the current transaction to one workspace for row-level security."""
    if not isinstance(workspace_id, uuid.UUID):
        raise TypeError("workspace_id must be a UUID")
    session.execute(
        text("SELECT set_config('app.workspace_id', :ws, true)"), {"ws": str(workspace_id)}
    )


def dispose_engines() -> None:
    with _lock:
        for engine in _engines.values():
            engine.dispose()
        _engines.clear()
        _factories.clear()
