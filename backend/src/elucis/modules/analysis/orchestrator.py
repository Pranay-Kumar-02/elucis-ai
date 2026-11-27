"""The ``analysis`` job: a fixed list of named steps run in order (D03 SVC-10, ADR-06).

Each step is idempotent and commits its own results together with the checkpoint
``{"step": name}``, so a crashed or retried job resumes at the step it was in. Nothing
decides the order at run time: the list below *is* the workflow.

Call chain::

    run_analysis(ctx, settings, gateway_factory)
      _begin(...)                  -> run 'running', started_at
      for name, step in STEPS:     -> skip steps finished before a restart
          step(ctx, run)
      activate(...)                -> report, 'succeeded', workspace's current run

A failed run never replaces the current one: the workspace keeps showing the last
successful run (AIR-22).
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from typing import Any

from sqlalchemy import and_, func, select, update

from elucis.ai.ollama import OllamaClient
from elucis.core.config import Settings
from elucis.db.models import (
    AnalysisRun,
    FeedbackRecord,
    RecordClassification,
    RecordEmbedding,
    Theme,
    ThemeMembership,
    Workspace,
)
from elucis.db.models._common import CURRENT_EMBEDDING_MODEL
from elucis.modules.analysis.classify import classify_step
from elucis.modules.analysis.context import RunContext
from elucis.modules.analysis.embedding import embed_step
from elucis.modules.analysis.gateway import ModelGateway
from elucis.modules.analysis.themes import (
    archive_earlier_themes,
    cluster_step,
    name_step,
    stats_step,
)
from elucis.workers.runtime import JobContext

logger = logging.getLogger(__name__)

Step = Callable[[JobContext, RunContext], None]
STEPS: list[tuple[str, Step]] = [
    ("embed", embed_step),  # SVC-08
    ("classify", classify_step),  # SVC-09, CP-02
    ("cluster", cluster_step),  # SVC-11
    ("stats", stats_step),  # SVC-10 statistics (before naming, so citations have a row)
    ("name", name_step),  # CP-03
]
FINAL = frozenset({"succeeded", "failed", "cancelled"})


def default_gateway(settings: Settings) -> ModelGateway:
    return OllamaClient(settings)


def run_analysis(
    ctx: JobContext,
    settings: Settings,
    gateway_factory: Callable[[Settings], ModelGateway] = default_gateway,
) -> str:
    run_id = uuid.UUID(str(ctx.job.payload["analysis_run_id"]))
    gateway = gateway_factory(settings)
    try:
        if not _begin(ctx, run_id):
            return "succeeded"  # already finished, or removed with its workspace
        run = RunContext(run_id, gateway, settings.ollama_chat_model, _product(ctx))
        names = [name for name, _ in STEPS]
        resume_at = (
            names.index(ctx.job.cursor["step"]) if ctx.job.cursor.get("step") in names else 0
        )
        for index, (name, step) in enumerate(STEPS[resume_at:], start=resume_at):
            logger.info("analysis step", extra={"step": name, "analysis_run_id": str(run_id)})
            step(ctx, run)
            following = names[index + 1] if index + 1 < len(names) else "activate"
            with ctx.step() as (_db, queue):  # where a retry resumes
                queue.checkpoint(ctx.job, {"step": following}, {"step": following})
        activate(ctx, run_id)
        return "succeeded"
    except Exception as exc:
        if ctx.job.attempts >= ctx.job.max_attempts:
            _fail(ctx, run_id, f"The analysis stopped: {type(exc).__name__}.")
        raise
    finally:
        gateway.close()


def _product(ctx: JobContext) -> str:
    """The workspace's product profile, as context for naming (CP-03, CP-04)."""
    with ctx.step() as (db, _queue):
        ws = db.execute(
            select(
                Workspace.product_name, Workspace.product_description, Workspace.target_users
            ).where(Workspace.id == ctx.job.workspace_id)
        ).one_or_none()
    if ws is None:
        return ""
    parts = [
        ws.product_name,
        ws.product_description,
        f"Users: {ws.target_users}" if ws.target_users else None,
    ]
    return " - ".join(p for p in parts if p)


