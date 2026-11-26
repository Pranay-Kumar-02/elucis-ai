"""SVC-01 Authentication and Workspace Service (D03): rules, not SQL.

Sign-in follows D10 §2 and A-07/A-08; workspace access follows D09 §1 (non-members get 404,
insufficient roles 403); every change in SEC-14 is written to the audit log.
"""

from __future__ import annotations

import math
import os
import uuid
from datetime import timedelta
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from elucis.api.pagination import Page, decode_cursor, encode_cursor
from elucis.core.config import Settings
from elucis.core.errors import (
    ConflictError,
    EmailTakenError,
    EncryptionUnavailableError,
    InvalidCredentialsError,
    NotFoundError,
    TooManyAttemptsError,
    ValidationFailedError,
)
from elucis.db.engine import workspace_scope
from elucis.db.models import User, Workspace, WorkspaceMembership
from elucis.modules.audit.recorder import record
from elucis.modules.identity import repository as repo
from elucis.modules.identity.context import Principal, WorkspaceContext
from elucis.modules.identity.schemas import (
    DeleteWorkspaceIn,
    JobRef,
    LoginIn,
    MemberIn,
    MemberOut,
    MemberPatch,
    MembershipOut,
    MeOut,
    RegisterIn,
    UserOut,
    WorkspaceIn,
    WorkspaceOut,
    WorkspacePatch,
)
from elucis.security import crypto, sessions
from elucis.security.passwords import (
    check_password_policy,
    hash_password,
    needs_rehash,
    verify_against_nothing,
    verify_password,
)

THROTTLE_WINDOW = timedelta(minutes=15)  # A-08
MAX_FAILURES_PER_ACCOUNT = 5  # A-08
MAX_FAILURES_PER_IP = 20  # D10 asks for a per-IP limit without a number (IMP-28)


def _window(settings: Settings) -> sessions.SessionWindow:
    return sessions.SessionWindow(
        idle=timedelta(minutes=settings.session_idle_minutes),
        absolute=timedelta(hours=settings.session_absolute_hours),
    )


def _signing_secret(settings: Settings) -> str:
    if settings.session_secret is None:
        raise EncryptionUnavailableError("Session signing is not configured (SESSION_SECRET).")
    return settings.session_secret.get_secret_value()


# ---------------------------------------------------------------- accounts
def register(db: Session, data: RegisterIn) -> UserOut:
    if problems := check_password_policy(data.password):
        raise ValidationFailedError(
            "The password " + "; ".join(problems) + ".",
            details=[{"field": "password", "issue": p} for p in problems],
        )
    if repo.user_by_email(db, data.email):
        raise EmailTakenError()
    try:
        with db.begin_nested():
            user = repo.insert_user(
                db,
                email=data.email,
                password_hash=hash_password(data.password),
                display_name=data.display_name or None,
            )
    except IntegrityError as exc:  # registered concurrently
        raise EmailTakenError() from exc
    return UserOut(
        id=user.id, email=user.email, display_name=user.display_name, created_at=user.created_at
    )


def login(
    db: Session,
    settings: Settings,
    data: LoginIn,
    *,
    ip: str | None,
    user_agent: str | None,
    previous_token: str | None,
) -> tuple[str, MeOut]:
    """Returns the new session token (for the cookie) and the signed-in user's ``MeOut``.

    Failed attempts are committed before the error is raised, so they count even though the
    request ends in an error.
    """
    email_lower = data.email.strip().lower()
    now = repo.database_now(db)
    since = now - THROTTLE_WINDOW
    account = repo.failures_since(db, since=since, email_lower=email_lower)
    by_ip = repo.failures_since(db, since=since, ip=ip) if ip else repo.FailureWindow(0, None)
    blocked = [
        w
        for w, limit in ((account, MAX_FAILURES_PER_ACCOUNT), (by_ip, MAX_FAILURES_PER_IP))
        if w.count >= limit and w.oldest is not None
    ]
    user = repo.user_by_email(db, email_lower)
    if blocked:
        release = max(w.oldest for w in blocked if w.oldest) + THROTTLE_WINDOW
        retry_after = max(1, math.ceil((release - now).total_seconds()))
        record(
            db,
            action="auth.login_failed",
            outcome="failure",
            workspace_id=None,
            actor_user_id=user.id if user else None,
            details={"reason": "throttled"},
            ip=ip,
        )
        db.commit()
        raise TooManyAttemptsError(
            details=[{"field": "retry_after_s", "issue": str(retry_after)}],
            headers={"Retry-After": str(retry_after)},
        )

    if user is None:
        verify_against_nothing(data.password)
    valid = (
        user is not None and user.is_active and verify_password(user.password_hash, data.password)
    )
    repo.insert_login_attempt(db, email_lower=email_lower, ip=ip, succeeded=valid)
    if not valid or user is None:
        record(
            db,
            action="auth.login_failed",
            outcome="failure",
            workspace_id=None,
            actor_user_id=user.id if user else None,
            details={"reason": "invalid_credentials"},
            ip=ip,
        )
        db.commit()
        raise InvalidCredentialsError()

    if previous_token:  # rotate: an old session in this browser ends at sign-in
        repo.delete_session_by_token(db, sessions.token_hash(previous_token))
    token = sessions.new_token()
    csrf = sessions.csrf_token_for(token, _signing_secret(settings))
    repo.insert_session(
        db,
        user_id=user.id,
        token_hash=sessions.token_hash(token),
        csrf_token_hash=sessions.token_hash(csrf),
        expires_at=_window(settings).expires_at(now),
        ip=ip,
        user_agent=(user_agent or "")[:500] or None,
    )
    new_hash = hash_password(data.password) if needs_rehash(user.password_hash) else None
    repo.update_user_after_login(db, user.id, now, new_hash)
    # The user's own expired sessions go now; the global purges (D07 section 8) are the
    # worker's maintenance step, because only app_worker may delete login attempts.
    repo.delete_expired_sessions(db, user.id, now, _window(settings).idle)
    record(db, action="auth.login", workspace_id=None, actor_user_id=user.id, ip=ip)
    principal = Principal(user_id=user.id, session_id=uuid.uuid4(), session_token=token, ip=ip)
    return token, me(db, settings, principal)


