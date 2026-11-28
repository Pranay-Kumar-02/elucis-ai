"""API-01 to API-13: authentication, workspaces and members (D09 §3.1)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Header, Request, Response, status

from elucis.api.auth import DbDep, OwnerDep, PrincipalDep, ViewerDep, client_ip
from elucis.api.deps import SettingsDep
from elucis.api.pagination import DEFAULT_LIMIT, CursorQuery, LimitQuery, Page
from elucis.modules.identity import service
from elucis.modules.identity.schemas import (
    DeleteWorkspaceIn,
    JobRef,
    LoginIn,
    MemberIn,
    MemberOut,
    MemberPatch,
    MeOut,
    RegisterIn,
    UserOut,
    WorkspaceIn,
    WorkspaceOut,
    WorkspacePatch,
)
from elucis.security.sessions import SESSION_COOKIE

auth = APIRouter(prefix="/auth", tags=["authentication"])
workspaces = APIRouter(prefix="/workspaces", tags=["workspaces"])

COOKIE_PATH = "/api"


# ---------------------------------------------------------------- authentication
@auth.post("/register", status_code=status.HTTP_201_CREATED, summary="API-01 Register")
def register(data: RegisterIn, db: DbDep) -> UserOut:
    return service.register(db, data)


@auth.post("/login", summary="API-02 Sign in; sets the session cookie")
def login(
    data: LoginIn, request: Request, response: Response, db: DbDep, settings: SettingsDep
) -> MeOut:
    token, me = service.login(
        db,
        settings,
        data,
        ip=client_ip(request),
        user_agent=request.headers.get("user-agent"),
        previous_token=request.cookies.get(SESSION_COOKIE),
    )
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=settings.session_absolute_hours * 3600,
        path=COOKIE_PATH,
        secure=settings.cookie_secure,
        httponly=True,
        samesite="lax",
    )
    return me


@auth.post("/logout", status_code=status.HTTP_204_NO_CONTENT, summary="API-03 Sign out")
def logout(principal: PrincipalDep, response: Response, db: DbDep) -> None:
    service.logout(db, principal)
    response.delete_cookie(SESSION_COOKIE, path=COOKIE_PATH, httponly=True, samesite="lax")


@auth.get("/me", summary="API-04 Current user, memberships and CSRF token")
def me(principal: PrincipalDep, db: DbDep, settings: SettingsDep) -> MeOut:
    return service.me(db, settings, principal)


# ---------------------------------------------------------------- workspaces
@workspaces.post("", status_code=status.HTTP_201_CREATED, summary="API-05 Create workspace")
def create_workspace(
    data: WorkspaceIn, principal: PrincipalDep, db: DbDep, settings: SettingsDep
) -> WorkspaceOut:
    return service.create_workspace(db, settings, principal, data)


@workspaces.get("", summary="API-06 List my workspaces")
def list_workspaces(
    principal: PrincipalDep,
    db: DbDep,
    settings: SettingsDep,
    limit: LimitQuery = DEFAULT_LIMIT,
    cursor: CursorQuery = None,
) -> Page[WorkspaceOut]:
    return service.list_workspaces(db, settings, principal, limit=limit, cursor=cursor)


@workspaces.get("/{ws}", summary="API-07 Workspace and product profile")
def get_workspace(ctx: ViewerDep, db: DbDep, settings: SettingsDep) -> WorkspaceOut:
    return service.get_workspace(db, settings, ctx)


@workspaces.patch("/{ws}", summary="API-08 Edit workspace and product profile")
def update_workspace(
    data: WorkspacePatch, ctx: OwnerDep, db: DbDep, settings: SettingsDep
) -> WorkspaceOut:
    return service.update_workspace(db, settings, ctx, data)


@workspaces.delete("/{ws}", status_code=status.HTTP_202_ACCEPTED, summary="API-09 Delete workspace")
def delete_workspace(
    data: DeleteWorkspaceIn,
    ctx: OwnerDep,
    db: DbDep,
    idempotency_key: Annotated[str | None, Header(max_length=64)] = None,
) -> JobRef:
    return service.request_deletion(db, ctx, data, idempotency_key)


# ---------------------------------------------------------------- members
@workspaces.get("/{ws}/members", summary="API-10 List members")
def list_members(
    ctx: ViewerDep, db: DbDep, limit: LimitQuery = DEFAULT_LIMIT, cursor: CursorQuery = None
) -> Page[MemberOut]:
    return service.list_members(db, ctx, limit=limit, cursor=cursor)


@workspaces.post("/{ws}/members", status_code=status.HTTP_201_CREATED, summary="API-11 Add member")
def add_member(data: MemberIn, ctx: OwnerDep, db: DbDep) -> MemberOut:
    return service.add_member(db, ctx, data)


@workspaces.patch("/{ws}/members/{user_id}", summary="API-12 Change role")
def change_role(user_id: uuid.UUID, data: MemberPatch, ctx: OwnerDep, db: DbDep) -> MemberOut:
    return service.change_role(db, ctx, user_id, data)


@workspaces.delete(
    "/{ws}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="API-13 Remove member",
)
def remove_member(user_id: uuid.UUID, ctx: OwnerDep, db: DbDep) -> None:
    service.remove_member(db, ctx, user_id)
