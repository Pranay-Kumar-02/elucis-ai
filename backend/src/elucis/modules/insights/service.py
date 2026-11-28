"""Insights read models: what the dashboard shows for the current run (or a chosen one),
filtered by period and source. Every figure is computed by ``stats`` from the stored run;
no model is called here (D03: the LLM never computes counts, customers or trends).

Call chain::

    insights(db, ctx, filters)          -> InsightsOut (dashboard, one request)
      _run(...)                         -> the current succeeded run, or None
      theme_list(...) / request_list()  -> stats.theme_stats / stats.request_stats + evidence
    theme_detail(...) / request_detail() -> one group with more evidence (API-34, API-38)
"""

from __future__ import annotations

import uuid
from datetime import UTC
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from elucis.core.errors import NotFoundError
from elucis.db.models import (
    AggregatedRequest,
    AnalysisRun,
    FeedbackRecord,
    RecordClassification,
    RecordEmbedding,
    RequestMembership,
    Theme,
    ThemeMembership,
    ThemeRunStats,
    Workspace,
)
from elucis.db.models._common import CURRENT_EMBEDDING_MODEL
from elucis.modules.identity.context import WorkspaceContext
from elucis.modules.insights import stats
from elucis.modules.insights.schemas import (
    AskOut,
    EvidenceOut,
    GroupStatsOut,
    InsightsOut,
    RequestOut,
    ThemeDetailOut,
    ThemeOut,
    WeekOut,
)
from elucis.modules.insights.stats import Filters, GroupStats

LIST_EVIDENCE = 3
DETAIL_EVIDENCE = 10


def _run(db: Session, ws: uuid.UUID, run_id: uuid.UUID | None) -> AnalysisRun | None:
    if run_id is None:
        run_id = db.execute(
            select(Workspace.current_analysis_run_id).where(Workspace.id == ws)
        ).scalar_one_or_none()
        if run_id is None:
            return None
    run = db.execute(
        select(AnalysisRun).where(
            AnalysisRun.workspace_id == ws,
            AnalysisRun.id == run_id,
            AnalysisRun.status == "succeeded",
        )
    ).scalar_one_or_none()
    if run is None:
        raise NotFoundError("The analysis run was not found.")
    return run


def _stats_out(s: GroupStats) -> dict[str, Any]:
    return GroupStatsOut(
        record_count=s.record_count,
        known_customers=s.known_customers,
        unknown_identity_records=s.unknown_identity_records,
        identity_coverage=round(s.identity_coverage, 4),
        share=round(s.share, 4),
        sentiment=s.sentiment,
        weekly=[WeekOut(**w) for w in s.weekly],
        undated=s.undated,
        trend=s.trend,  # type: ignore[arg-type]
    ).model_dump()


# ---------------------------------------------------------------- evidence
def _evidence(  # noqa: PLR0917 - a membership table and one group in it
    db: Session,
    ws: uuid.UUID,
    run_id: uuid.UUID,
    membership: Any,
    group_column: Any,
    group_id: uuid.UUID,
    *,
    filters: Filters,
    first: list[uuid.UUID],
    centroid: list[float] | None,
    limit: int,
) -> list[EvidenceOut]:
    """Cited records first, then the most central members (themes) or the most recent ones
    (requests), all inside the filter. Masked text only."""
    fr = FeedbackRecord
    query = (
        select(fr.id, fr.processed_text, fr.occurred_at, fr.rating, fr.source_type)
        .join(
            membership,
            and_(membership.workspace_id == fr.workspace_id, membership.record_id == fr.id),
        )
        .where(
            membership.workspace_id == ws,
            membership.analysis_run_id == run_id,
            group_column == group_id,
            fr.processed_text.is_not(None),
        )
    )
    query = stats._filtered(query, filters)
    if centroid is not None:
        emb = RecordEmbedding
        query = query.join(
            emb,
            and_(
                emb.workspace_id == fr.workspace_id,
                emb.record_id == fr.id,
                emb.model_id == CURRENT_EMBEDDING_MODEL,
            ),
        ).order_by(emb.embedding.cosine_distance(centroid), fr.id)
    else:
        query = query.order_by(fr.occurred_at.desc().nulls_last(), fr.id)
    rows = db.execute(query.limit(limit + len(first))).all()
    cited = set(first)
    if first:
        rows = [*db.execute(stats._filtered(query.where(fr.id.in_(first)), filters)).all(), *rows]
    out: list[EvidenceOut] = []
    seen: set[uuid.UUID] = set()
    for r in rows:
        if r.id in seen:
            continue
        seen.add(r.id)
        out.append(
            EvidenceOut(
                record_id=r.id,
                text=r.processed_text or "",
                occurred_at=r.occurred_at.astimezone(UTC) if r.occurred_at else None,
                rating=r.rating,
                source_type=r.source_type,
                cited=r.id in cited,
            )
        )
        if len(out) == limit:
            break
    return out


