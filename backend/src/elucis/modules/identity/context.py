"""Who is asking, and in which workspace: built by the request dependencies (``api/auth``)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

ROLE_RANK = {"viewer": 1, "editor": 2, "owner": 3}


@dataclass(frozen=True, slots=True)
class Principal:
    user_id: uuid.UUID
    session_id: uuid.UUID
    session_token: str
    ip: str | None


@dataclass(frozen=True, slots=True)
class WorkspaceContext:
    """A verified membership; the request transaction is already bound to the workspace."""

    principal: Principal
    workspace_id: uuid.UUID
    role: str

    def allows(self, min_role: str) -> bool:
        return ROLE_RANK[self.role] >= ROLE_RANK[min_role]
