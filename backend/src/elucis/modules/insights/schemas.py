"""API schemas for insights: themes, pain points, request groups and trends (D09 API-33,
API-34, API-37, API-38; D12 UI-06, UI-11)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

Trend = Literal["up", "flat", "down"]


class WeekOut(BaseModel):
    week: str = Field(description="ISO week, e.g. 2026-W40")
    start: date
    n: int


class GroupStatsOut(BaseModel):
    record_count: int
    known_customers: int
    unknown_identity_records: int
    identity_coverage: float
    share: float = Field(description="Of the classified records in the same filter")
    sentiment: dict[str, int]
    weekly: list[WeekOut]
    undated: int
    trend: Trend


class EvidenceOut(BaseModel):
    """One record as evidence: masked text only (DR-29), with its ID for traceability."""

    record_id: uuid.UUID
    text: str
    occurred_at: datetime | None
    rating: int | None
    source_type: str
    cited: bool = Field(description="Cited by the model when it named the theme (CP-03)")


class ThemeOut(GroupStatsOut):
    id: uuid.UUID
    name: str
    description: str | None
    pain_point: bool
    vocal_flag: bool | None = Field(description="A-11; null when identity coverage < 50%")
    categories: dict[str, int]
    evidence: list[EvidenceOut] = Field(description="Up to 3 quotes: cited first, then central")


class ThemeDetailOut(ThemeOut):
    pass


class AskOut(BaseModel):
    ask: str
    n: int


class RequestOut(GroupStatsOut):
    id: uuid.UUID
    title: str
    asks: list[AskOut] = Field(description="The canonical asks in the group, most common first")
    low_confidence: int = Field(description="Asks that fell back to the record's own text")
    evidence: list[EvidenceOut]


class InsightsOut(BaseModel):
    """Everything the Insights dashboard shows, for one run and one filter."""

    run_id: uuid.UUID | None = Field(description="Null when no analysis has succeeded yet")
    run_finished_at: datetime | None
    filters: dict[str, str | None]
    records_analysed: int
    themes: list[ThemeOut]
    unassigned: int = Field(description="Classified records in no theme (FR-THM-07)")
    pain_points: int
    requests: list[RequestOut]
    source_types: list[str] = Field(description="Source types present in the run, for the filter")
    date_range: dict[str, date | None]
