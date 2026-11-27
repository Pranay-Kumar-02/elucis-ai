"""Theme and request statistics, weekly series and trend direction (SVC-10 statistics,
SVC-13 trend rule, FR-THM-05, FR-AGG-04, FR-AGG-07). Deterministic SQL; no model involved.

The same functions serve the analysis job (unfiltered snapshot in ``theme_run_stats``) and
the API (filtered by period and source), so a number on the dashboard is always computed
one way.

Rules:

* ``record_count`` counts classified records only; near duplicates and failures never count.
* ``known_customers`` = distinct non-null customer IDs; unknown-identity records are counted
  separately and never as customers (CR-18).
* Weekly series use ISO weeks of ``occurred_at`` in UTC; undated records are counted as
  ``undated``, not placed in a week.
* Trend: least-squares slope over the last 8 weeks ending at the latest week with data in
  the filtered set (feedback exports are historical, so "now" would make every trend flat);
  up or down when the change across the window is at least 5% of the window's mean
  (SVC-13) and the window holds at least 3 records; otherwise flat.
* Pain point: at least half of a theme's records are issues (bug, usability, performance)
  or negative (IMP-33, proposed).
"""

from __future__ import annotations

import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from elucis.ai.prompts import ISSUE_CATEGORIES
from elucis.db.models import FeedbackRecord, RecordClassification, ThemeMembership

TREND_WEEKS = 8
MIN_RELATIVE_CHANGE = 0.05  # SVC-13
MIN_WINDOW_RECORDS = 3
VOCAL_MIN_RECORDS = 10  # A-11
VOCAL_TOP_SHARE = 0.2
VOCAL_MIN_COVERAGE = 0.5
PAIN_POINT_SHARE = 0.5


@dataclass(frozen=True, slots=True)
class Filters:
    date_from: date | None = None
    date_to: date | None = None
    source_type: str | None = None


@dataclass(slots=True)
class GroupStats:
    group_id: uuid.UUID
    record_count: int = 0
    known_customers: int = 0
    unknown_identity_records: int = 0
    identity_coverage: float = 0.0
    share: float = 0.0
    sentiment: dict[str, int] = field(default_factory=dict)
    categories: dict[str, int] = field(default_factory=dict)
    weekly: list[dict[str, Any]] = field(default_factory=list)
    undated: int = 0
    trend: str = "flat"
    top_customer_share: float | None = None
    vocal_flag: bool | None = None

    @property
    def pain_point(self) -> bool:
        if not self.record_count:
            return False
        issues = sum(n for c, n in self.categories.items() if c in ISSUE_CATEGORIES)
        negative = self.sentiment.get("negative", 0)
        return max(issues, negative) / self.record_count >= PAIN_POINT_SHARE


# ---------------------------------------------------------------- trend
def iso_week(day: date) -> str:
    year, week, _ = day.isocalendar()
    return f"{year}-W{week:02d}"


def weekly_series(dates: list[datetime]) -> list[dict[str, Any]]:
    """Counts per ISO week from the first to the last week, empty weeks included."""
    if not dates:
        return []
    days = [d.astimezone(UTC).date() for d in dates]
    mondays = Counter(d - timedelta(days=d.weekday()) for d in days)
    first, last = min(mondays), max(mondays)
    series = []
    week = first
    while week <= last:
        series.append(
            {"week": iso_week(week), "start": week.isoformat(), "n": mondays.get(week, 0)}
        )
        week += timedelta(days=7)
    return series


def trend_direction(series: list[dict[str, Any]], window_end: date | None) -> str:
    if not series or window_end is None:
        return "flat"
    end = window_end - timedelta(days=window_end.weekday())
    counts = {date.fromisoformat(w["start"]): int(w["n"]) for w in series}
    ys = [counts.get(end - timedelta(days=7 * k), 0) for k in reversed(range(TREND_WEEKS))]
    total = sum(ys)
    if total < MIN_WINDOW_RECORDS:
        return "flat"
    xs = list(range(TREND_WEEKS))
    mean_x, mean_y = sum(xs) / len(xs), total / len(ys)
    slope = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys, strict=True)) / sum(
        (x - mean_x) ** 2 for x in xs
    )
    change = slope * (TREND_WEEKS - 1) / mean_y
    if change >= MIN_RELATIVE_CHANGE:
        return "up"
    if change <= -MIN_RELATIVE_CHANGE:
        return "down"
    return "flat"