def logout(db: Session, principal: Principal) -> None:
    repo.delete_session(db, principal.session_id)


def me(db: Session, settings: Settings, principal: Principal) -> MeOut:
    user = db.get(User, principal.user_id)
    if user is None:  # deleted between steps; the session cascade removes it too
        raise NotFoundError()
    memberships = [
        MembershipOut(workspace_id=ws_id, workspace_name=name, role=role)  # type: ignore[arg-type]
        for ws_id, name, role in repo.memberships_for_user(db, principal.user_id)
    ]
    return MeOut(
        user=UserOut(
            id=user.id, email=user.email, display_name=user.display_name, created_at=user.created_at
        ),
        memberships=memberships,
        csrf_token=sessions.csrf_token_for(principal.session_token, _signing_secret(settings)),
    )


# ---------------------------------------------------------------- workspaces
def _workspace_out(ws: Workspace, role: str) -> WorkspaceOut:
    return WorkspaceOut(
        id=ws.id,
        name=ws.name,
        description=ws.description,
        product_name=ws.product_name,
        product_description=ws.product_description,
        target_users=ws.target_users,
        glossary=ws.glossary,
        role=role,  # type: ignore[arg-type]
        created_at=ws.created_at,
    )


def create_workspace(
    db: Session, settings: Settings, principal: Principal, data: WorkspaceIn
) -> WorkspaceOut:
    """Workspace and Owner membership in one transaction (D03 SVC-01)."""
    secret = crypto.encrypt(settings, os.urandom(32))  # HMAC key for customer IDs (DR-23)
    ws = repo.insert_workspace(
        db,
        name=data.name,
        description=data.description,
        secret=secret,
        created_by=principal.user_id,
    )
    repo.insert_membership(
        db,
        workspace_id=ws.id,
        user_id=principal.user_id,
        role="owner",
        added_by=principal.user_id,
    )
    workspace_scope(db, ws.id)
    record(
        db,
        action="workspace.created",
        workspace_id=ws.id,
        actor_user_id=principal.user_id,
        target_type="workspace",
        target_id=ws.id,
        ip=principal.ip,
    )
    return _workspace_out(ws, "owner")


def list_workspaces(
    db: Session, principal: Principal, *, limit: int, cursor: str | None
) -> Page[WorkspaceOut]:
    rows = repo.workspaces_for_user(db, principal.user_id, after=decode_cursor(cursor), limit=limit)
    page, more = rows[:limit], len(rows) > limit
    return Page(
        items=[_workspace_out(ws, role) for ws, role in page],
        next_cursor=encode_cursor(page[-1][0].created_at, page[-1][0].id) if more else None,
    )


def get_workspace(db: Session, ctx: WorkspaceContext) -> WorkspaceOut:
    ws = repo.workspace(db, ctx.workspace_id)
    if ws is None:
        raise NotFoundError()
    return _workspace_out(ws, ctx.role)


def update_workspace(db: Session, ctx: WorkspaceContext, data: WorkspacePatch) -> WorkspaceOut:
    values: dict[str, Any] = data.model_dump(exclude_unset=True)
    if "name" in values and values["name"] is None:
        raise ValidationFailedError(details=[{"field": "name", "issue": "required"}])
    if values.get("glossary") is None and "glossary" in values:
        values["glossary"] = {}
    if values:
        repo.update_workspace(db, ctx.workspace_id, values)
        db.expire_all()
    return get_workspace(db, ctx)


