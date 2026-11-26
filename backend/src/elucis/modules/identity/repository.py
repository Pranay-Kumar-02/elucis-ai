"""Data access for SVC-01. Services never build queries; workspace-scoped queries always
filter by ``workspace_id`` as well as relying on row-level security (D09 §8)."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import and_, delete, func, insert, or_, select, text, tuple_, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from elucis.db.models import Job, LoginAttempt, User, Workspace, WorkspaceMembership
from elucis.db.models import Session as SessionRow


def database_now(db: Session) -> datetime:
    """The database clock, used for every time comparison (one clock, see F-07)."""
    now: datetime = db.execute(select(func.now())).scalar_one()
    return now


# ---------------------------------------------------------------- users
def user_by_email(db: Session, email: str) -> User | None:
    return db.execute(
        select(User).where(func.lower(User.email) == email.strip().lower())
    ).scalar_one_or_none()


def insert_user(db: Session, *, email: str, password_hash: str, display_name: str | None) -> User:
    user = User(email=email, password_hash=password_hash, display_name=display_name)
    db.add(user)
    db.flush()
    db.refresh(user)
    return user


# ---------------------------------------------------------------- sessions
def session_with_user(db: Session, token_hash: bytes) -> tuple[SessionRow, User] | None:
    row = db.execute(
        select(SessionRow, User)
        .join(User, User.id == SessionRow.user_id)
        .where(SessionRow.token_hash == token_hash)
    ).one_or_none()
    return (row[0], row[1]) if row else None


def insert_session(
    db: Session,
    *,
    user_id: uuid.UUID,
    token_hash: bytes,
    csrf_token_hash: bytes,
    expires_at: datetime,
    ip: str | None,
    user_agent: str | None,
) -> None:
    db.execute(
        insert(SessionRow).values(
            user_id=user_id,
            token_hash=token_hash,
            csrf_token_hash=csrf_token_hash,
            expires_at=expires_at,
            ip=ip,
            user_agent=user_agent,
        )
    )


def delete_session(db: Session, session_id: uuid.UUID) -> None:
    db.execute(delete(SessionRow).where(SessionRow.id == session_id))


def delete_session_by_token(db: Session, token_hash: bytes) -> None:
    db.execute(delete(SessionRow).where(SessionRow.token_hash == token_hash))


def touch_session(db: Session, session_id: uuid.UUID, now: datetime) -> None:
    db.execute(update(SessionRow).where(SessionRow.id == session_id).values(last_seen_at=now))


def delete_expired_sessions(
    db: Session, user_id: uuid.UUID, now: datetime, idle: timedelta
) -> None:
    db.execute(
        delete(SessionRow).where(
            SessionRow.user_id == user_id,
            or_(SessionRow.expires_at <= now, SessionRow.last_seen_at <= now - idle),
        )
    )


def update_user_after_login(
    db: Session, user_id: uuid.UUID, now: datetime, new_hash: str | None
) -> None:
    values: dict[str, Any] = {"last_login_at": now}
    if new_hash:
        values["password_hash"] = new_hash
    db.execute(update(User).where(User.id == user_id).values(**values))


# ---------------------------------------------------------------- sign-in throttling (A-08)
@dataclass(frozen=True, slots=True)
class FailureWindow:
    count: int
    oldest: datetime | None


def failures_since(
    db: Session, *, since: datetime, email_lower: str | None = None, ip: str | None = None
) -> FailureWindow:
    condition = and_(LoginAttempt.succeeded.is_(False), LoginAttempt.attempted_at > since)
    if email_lower is not None:
        condition = and_(condition, LoginAttempt.email_lower == email_lower)
    if ip is not None:
        condition = and_(condition, LoginAttempt.ip == ip)
    count, oldest = db.execute(
        select(func.count(), func.min(LoginAttempt.attempted_at)).where(condition)
    ).one()
    return FailureWindow(int(count), oldest)


def insert_login_attempt(db: Session, *, email_lower: str, ip: str | None, succeeded: bool) -> None:
    db.execute(insert(LoginAttempt).values(email_lower=email_lower, ip=ip, succeeded=succeeded))


# ---------------------------------------------------------------- workspaces and memberships
def memberships_for_user(db: Session, user_id: uuid.UUID) -> list[tuple[uuid.UUID, str, str]]:
    rows = db.execute(
        select(Workspace.id, Workspace.name, WorkspaceMembership.role)
        .join(WorkspaceMembership, WorkspaceMembership.workspace_id == Workspace.id)
        .where(WorkspaceMembership.user_id == user_id)
        .order_by(Workspace.created_at, Workspace.id)
    ).all()
    return [(ws_id, name, role) for ws_id, name, role in rows]


def workspaces_for_user(
    db: Session, user_id: uuid.UUID, *, after: tuple[datetime, uuid.UUID] | None, limit: int
) -> list[tuple[Workspace, str]]:
    query = (
        select(Workspace, WorkspaceMembership.role)
        .join(WorkspaceMembership, WorkspaceMembership.workspace_id == Workspace.id)
        .where(WorkspaceMembership.user_id == user_id)
        .order_by(Workspace.created_at, Workspace.id)
        .limit(limit + 1)
    )
    if after:
        query = query.where(tuple_(Workspace.created_at, Workspace.id) > after)
    return [(w, r) for w, r in db.execute(query).all()]


def membership_role(db: Session, workspace_id: uuid.UUID, user_id: uuid.UUID) -> str | None:
    role: str | None = db.execute(
        select(WorkspaceMembership.role).where(
            WorkspaceMembership.workspace_id == workspace_id,
            WorkspaceMembership.user_id == user_id,
        )
    ).scalar_one_or_none()
    return role


def workspace(db: Session, workspace_id: uuid.UUID) -> Workspace | None:
    return db.get(Workspace, workspace_id)


def insert_workspace(
    db: Session, *, name: str, description: str | None, secret: bytes, created_by: uuid.UUID
) -> Workspace:
    ws = Workspace(
        name=name, description=description, customer_key_secret=secret, created_by=created_by
    )
    db.add(ws)
    db.flush()
    db.refresh(ws)
    return ws


def insert_membership(
    db: Session, *, workspace_id: uuid.UUID, user_id: uuid.UUID, role: str, added_by: uuid.UUID
) -> bool:
    """False when the user is already a member."""
    inserted = db.execute(
        pg_insert(WorkspaceMembership)
        .values(workspace_id=workspace_id, user_id=user_id, role=role, added_by=added_by)
        .on_conflict_do_nothing(index_elements=["workspace_id", "user_id"])
        .returning(WorkspaceMembership.user_id)
    ).scalar_one_or_none()
    return inserted is not None


def update_workspace(db: Session, workspace_id: uuid.UUID, values: dict[str, Any]) -> None:
    db.execute(update(Workspace).where(Workspace.id == workspace_id).values(**values))


def members(
    db: Session, workspace_id: uuid.UUID, *, after: tuple[datetime, uuid.UUID] | None, limit: int
) -> list[tuple[WorkspaceMembership, User]]:
    query = (
        select(WorkspaceMembership, User)
        .join(User, User.id == WorkspaceMembership.user_id)
        .where(WorkspaceMembership.workspace_id == workspace_id)
        .order_by(WorkspaceMembership.created_at, WorkspaceMembership.user_id)
        .limit(limit + 1)
    )
    if after:
        query = query.where(
            tuple_(WorkspaceMembership.created_at, WorkspaceMembership.user_id) > after
        )
    return [(m, u) for m, u in db.execute(query).all()]


def member(
    db: Session, workspace_id: uuid.UUID, user_id: uuid.UUID
) -> tuple[WorkspaceMembership, User] | None:
    row = db.execute(
        select(WorkspaceMembership, User)
        .join(User, User.id == WorkspaceMembership.user_id)
        .where(
            WorkspaceMembership.workspace_id == workspace_id,
            WorkspaceMembership.user_id == user_id,
        )
    ).one_or_none()
    return (row[0], row[1]) if row else None


def lock_owners(db: Session, workspace_id: uuid.UUID) -> list[uuid.UUID]:
    """Owners of the workspace, locked until the transaction ends (last-Owner rule)."""
    return list(
        db.execute(
            select(WorkspaceMembership.user_id)
            .where(
                WorkspaceMembership.workspace_id == workspace_id,
                WorkspaceMembership.role == "owner",
            )
            .with_for_update()
        ).scalars()
    )


def set_member_role(db: Session, workspace_id: uuid.UUID, user_id: uuid.UUID, role: str) -> None:
    db.execute(
        update(WorkspaceMembership)
        .where(
            WorkspaceMembership.workspace_id == workspace_id,
            WorkspaceMembership.user_id == user_id,
        )
        .values(role=role)
    )


def delete_member(db: Session, workspace_id: uuid.UUID, user_id: uuid.UUID) -> None:
    db.execute(
        delete(WorkspaceMembership).where(
            WorkspaceMembership.workspace_id == workspace_id,
            WorkspaceMembership.user_id == user_id,
        )
    )


# ---------------------------------------------------------------- jobs
def enqueue_job(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    job_type: str,
    payload: dict[str, Any],
    created_by: uuid.UUID,
    idempotency_key: str | None,
) -> uuid.UUID:
    """Insert a job; with an idempotency key, a repeat returns the original job (D09 §1)."""
    job_id = db.execute(
        text(
            "INSERT INTO jobs (workspace_id, job_type, payload, created_by, idempotency_key)"
            " VALUES (:ws, :type, CAST(:payload AS jsonb), :by, :key)"
            " ON CONFLICT (workspace_id, job_type, idempotency_key)"
            " WHERE idempotency_key IS NOT NULL DO NOTHING RETURNING id"
        ),
        {
            "ws": workspace_id,
            "type": job_type,
            "payload": json.dumps(payload),
            "by": created_by,
            "key": idempotency_key,
        },
    ).scalar_one_or_none()
    if job_id is None:  # the key was used before: return that job
        job_id = db.execute(
            select(Job.id).where(
                Job.workspace_id == workspace_id,
                Job.job_type == job_type,
                Job.idempotency_key == idempotency_key,
            )
        ).scalar_one()
    return uuid.UUID(str(job_id))