# ---------------------------------------------------------------- per group
def _filtered(query: Any, filters: Filters) -> Any:
    fr = FeedbackRecord
    if filters.source_type:
        query = query.where(fr.source_type == filters.source_type)
    if filters.date_from:
        query = query.where(
            fr.occurred_at >= datetime.combine(filters.date_from, datetime.min.time(), UTC)
        )
    if filters.date_to:
        query = query.where(
            fr.occurred_at
            < datetime.combine(filters.date_to + timedelta(days=1), datetime.min.time(), UTC)
        )
    return query


def classified_total(db: Session, ws: uuid.UUID, run_id: uuid.UUID, filters: Filters) -> int:
    fr, rc = FeedbackRecord, RecordClassification
    query = (
        select(func.count())
        .select_from(rc)
        .join(fr, and_(fr.workspace_id == rc.workspace_id, fr.id == rc.record_id))
        .where(rc.workspace_id == ws, rc.analysis_run_id == run_id, rc.status == "classified")
    )
    return int(db.execute(_filtered(query, filters)).scalar_one())


def group_stats(
    db: Session,
    ws: uuid.UUID,
    run_id: uuid.UUID,
    membership: Any,
    group_column: Any,
    *,
    filters: Filters | None = None,
) -> dict[uuid.UUID, GroupStats]:
    """Statistics for every group of a membership table (themes or requests) in a run."""
    filters = filters or Filters()
    fr, rc = FeedbackRecord, RecordClassification
    query = (
        select(
            group_column.label("group_id"),
            fr.customer_id,
            fr.occurred_at,
            rc.sentiment,
            rc.category,
        )
        .select_from(membership)
        .join(fr, and_(fr.workspace_id == membership.workspace_id, fr.id == membership.record_id))
        .join(
            rc,
            and_(
                rc.workspace_id == membership.workspace_id,
                rc.analysis_run_id == membership.analysis_run_id,
                rc.record_id == membership.record_id,
            ),
        )
        .where(
            membership.workspace_id == ws,
            membership.analysis_run_id == run_id,
            rc.status == "classified",
        )
    )
    rows = db.execute(_filtered(query, filters)).all()
    total = classified_total(db, ws, run_id, filters)
    latest = max((r.occurred_at for r in rows if r.occurred_at), default=None)
    grouped: dict[uuid.UUID, list[Any]] = defaultdict(list)
    for r in rows:
        grouped[r.group_id].append(r)
    out: dict[uuid.UUID, GroupStats] = {}
    for gid, members in grouped.items():
        s = GroupStats(gid)
        s.record_count = len(members)
        per_customer = Counter(m.customer_id for m in members if m.customer_id is not None)
        known_records = sum(per_customer.values())
        s.known_customers = len(per_customer)
        s.unknown_identity_records = s.record_count - known_records
        s.identity_coverage = known_records / s.record_count
        s.share = s.record_count / total if total else 0.0
        s.sentiment = dict(Counter(m.sentiment for m in members))
        s.categories = dict(Counter(m.category for m in members))
        dated = [m.occurred_at for m in members if m.occurred_at is not None]
        s.weekly = weekly_series(dated)
        s.undated = s.record_count - len(dated)
        s.trend = trend_direction(s.weekly, latest.astimezone(UTC).date() if latest else None)
        if known_records:
            s.top_customer_share = max(per_customer.values()) / known_records
        if s.identity_coverage >= VOCAL_MIN_COVERAGE:
            s.vocal_flag = (
                known_records >= VOCAL_MIN_RECORDS and (s.top_customer_share or 0) > VOCAL_TOP_SHARE
            )
        out[gid] = s
    return out


def theme_stats(
    db: Session, ws: uuid.UUID, run_id: uuid.UUID, filters: Filters | None = None
) -> dict[uuid.UUID, GroupStats]:
    tm = ThemeMembership
    return group_stats(db, ws, run_id, tm, tm.theme_id, filters=filters)
