"""Prioritisation (D07 §3.6): opportunities, scoring and input provenance (FR-PRI-04)."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import BigInteger, Boolean, Index, Integer, Numeric, Text, Uuid, text
from sqlalchemy.dialects.postgresql import REAL
from sqlalchemy.orm import Mapped, mapped_column

from elucis.db.base import Base
from elucis.db.models._common import (
    EMPTY_ARRAY,
    NOW,
    Json,
    StdColumns,
    Timestamp,
    UuidArray,
    check,
    check_in,
    std_args,
    tenant_fk,
    user_fk,
)


class ScoringConfig(StdColumns, Base):
    __tablename__ = "scoring_configs"
    __table_args__ = std_args(
        "scoring_configs",
        check_in("scoring_configs", "framework", "rice", "ice"),
        Index(
            "uq_scoring_configs_active",
            "workspace_id",
            unique=True,
            postgresql_where=text("is_active"),
        ),
    )

    framework: Mapped[str] = mapped_column(Text)
    impact_scale: Mapped[dict[str, Any]] = mapped_column(Json)
    confidence_rules: Mapped[dict[str, Any]] = mapped_column(Json)
    lane_capacity_weeks: Mapped[float] = mapped_column(REAL, server_default=text("6"))
    version: Mapped[int] = mapped_column(Integer, server_default=text("1"))
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))


class Opportunity(StdColumns, Base):
    __tablename__ = "opportunities"
    __table_args__ = std_args(
        "opportunities",
        check_in("opportunities", "source_kind", "theme", "request"),
        check_in("opportunities", "status", "open", "accepted", "deferred", "rejected"),
        check("opportunities", "one_source", "(theme_id IS NULL) <> (request_id IS NULL)"),
        check(
            "opportunities",
            "source_matches_kind",
            "(source_kind = 'theme') = (theme_id IS NOT NULL)",
        ),
        tenant_fk("opportunities", "theme_id", "themes"),
        tenant_fk("opportunities", "request_id", "aggregated_requests"),
        user_fk("opportunities", "decided_by"),
        Index(
            "uq_opportunities_theme",
            "workspace_id",
            "theme_id",
            unique=True,
            postgresql_where=text("theme_id IS NOT NULL"),
        ),
        Index(
            "uq_opportunities_request",
            "workspace_id",
            "request_id",
            unique=True,
            postgresql_where=text("request_id IS NOT NULL"),
        ),
    )

    source_kind: Mapped[str] = mapped_column(Text)
    theme_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    request_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default=text("'open'"))
    decision_reason: Mapped[str | None] = mapped_column(Text)
    decided_by: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    decided_at: Mapped[datetime | None] = mapped_column(Timestamp)


class ScoreInput(StdColumns, Base):
    """Rows are never updated except ``is_current`` and ``superseded_at`` (column grant)."""

    __tablename__ = "score_inputs"
    __table_args__ = std_args(
        "score_inputs",
        check_in("score_inputs", "framework", "rice", "ice"),
        check_in("score_inputs", "input_name", "reach", "impact", "confidence", "effort", "ease"),
        check_in("score_inputs", "origin", "data", "ai", "person"),
        check(
            "score_inputs", "framework_or_effort", "framework IS NOT NULL OR input_name = 'effort'"
        ),
        check("score_inputs", "ai_rationale", "origin <> 'ai' OR rationale IS NOT NULL"),
        tenant_fk("score_inputs", "opportunity_id", "opportunities", ondelete="CASCADE"),
        tenant_fk("score_inputs", "llm_call_id", "llm_call_records", ondelete="SET NULL"),
        user_fk("score_inputs", "set_by"),
        Index(
            "uq_score_inputs_current",
            "opportunity_id",
            text("coalesce(framework, '-')"),
            "input_name",
            unique=True,
            postgresql_where=text("is_current"),
        ),
    )

    opportunity_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    framework: Mapped[str | None] = mapped_column(Text)  # NULL only for the shared effort
    input_name: Mapped[str] = mapped_column(Text)
    value: Mapped[Decimal] = mapped_column(Numeric)
    origin: Mapped[str] = mapped_column(Text)
    rationale: Mapped[str | None] = mapped_column(Text)
    evidence_ids: Mapped[list[uuid.UUID]] = mapped_column(UuidArray, server_default=EMPTY_ARRAY)
    llm_call_id: Mapped[int | None] = mapped_column(BigInteger)
    set_by: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    is_current: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    superseded_at: Mapped[datetime | None] = mapped_column(Timestamp)


class ScoreSnapshot(StdColumns, Base):
    """Derived ranking, written only by SVC-15 (D07 §1)."""

    __tablename__ = "score_snapshots"
    __table_args__ = std_args(
        "score_snapshots",
        check_in("score_snapshots", "trigger", "recompute", "input_change", "config_change"),
        tenant_fk("score_snapshots", "scoring_config_id", "scoring_configs"),
    )

    scoring_config_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    config_hash: Mapped[str] = mapped_column(Text)
    ranking: Mapped[list[Any]] = mapped_column(Json)
    trigger: Mapped[str] = mapped_column(Text)
    computed_at: Mapped[datetime] = mapped_column(Timestamp, server_default=NOW)