def _begin(ctx: JobContext, run_id: uuid.UUID) -> bool:
    with ctx.step() as (db, _queue):
        status = db.execute(
            select(AnalysisRun.status).where(
                AnalysisRun.workspace_id == ctx.job.workspace_id, AnalysisRun.id == run_id
            )
        ).scalar_one_or_none()
        if status is None or status in FINAL:
            return False
        db.execute(
            update(AnalysisRun)
            .where(AnalysisRun.workspace_id == ctx.job.workspace_id, AnalysisRun.id == run_id)
            .values(status="running", started_at=func.coalesce(AnalysisRun.started_at, func.now()))
        )
    return True


def run_report(db: Any, ws: uuid.UUID, run_id: uuid.UUID) -> dict[str, Any]:
    """Outcome counts (D06 §10.2), from the database."""
    fr, emb, rc = FeedbackRecord, RecordEmbedding, RecordClassification
    eligible = db.execute(
        select(func.count()).where(fr.workspace_id == ws, fr.analysable.is_(True))
    ).scalar_one()
    embedded = db.execute(
        select(func.count())
        .select_from(fr)
        .join(emb, and_(emb.workspace_id == fr.workspace_id, emb.record_id == fr.id))
        .where(
            fr.workspace_id == ws, fr.analysable.is_(True), emb.model_id == CURRENT_EMBEDDING_MODEL
        )
    ).scalar_one()
    statuses = dict(
        db.execute(
            select(rc.status, func.count())
            .where(rc.workspace_id == ws, rc.analysis_run_id == run_id)
            .group_by(rc.status)
        ).all()
    )
    return {
        "eligible": int(eligible),
        "embedded": int(embedded),
        "embedding_failed": int(statuses.get("embedding_failed", 0)),
        "classified": int(statuses.get("classified", 0)),
        "unclassified": int(statuses.get("unclassified", 0)),
        "themes": int(
            db.execute(
                select(func.count()).where(Theme.workspace_id == ws, Theme.first_run_id == run_id)
            ).scalar_one()
        ),
        "assigned": int(
            db.execute(
                select(func.count()).where(
                    ThemeMembership.workspace_id == ws, ThemeMembership.analysis_run_id == run_id
                )
            ).scalar_one()
        ),
        "categories": {
            str(c): int(n)
            for c, n in db.execute(
                select(rc.category, func.count())
                .where(
                    rc.workspace_id == ws, rc.analysis_run_id == run_id, rc.status == "classified"
                )
                .group_by(rc.category)
            ).all()
        },
        "steps": [name for name, _ in STEPS],
    }


def activate(ctx: JobContext, run_id: uuid.UUID) -> None:
    """One transaction: report, status and the workspace's current run (SVC-10 step 12)."""
    ws = ctx.job.workspace_id
    with ctx.step() as (db, _queue):
        report = run_report(db, ws, run_id)
        db.execute(
            update(AnalysisRun)
            .where(AnalysisRun.workspace_id == ws, AnalysisRun.id == run_id)
            .values(status="succeeded", report=report, finished_at=func.now())
        )
        archive_earlier_themes(db, ws, run_id)
        db.execute(
            update(Workspace).where(Workspace.id == ws).values(current_analysis_run_id=run_id)
        )
    logger.info("analysis run succeeded", extra={"analysis_run_id": str(run_id)})


def _fail(ctx: JobContext, run_id: uuid.UUID, message: str) -> None:
    try:
        with ctx.step() as (db, _queue):
            db.execute(
                update(AnalysisRun)
                .where(AnalysisRun.workspace_id == ctx.job.workspace_id, AnalysisRun.id == run_id)
                .values(status="failed", report={"error": message}, finished_at=func.now())
            )
    except Exception:
        logger.exception("could not mark the analysis run as failed")
