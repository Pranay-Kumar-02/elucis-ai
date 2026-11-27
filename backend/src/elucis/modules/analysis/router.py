"""API-31 and API-32: analysis runs (D09 §3.4), plus the dashboard's run status."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Header, Query, status

from elucis.api.auth import DbDep, EditorDep, ViewerDep
from elucis.api.deps import SettingsDep
from elucis.modules.analysis import service
from elucis.modules.analysis.schemas import AnalysisStatusOut, RunIn, RunOut
from elucis.modules.identity.schemas import JobRef

router = APIRouter(prefix="/workspaces/{ws}", tags=["analysis"])


@router.post("/analysis-runs", status_code=status.HTTP_202_ACCEPTED, summary="API-31 Run analysis")
def start_run(
    _data: RunIn,
    ctx: EditorDep,
    db: DbDep,
    settings: SettingsDep,
    idempotency_key: Annotated[str | None, Header(max_length=64)] = None,
) -> JobRef:
    return service.start_run(db, settings, ctx, idempotency_key)


@router.get("/analysis-runs", summary="API-32 Analysis runs, newest first")
def list_runs(
    ctx: ViewerDep, db: DbDep, limit: Annotated[int, Query(ge=1, le=50)] = 20
) -> list[RunOut]:
    return service.list_runs(db, ctx, limit=limit)


@router.get("/analysis-runs/{run_id}", summary="API-32 One analysis run")
def get_run(run_id: uuid.UUID, ctx: ViewerDep, db: DbDep) -> RunOut:
    return service.get_run(db, ctx, run_id)


@router.get("/analysis", summary="Analysis status for the dashboard (IMP-31)")
def analysis_status(ctx: ViewerDep, db: DbDep) -> AnalysisStatusOut:
    return service.analysis_status(db, ctx)
