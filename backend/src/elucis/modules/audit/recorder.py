"""The one writer of ``audit_logs`` (SEC-14, SEC-15).

Details are restricted to a whitelist of keys, so personal data, customer text and secrets
cannot be written by accident (D07: "No PII or secrets"). Rows are append-only: the
application roles have no UPDATE or DELETE on the table.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import insert
from sqlalchemy.orm import Session

from elucis.db.models import AuditLog

ALLOWED_DETAIL_KEYS = frozenset(
    {
        "reason",
        "required_role",
        "route",
        "role",
        "previous_role",
        "workspace_name",
        "job_id",
        "enabled",
    }
)


def record(
    db: Session,
    *,
    action: str,
    outcome: str = "success",
    workspace_id: uuid.UUID | None,
    actor_user_id: uuid.UUID | None,
    target_type: str | None = None,
    target_id: uuid.UUID | None = None,
    details: dict[str, Any] | None = None,
    ip: str | None = None,
) -> None:
    """Insert one audit entry in the caller's transaction.

    ``workspace_id`` must match the transaction's ``app.workspace_id`` or be ``None`` (sign-in
    events, ``workspace.deleted``), which the ``audit_insert`` policy enforces.
    """
    unknown = set(details or {}) - ALLOWED_DETAIL_KEYS
    if unknown:
        raise ValueError(f"audit detail keys not allowed: {sorted(unknown)}")
    # No RETURNING: a returned row must pass the SELECT policies, and global events
    # (workspace_id NULL) are deliberately unreadable by the application roles.
    db.execute(
        insert(AuditLog)
        .inline()
        .values(
            workspace_id=workspace_id,
            actor_user_id=actor_user_id,
            action=action,
            outcome=outcome,
            target_type=target_type,
            target_id=target_id,
            details=details or {},
            ip=ip,
        )
    )
