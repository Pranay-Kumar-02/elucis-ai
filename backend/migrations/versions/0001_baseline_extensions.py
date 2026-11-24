"""Baseline: require pgvector >= 0.8 in the database.

The 54 tables of D07/D08 start in revision 0002 (schema task). This revision only makes
sure the ``vector`` extension exists. ``vector`` is not a trusted extension, so it is
normally created once by a superuser in database/bootstrap; ``IF NOT EXISTS`` makes this
step a no-op then, and a clear error is raised if it is missing and cannot be created.

Revision ID: 0001
Revises:
Create Date: 2026-11-24
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

MIN_VERSION = (0, 8, 0)


def upgrade() -> None:
    bind = op.get_bind()
    installed = bind.execute(
        sa.text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
    ).scalar()
    if installed is None:
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
        installed = bind.execute(
            sa.text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
        ).scalar()
    version = tuple(int(p) for p in str(installed).split(".") if p.isdigit())
    if version < MIN_VERSION:
        raise RuntimeError(f"pgvector {installed} is too old; 0.8.0 or newer is required")


def downgrade() -> None:
    # Dropping the extension would destroy vector data; downgrade below the baseline is a
    # deliberate manual action, never an automatic one.
    pass
