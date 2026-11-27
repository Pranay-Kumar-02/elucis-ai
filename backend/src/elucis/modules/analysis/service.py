"""What API-31 and API-32 do: start an analysis run and report on runs (D09 §3.4)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from elucis.ai.ollama import OllamaClient
from elucis.core.config import Settings
from elucis.core.errors import (
    ModelUnavailableError,
    NoAnalysableRecordsError,
    NotFoundError,
    RunInProgressError,
    ValidationFailedError,
)
from elucis.db.models import AnalysisRun, FeedbackRecord, Job, Workspace
from elucis.db.models._common import CURRENT_EMBEDDING_MODEL
from elucis.modules.analysis.config import config_hash, run_config
from elucis.modules.analysis.schemas import AnalysisStatusOut, RunOut
from elucis.modules.audit.recorder import record
from elucis.modules.identity.context import WorkspaceContext
from elucis.modules.identity.repository import enqueue_job
from elucis.modules.identity.schemas import JobRef

ACTIVE = ("queued", "running")


def required_models(settings: Settings) -> list[str]:
    return [CURRENT_EMBEDDING_MODEL, settings.ollama_chat_model]


def check_models(settings: Settings) -> None:
    """503 before queueing a run the worker could not complete (UI-05, AIR-22)."""
    with OllamaClient(settings, timeout_s=10) as client:
        missing = [m for m in required_models(settings) if not client.has_model(m)]
    if missing:
        raise ModelUnavailableError(f"The model {missing[0]} is not available in Ollama.")


def _analysable(db: Session, ws: uuid.UUID) -> Any:
    return select(func.count()).where(
        FeedbackRecord.workspace_id == ws, FeedbackRecord.analysable.is_(True)
    )


def start_run(
    db: Session, settings: Settings, ctx: WorkspaceContext, idempotency_key: str | None
) -> JobRef:
    key = None
    if idempotency_key is not None:
        try:
            key = str(uuid.UUID(idempotency_key))
        except ValueError as exc:
            raise ValidationFailedError(
                details=[{"field": "Idempotency-Key", "issue": "must be a UUID"}]
            ) from exc
        repeat = db.execute(
            select(AnalysisRun.id, Job.id)
            .join(
                Job,
                and_(Job.workspace_id == AnalysisRun.workspace_id, Job.id == AnalysisRun.job_id),
            )
            .where(
                AnalysisRun.workspace_id == ctx.workspace_id,
                Job.job_type == "analysis",
                Job.idempotency_key == key,
            )
        ).one_or_none()
        if repeat is not None:
            return JobRef(job_id=repeat[1], resource_id=repeat[0])
    running = db.execute(
        select(AnalysisRun.id).where(
            AnalysisRun.workspace_id == ctx.workspace_id, AnalysisRun.status.in_(ACTIVE)
        )
    ).first()
    if running is not None:
        raise RunInProgressError()
    if db.execute(_analysable(db, ctx.workspace_id)).scalar_one() == 0:
        raise NoAnalysableRecordsError()
    check_models(settings)

    config = run_config(settings)
    previous = db.execute(
        select(Workspace.current_analysis_run_id).where(Workspace.id == ctx.workspace_id)
    ).scalar_one()
    run_id = uuid.uuid4()
    job_id = enqueue_job(
        db,
        workspace_id=ctx.workspace_id,
        job_type="analysis",
        payload={"analysis_run_id": str(run_id)},
        created_by=ctx.principal.user_id,
        idempotency_key=key,
    )
    db.add(
        AnalysisRun(
            id=run_id,
            workspace_id=ctx.workspace_id,
            config=config,
            config_hash=config_hash(config),
            embedding_model_id=CURRENT_EMBEDDING_MODEL,
            previous_run_id=previous,
            job_id=job_id,
            triggered_by=ctx.principal.user_id,
        )
    )
    db.flush()
    record(
        db,
        action="analysis.started",
        workspace_id=ctx.workspace_id,
        actor_user_id=ctx.principal.user_id,
        target_type="analysis_run",
        target_id=run_id,
        details={"job_id": str(job_id)},
        ip=ctx.principal.ip,
    )
    return JobRef(job_id=job_id, resource_id=run_id)


# ---------------------------------------------------------------- reading runs
def _query(ws: uuid.UUID) -> Any:
    return (
        select(AnalysisRun, Job.cursor, Job.progress, Job.error)
        .outerjoin(
            Job, and_(Job.workspace_id == AnalysisRun.workspace_id, Job.id == AnalysisRun.job_id)
        )
        .where(AnalysisRun.workspace_id == ws)
    )


def _current_id(db: Session, ws: uuid.UUID) -> uuid.UUID | None:
    return db.execute(
        select(Workspace.current_analysis_run_id).where(Workspace.id == ws)
    ).scalar_one_or_none()


def _out(row: Any, current: uuid.UUID | None) -> RunOut:
    run, cursor, progress, error = row
    active = run.status in ACTIVE
    failure = (run.report or {}).get("error") if run.status == "failed" else None
    return RunOut(
        id=run.id,
        status=run.status,
        is_current=run.id == current,
        created_at=run.created_at,
        started_at=run.started_at,
        finished_at=run.finished_at,
        job_id=run.job_id,
        step=(cursor or {}).get("step") if active else None,
        progress=progress if active and progress else None,
        config=run.config,
        report=run.report,
        error=failure or (error if run.status == "failed" else None),
    )


def list_runs(db: Session, ctx: WorkspaceContext, *, limit: int) -> list[RunOut]:
    current = _current_id(db, ctx.workspace_id)
    rows = db.execute(
        _query(ctx.workspace_id).order_by(AnalysisRun.created_at.desc()).limit(limit)
    ).all()
    return [_out(r, current) for r in rows]


def get_run(db: Session, ctx: WorkspaceContext, run_id: uuid.UUID) -> RunOut:
    row = db.execute(_query(ctx.workspace_id).where(AnalysisRun.id == run_id)).one_or_none()
    if row is None:
        raise NotFoundError("The analysis run was not found.")
    return _out(row, _current_id(db, ctx.workspace_id))


def analysis_status(db: Session, ctx: WorkspaceContext) -> AnalysisStatusOut:
    ws = ctx.workspace_id
    current = _current_id(db, ws)
    runs = list_runs(db, ctx, limit=1)
    current_run = get_run(db, ctx, current) if current else None
    since = 0
    total = int(db.execute(_analysable(db, ws)).scalar_one())
    if current_run is not None and current_run.started_at is not None:
        since = int(
            db.execute(
                _analysable(db, ws).where(FeedbackRecord.created_at > current_run.started_at)
            ).scalar_one()
        )
    else:
        since = total
    return AnalysisStatusOut(
        analysable_records=total,
        records_since_last_run=since,
        current_run=current_run,
        latest_run=runs[0] if runs else None,
    )