# ---------------------------------------------------------------- themes
def theme_list(
    db: Session,
    ws: uuid.UUID,
    run_id: uuid.UUID,
    filters: Filters,
    *,
    evidence: int = LIST_EVIDENCE,
) -> list[ThemeOut]:
    group = stats.theme_stats(db, ws, run_id, filters)
    themes = db.execute(
        select(Theme, ThemeRunStats.cited_record_ids, ThemeRunStats.vocal_flag)
        .outerjoin(
            ThemeRunStats,
            and_(
                ThemeRunStats.workspace_id == Theme.workspace_id,
                ThemeRunStats.theme_id == Theme.id,
                ThemeRunStats.analysis_run_id == run_id,
            ),
        )
        .where(Theme.workspace_id == ws, Theme.first_run_id == run_id)
    ).all()
    out = []
    for theme, cited, vocal in themes:
        s = group.get(theme.id)
        if s is None or s.record_count == 0:
            continue  # no records of this theme inside the filter
        out.append(
            ThemeOut(
                **_stats_out(s),
                id=theme.id,
                name=theme.name,
                description=theme.description or None,
                pain_point=s.pain_point,
                vocal_flag=vocal if filters == Filters() else s.vocal_flag,
                categories=s.categories,
                evidence=_evidence(
                    db,
                    ws,
                    run_id,
                    ThemeMembership,
                    ThemeMembership.theme_id,
                    theme.id,
                    filters=filters,
                    first=list(cited or []),
                    centroid=theme.centroid,
                    limit=evidence,
                ),
            )
        )
    return sorted(out, key=lambda t: (-t.record_count, t.name))


def theme_detail(
    db: Session,
    ctx: WorkspaceContext,
    theme_id: uuid.UUID,
    filters: Filters,
    run_id: uuid.UUID | None,
) -> ThemeDetailOut:
    run = _run(db, ctx.workspace_id, run_id)
    found = run and next(
        (
            t
            for t in theme_list(db, ctx.workspace_id, run.id, filters, evidence=DETAIL_EVIDENCE)
            if t.id == theme_id
        ),
        None,
    )
    if not found:
        raise NotFoundError("The theme was not found in this analysis.")
    return ThemeDetailOut(**found.model_dump())


