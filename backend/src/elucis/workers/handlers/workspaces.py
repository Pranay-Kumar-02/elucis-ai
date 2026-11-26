"""``delete_workspace`` job (API-09, FR-AUTH-11, IMP-24).

One transaction: delete the workspace (the foreign-key cascade removes every tenant row,
including its audit history and this job's own row), then record ``workspace.deleted``
with no workspace, so the event outlives the data it describes (A-21). The details hold
only the workspace name, never customer text. Running it again is a no-op.
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import delete, select

from elucis.db.models import Workspace
from elucis.modules.audit.recorder import record
from elucis.workers.runtime import JobContext

logger = logging.getLogger(__name__)


def delete_workspace(ctx: JobContext) -> str:
    workspace_id = ctx.job.workspace_id
    requested_by = uuid.UUID(str(ctx.job.payload["requested_by"]))
    with ctx.step() as (db, _queue):
        name = db.execute(
            select(Workspace.name).where(Workspace.id == workspace_id)
        ).scalar_one_or_none()
        if name is None:
            logger.info("workspace already deleted", extra={"workspace_id": str(workspace_id)})
            return "succeeded"
        db.execute(delete(Workspace).where(Workspace.id == workspace_id))
        record(
            db,
            action="workspace.deleted",
            workspace_id=None,
            actor_user_id=requested_by,
            target_type="workspace",
            target_id=workspace_id,
            details={"workspace_name": name},
        )
    logger.info("workspace deleted", extra={"workspace_id": str(workspace_id)})
    return "succeeded"