def request_deletion(
    db: Session, ctx: WorkspaceContext, data: DeleteWorkspaceIn, idempotency_key: str | None
) -> JobRef:
    """Queue ``delete_workspace`` (API-09, FR-AUTH-11). The worker deletes the workspace and
    writes ``workspace.deleted`` (IMP-24)."""
    ws = repo.workspace(db, ctx.workspace_id)
    if ws is None:
        raise NotFoundError()
    if data.confirm_name != ws.name:
        raise ValidationFailedError(
            "Type the workspace name exactly to confirm deletion.",
            details=[{"field": "confirm_name", "issue": "mismatch"}],
        )
    if idempotency_key is not None:
        try:
            idempotency_key = str(uuid.UUID(idempotency_key))
        except ValueError as exc:
            raise ValidationFailedError(
                details=[{"field": "Idempotency-Key", "issue": "must be a UUID"}]
            ) from exc
    job_id = repo.enqueue_job(
        db,
        workspace_id=ws.id,
        job_type="delete_workspace",
        payload={"workspace_id": str(ws.id), "requested_by": str(ctx.principal.user_id)},
        created_by=ctx.principal.user_id,
        idempotency_key=idempotency_key,
    )
    record(
        db,
        action="workspace.deletion_requested",
        workspace_id=ws.id,
        actor_user_id=ctx.principal.user_id,
        target_type="workspace",
        target_id=ws.id,
        details={"job_id": str(job_id)},
        ip=ctx.principal.ip,
    )
    return JobRef(job_id=job_id, resource_id=ws.id)


# ---------------------------------------------------------------- members
def _member_out(row: tuple[WorkspaceMembership, User]) -> MemberOut:
    membership, user = row
    return MemberOut(
        user_id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=membership.role,  # type: ignore[arg-type]
        added_at=membership.created_at,
    )


def list_members(
    db: Session, ctx: WorkspaceContext, *, limit: int, cursor: str | None
) -> Page[MemberOut]:
    rows = repo.members(db, ctx.workspace_id, after=decode_cursor(cursor), limit=limit)
    page, more = rows[:limit], len(rows) > limit
    last = page[-1][0] if page else None
    return Page(
        items=[_member_out(r) for r in page],
        next_cursor=encode_cursor(last.created_at, last.user_id) if more and last else None,
    )


def _member(db: Session, ctx: WorkspaceContext, user_id: uuid.UUID) -> MemberOut:
    row = repo.member(db, ctx.workspace_id, user_id)
    if row is None:
        raise NotFoundError()
    return _member_out(row)


def add_member(db: Session, ctx: WorkspaceContext, data: MemberIn) -> MemberOut:
    user = repo.user_by_email(db, data.email)
    if user is None:
        raise NotFoundError("No registered user has this email.")
    if not repo.insert_membership(
        db,
        workspace_id=ctx.workspace_id,
        user_id=user.id,
        role=data.role,
        added_by=ctx.principal.user_id,
    ):
        raise ConflictError("This user is already a member of the workspace.")
    record(
        db,
        action="member.added",
        workspace_id=ctx.workspace_id,
        actor_user_id=ctx.principal.user_id,
        target_type="user",
        target_id=user.id,
        details={"role": data.role},
        ip=ctx.principal.ip,
    )
    return _member(db, ctx, user.id)


def _ensure_another_owner(owners: list[uuid.UUID], user_id: uuid.UUID) -> None:
    if owners == [user_id]:
        raise ConflictError("A workspace must keep at least one Owner.")


def change_role(
    db: Session, ctx: WorkspaceContext, user_id: uuid.UUID, data: MemberPatch
) -> MemberOut:
    previous = repo.membership_role(db, ctx.workspace_id, user_id)
    if previous is None:
        raise NotFoundError()
    if previous == "owner" and data.role != "owner":
        _ensure_another_owner(repo.lock_owners(db, ctx.workspace_id), user_id)
    repo.set_member_role(db, ctx.workspace_id, user_id, data.role)
    record(
        db,
        action="member.role_changed",
        workspace_id=ctx.workspace_id,
        actor_user_id=ctx.principal.user_id,
        target_type="user",
        target_id=user_id,
        details={"role": data.role, "previous_role": previous},
        ip=ctx.principal.ip,
    )
    return _member(db, ctx, user_id)


def remove_member(db: Session, ctx: WorkspaceContext, user_id: uuid.UUID) -> None:
    previous = repo.membership_role(db, ctx.workspace_id, user_id)
    if previous is None:
        raise NotFoundError()
    if previous == "owner":
        _ensure_another_owner(repo.lock_owners(db, ctx.workspace_id), user_id)
    repo.delete_member(db, ctx.workspace_id, user_id)
    record(
        db,
        action="member.removed",
        workspace_id=ctx.workspace_id,
        actor_user_id=ctx.principal.user_id,
        target_type="user",
        target_id=user_id,
        details={"previous_role": previous},
        ip=ctx.principal.ip,
    )
