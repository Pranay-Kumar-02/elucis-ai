"""Optional Gemini backup (IMP-38, proposed for D07): a per-workspace switch, off by
default, and the provider of every recorded model call.

Revision ID: 0004
Revises: 0003
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE workspaces ADD COLUMN IF NOT EXISTS gemini_fallback boolean NOT NULL"
        " DEFAULT false"
    )
    op.execute(
        "ALTER TABLE llm_call_records ADD COLUMN IF NOT EXISTS provider text NOT NULL"
        " DEFAULT 'ollama'"
    )
    op.execute(
        "ALTER TABLE llm_call_records ADD CONSTRAINT ck_llm_call_records_provider"
        " CHECK (provider IN ('ollama', 'gemini'))"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE llm_call_records DROP CONSTRAINT IF EXISTS ck_llm_call_records_provider")
    op.execute("ALTER TABLE llm_call_records DROP COLUMN IF EXISTS provider")
    op.execute("ALTER TABLE workspaces DROP COLUMN IF EXISTS gemini_fallback")
