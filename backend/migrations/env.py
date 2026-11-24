"""Alembic environment: online migrations with the app_owner role (D07 section 5)."""

from __future__ import annotations

from alembic import context

from copilot.core.config import get_settings
from copilot.db.base import Base
from copilot.db.engine import build_engine

config = context.config
target_metadata = Base.metadata


def _url() -> str:
    url = get_settings().dsn("migration")
    if not url:
        raise RuntimeError(
            "Set DATABASE_MIGRATION_URL (or DATABASE_URL) before running migrations."
        )
    return url


def run_migrations_offline() -> None:
    context.configure(
        url=_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = build_engine(_url(), get_settings(), application_name="copilot-alembic", pooled=False)
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            transaction_per_migration=True,
        )
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