# ---------------------------------------------------------------- requests
def request_list(
    db: Session,
    ws: uuid.UUID,
    run_id: uuid.UUID,
    filters: Filters,
    *,
    evidence: int = LIST_EVIDENCE,
) -> list[RequestOut]:
    group = stats.request_stats(db, ws, run_id, filters)
    rm, fr = RequestMembership, FeedbackRecord
    ask_query = (
        select(
            rm.request_id,
            rm.canonical_ask,
            func.count().label("n"),
            func.count().filter(rm.low_confidence).label("low"),
        )
        .join(fr, and_(fr.workspace_id == rm.workspace_id, fr.id == rm.record_id))
        .where(rm.workspace_id == ws, rm.analysis_run_id == run_id)
        .group_by(rm.request_id, rm.canonical_ask)
    )
    asks: dict[uuid.UUID, list[AskOut]] = {}
    low: dict[uuid.UUID, int] = {}
    for r in db.execute(stats._filtered(ask_query, filters)).all():
        asks.setdefault(r.request_id, []).append(AskOut(ask=r.canonical_ask, n=r.n))
        low[r.request_id] = low.get(r.request_id, 0) + int(r.low)
    out = []
    for request in db.execute(
        select(AggregatedRequest).where(
            AggregatedRequest.workspace_id == ws, AggregatedRequest.first_run_id == run_id
        )
    ).scalars():
        s = group.get(request.id)
        if s is None or s.record_count == 0:
            continue
        out.append(
            RequestOut(
                **_stats_out(s),
                id=request.id,
                title=request.title,
                asks=sorted(asks.get(request.id, []), key=lambda a: (-a.n, a.ask)),
                low_confidence=low.get(request.id, 0),
                evidence=_evidence(
                    db,
                    ws,
                    run_id,
                    rm,
                    rm.request_id,
                    request.id,
                    filters=filters,
                    first=[],
                    centroid=None,
                    limit=evidence,
                ),
            )
        )
    return sorted(out, key=lambda r: (-r.record_count, r.title))


def request_detail(
    db: Session,
    ctx: WorkspaceContext,
    request_id: uuid.UUID,
    filters: Filters,
    run_id: uuid.UUID | None,
) -> RequestOut:
    run = _run(db, ctx.workspace_id, run_id)
    found = run and next(
        (
            r
            for r in request_list(db, ctx.workspace_id, run.id, filters, evidence=DETAIL_EVIDENCE)
            if r.id == request_id
        ),
        None,
    )
    if not found:
        raise NotFoundError("The request group was not found in this analysis.")
    return found


# ---------------------------------------------------------------- dashboard
def insights(
    db: Session,
    ctx: WorkspaceContext,
    filters: Filters,
    *,
    pain_points_only: bool,
    run_id: uuid.UUID | None,
) -> InsightsOut:
    ws = ctx.workspace_id
    run = _run(db, ws, run_id)
    applied = {
        "from": filters.date_from.isoformat() if filters.date_from else None,
        "to": filters.date_to.isoformat() if filters.date_to else None,
        "source_type": filters.source_type,
    }
    if run is None:
        return InsightsOut(
            run_id=None,
            run_finished_at=None,
            filters=applied,
            records_analysed=0,
            themes=[],
            unassigned=0,
            pain_points=0,
            requests=[],
            source_types=[],
            date_range={"from": None, "to": None},
        )
    themes = theme_list(db, ws, run.id, filters)
    total = stats.classified_total(db, ws, run.id, filters)
    assigned = sum(t.record_count for t in themes)
    fr, rc = FeedbackRecord, RecordClassification
    in_run = and_(rc.workspace_id == ws, rc.analysis_run_id == run.id, rc.status == "classified")
    joined = select(fr.source_type).join(
        rc, and_(rc.workspace_id == fr.workspace_id, rc.record_id == fr.id)
    )
    source_types = sorted(db.execute(joined.where(in_run).distinct()).scalars())
    first, last = db.execute(
        select(func.min(fr.occurred_at), func.max(fr.occurred_at))
        .join(rc, and_(rc.workspace_id == fr.workspace_id, rc.record_id == fr.id))
        .where(in_run)
    ).one()
    return InsightsOut(
        run_id=run.id,
        run_finished_at=run.finished_at,
        filters=applied,
        records_analysed=total,
        themes=[t for t in themes if t.pain_point] if pain_points_only else themes,
        unassigned=max(total - assigned, 0),
        pain_points=sum(1 for t in themes if t.pain_point),
        requests=request_list(db, ws, run.id, filters),
        source_types=source_types,
        date_range={
            "from": first.astimezone(UTC).date() if first else None,
            "to": last.astimezone(UTC).date() if last else None,
        },
    )
