"""Theme citations: the records CP-03 cited when naming a theme (IMP-33, proposed for D07).

D07 stores a theme's name and description but has no place for the evidence the name was
based on; the dashboard shows those cited quotes as the theme's evidence (FR-THM-04). The
column is per run, like every other theme statistic, so a later run's naming never rewrites
an earlier run's evidence.

Revision ID: 0003
Revises: 0002
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE theme_run_stats"
        " ADD COLUMN IF NOT EXISTS cited_record_ids uuid[] NOT NULL DEFAULT '{}'::uuid[]"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE theme_run_stats DROP COLUMN IF EXISTS cited_record_ids")
