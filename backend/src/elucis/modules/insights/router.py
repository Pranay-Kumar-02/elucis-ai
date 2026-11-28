"""Insights API: the dashboard summary (IMP-35, proposed), themes (API-33, API-34) and
request groups (API-37, API-38), all for the current run unless ``run_id`` is given."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Query

from elucis.api.auth import DbDep, ViewerDep
from elucis.api.pagination import Page
from elucis.core.errors import ValidationFailedError
from elucis.modules.insights import service
from elucis.modules.insights.schemas import InsightsOut, RequestOut, ThemeDetailOut, ThemeOut
from elucis.modules.insights.stats import Filters

router = APIRouter(prefix="/workspaces/{ws}", tags=["insights"])

FeedbackSource = Literal["review", "ticket", "feature_request", "transcript", "other"]
FromQuery = Annotated[date | None, Query(alias="from")]
ToQuery = Annotated[date | None, Query(alias="to")]
SourceQuery = Annotated[FeedbackSource | None, Query()]
RunQuery = Annotated[uuid.UUID | None, Query()]


def _filters(date_from: date | None, date_to: date | None, source_type: str | None) -> Filters:
    if date_from and date_to and date_from > date_to:
        raise ValidationFailedError(
            "The start of the period is after its end.",
            details=[{"field": "from", "issue": "after_to"}],
        )
    return Filters(date_from=date_from, date_to=date_to, source_type=source_type)


@router.get("/insights", summary="Dashboard insights for one run and filter (IMP-35)")
def insights(
    *,
    ctx: ViewerDep,
    db: DbDep,
    date_from: FromQuery = None,
    date_to: ToQuery = None,
    source_type: SourceQuery = None,
    pain_points_only: bool = False,
    run_id: RunQuery = None,
) -> InsightsOut:
    return service.insights(
        db,
        ctx,
        _filters(date_from, date_to, source_type),
        pain_points_only=pain_points_only,
        run_id=run_id,
    )


@router.get("/themes", summary="API-33 Themes with statistics")
def list_themes(
    *,
    ctx: ViewerDep,
    db: DbDep,
    date_from: FromQuery = None,
    date_to: ToQuery = None,
    source_type: SourceQuery = None,
    run_id: RunQuery = None,
) -> Page[ThemeOut]:
    run = service._run(db, ctx.workspace_id, run_id)
    items = (
        service.theme_list(db, ctx.workspace_id, run.id, _filters(date_from, date_to, source_type))
        if run
        else []
    )
    return Page(items=items, next_cursor=None)


@router.get("/themes/{theme_id}", summary="API-34 Theme detail and evidence")
def theme_detail(
    *,
    theme_id: uuid.UUID,
    ctx: ViewerDep,
    db: DbDep,
    date_from: FromQuery = None,
    date_to: ToQuery = None,
    source_type: SourceQuery = None,
    run_id: RunQuery = None,
) -> ThemeDetailOut:
    return service.theme_detail(
        db, ctx, theme_id, _filters(date_from, date_to, source_type), run_id
    )


@router.get("/requests", summary="API-37 Feature-request groups")
def list_requests(
    *,
    ctx: ViewerDep,
    db: DbDep,
    date_from: FromQuery = None,
    date_to: ToQuery = None,
    source_type: SourceQuery = None,
    run_id: RunQuery = None,
) -> Page[RequestOut]:
    run = service._run(db, ctx.workspace_id, run_id)
    items = (
        service.request_list(
            db, ctx.workspace_id, run.id, _filters(date_from, date_to, source_type)
        )
        if run
        else []
    )
    return Page(items=items, next_cursor=None)


@router.get("/requests/{request_id}", summary="API-38 Request group detail and evidence")
def request_detail(
    *,
    request_id: uuid.UUID,
    ctx: ViewerDep,
    db: DbDep,
    date_from: FromQuery = None,
    date_to: ToQuery = None,
    source_type: SourceQuery = None,
    run_id: RunQuery = None,
) -> RequestOut:
    return service.request_detail(
        db, ctx, request_id, _filters(date_from, date_to, source_type), run_id
    )
