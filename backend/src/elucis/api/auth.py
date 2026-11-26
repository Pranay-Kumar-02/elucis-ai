"""Authentication and workspace-access dependencies (D09 §1, D10 §2).

* ``DbDep``: one transaction per request as ``app_api``. It commits when the endpoint
  returns and before the response is sent (``scope="function"``), so a client never sees
  success for a write that did not commit.
* ``PrincipalDep``: a valid session cookie (idle and absolute expiry), plus the CSRF
  header on unsafe methods.
* ``WorkspaceAccess(min_role)``: membership (else 404, so IDs cannot be probed), role
  (else 403, logged), then ``SET LOCAL app.workspace_id`` before any query.
"""

from __future__ import annotations

import ipaddress
import uuid
from collections.abc import Iterator
from datetime import timedelta
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from elucis.api.deps import SettingsDep
from elucis.core.errors import (
    CsrfInvalidError,
    CsrfMissingError,
    ForbiddenRoleError,
    NotAuthenticatedError,
    NotFoundError,
    SessionExpiredError,
)
from elucis.db.engine import session_scope, workspace_scope
from elucis.modules.audit.recorder import record
from elucis.modules.identity import repository as repo
from elucis.modules.identity.context import Principal, WorkspaceContext
from elucis.security import sessions


def get_db(settings: SettingsDep) -> Iterator[Session]:
    with session_scope("api", settings) as db:
        yield db


DbDep = Annotated[Session, Depends(get_db, scope="function")]


def client_ip(request: Request) -> str | None:
    """The peer address if it is an IP address (stored in ``inet`` columns), else None.

    Forwarded headers are not trusted: the API is served directly or through the local
    Vite proxy, never behind a proxy that could vouch for them.
    """
    host = request.client.host if request.client else None
    try:
        return str(ipaddress.ip_address(host)) if host else None
    except ValueError:
        return None


def current_principal(request: Request, db: DbDep, settings: SettingsDep) -> Principal:
    token = request.cookies.get(sessions.SESSION_COOKIE)
    if not token:
        raise NotAuthenticatedError()
    found = repo.session_with_user(db, sessions.token_hash(token))
    if found is None:  # unknown, signed out (AC-AUTH-03) or already purged
        raise NotAuthenticatedError()
    row, user = found
    now = repo.database_now(db)
    window = sessions.SessionWindow(
        idle=timedelta(minutes=settings.session_idle_minutes),
        absolute=timedelta(hours=settings.session_absolute_hours),
    )
    if not user.is_active or window.is_expired(
        created_at=row.created_at, last_seen_at=row.last_seen_at, now=now
    ):
        repo.delete_session(db, row.id)
        db.commit()  # the request fails, but the expired session must still be gone
        raise SessionExpiredError()
    if request.method in sessions.UNSAFE_METHODS:
        presented = request.headers.get(sessions.CSRF_HEADER)
        if not presented:
            raise CsrfMissingError()
        if not sessions.tokens_match(presented, row.csrf_token_hash):
            raise CsrfInvalidError()
    if window.should_touch(row.last_seen_at, now):
        repo.touch_session(db, row.id, now)
    return Principal(user_id=user.id, session_id=row.id, session_token=token, ip=client_ip(request))


PrincipalDep = Annotated[Principal, Depends(current_principal)]


class WorkspaceAccess:
    """Dependency for ``/workspaces/{ws}/...`` routes, with the minimum role of D09 §5."""

    def __init__(self, min_role: str) -> None:
        self.min_role = min_role

    def __call__(
        self, ws: uuid.UUID, request: Request, principal: PrincipalDep, db: DbDep
    ) -> WorkspaceContext:
        role = repo.membership_role(db, ws, principal.user_id)
        if role is None:
            raise NotFoundError()
        workspace_scope(db, ws)
        context = WorkspaceContext(principal=principal, workspace_id=ws, role=role)
        if not context.allows(self.min_role):
            route = getattr(request.scope.get("route"), "path", "")
            record(
                db,
                action="authz.refused",
                outcome="failure",
                workspace_id=ws,
                actor_user_id=principal.user_id,
                details={"required_role": self.min_role, "route": route},
                ip=principal.ip,
            )
            db.commit()  # AC-AUTH-04: the refusal is logged although the request fails
            raise ForbiddenRoleError(
                details=[{"field": "role", "issue": f"requires {self.min_role}"}]
            )
        return context


ViewerDep = Annotated[WorkspaceContext, Depends(WorkspaceAccess("viewer"))]
EditorDep = Annotated[WorkspaceContext, Depends(WorkspaceAccess("editor"))]
OwnerDep = Annotated[WorkspaceContext, Depends(WorkspaceAccess("owner"))]
