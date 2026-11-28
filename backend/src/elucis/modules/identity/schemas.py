"""Request and response shapes for SVC-01 (D09 §4: RegisterIn, LoginIn, MeOut, WorkspaceIn,
WorkspacePatch, JobRef)."""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints

from elucis.security.passwords import MAX_PASSWORD_LENGTH

Role = Literal["owner", "editor", "viewer"]

# A deliberately simple shape check; deliverability is not verified (no email-validator
# dependency). Uniqueness is case-insensitive in the database (D07 users).
_EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")


def _email(value: str) -> str:
    value = value.strip()
    if not _EMAIL.fullmatch(value):
        raise ValueError("must be an email address such as name@example.com")
    return value


Email = Annotated[str, StringConstraints(max_length=254), AfterValidator(_email)]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RegisterIn(StrictModel):
    email: Email
    # Length and the common-password list are checked by the service, so the error names the
    # rule instead of a generic length message.
    password: str = Field(max_length=MAX_PASSWORD_LENGTH)
    display_name: Annotated[str, StringConstraints(strip_whitespace=True, max_length=80)] | None = (
        None
    )


class LoginIn(StrictModel):
    email: Annotated[str, StringConstraints(strip_whitespace=True, max_length=254)]
    password: str = Field(max_length=1024)  # anything longer cannot be a valid password


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str | None
    created_at: datetime


class MembershipOut(BaseModel):
    workspace_id: uuid.UUID
    workspace_name: str
    role: Role


class MeOut(BaseModel):
    user: UserOut
    memberships: list[MembershipOut]
    csrf_token: str


class WorkspaceIn(StrictModel):
    name: Name
    description: Annotated[str, StringConstraints(max_length=500)] | None = None


GlossaryTerm = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
GlossaryDefinition = Annotated[str, StringConstraints(max_length=500)]


class WorkspacePatch(StrictModel):
    """Only the fields sent are changed (D09 API-08); ``null`` clears an optional field."""

    name: Name | None = None
    description: Annotated[str, StringConstraints(max_length=500)] | None = None
    product_name: Annotated[str, StringConstraints(max_length=200)] | None = None
    product_description: Annotated[str, StringConstraints(max_length=2000)] | None = None
    target_users: Annotated[str, StringConstraints(max_length=500)] | None = None
    glossary: Annotated[dict[GlossaryTerm, GlossaryDefinition], Field(max_length=200)] | None = None
    gemini_fallback: bool | None = None  # IMP-38; refused without GEMINI_API_KEY


class WorkspaceOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    product_name: str | None
    product_description: str | None
    target_users: str | None
    glossary: dict[str, str]
    role: Role  # the caller's role in this workspace
    created_at: datetime
    gemini_fallback: bool = Field(
        default=False, description="Owner's switch: Gemini as a backup for chat calls (IMP-38)"
    )
    gemini_available: bool = Field(
        default=False, description="GEMINI_API_KEY is configured on this server"
    )


class DeleteWorkspaceIn(StrictModel):
    confirm_name: str = Field(max_length=200)


class JobRef(BaseModel):
    job_id: uuid.UUID
    resource_id: uuid.UUID
    status: Literal["queued"] = "queued"


class MemberIn(StrictModel):
    email: Annotated[str, StringConstraints(strip_whitespace=True, max_length=254)]
    role: Role = "viewer"  # SEC-21


class MemberPatch(StrictModel):
    role: Role


class MemberOut(BaseModel):
    user_id: uuid.UUID
    email: str
    display_name: str | None
    role: Role
    added_at: datetime
