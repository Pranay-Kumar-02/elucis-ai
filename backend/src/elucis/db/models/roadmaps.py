"""Roadmaps (D07 §3.8). Dependencies are kept inside one roadmap by a composite FK."""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import Boolean, ForeignKeyConstraint, Integer, Numeric, Text, Uuid, text
from sqlalchemy.dialects.postgresql import REAL
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql.elements import conv

from elucis.db.base import Base
from elucis.db.models._common import (
    StdColumns,
    check,
    check_in,
    std_args,
    tenant_fk,
    unique,
    workspace_fk,
)


class Roadmap(StdColumns, Base):
    __tablename__ = "roadmaps"
    __table_args__ = std_args(
        "roadmaps",
        check_in("roadmaps", "status", "draft", "approved"),
        tenant_fk("roadmaps", "score_snapshot_id", "score_snapshots"),
    )

    name: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default=text("'draft'"))
    capacity_per_lane_weeks: Mapped[float] = mapped_column(REAL, server_default=text("6"))
    score_snapshot_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)


class RoadmapItem(StdColumns, Base):
    __tablename__ = "roadmap_items"
    __table_args__ = std_args(
        "roadmap_items",
        unique("roadmap_items", "roadmap_id_opportunity_id", "roadmap_id", "opportunity_id"),
        unique("roadmap_items", "workspace_roadmap_id", "workspace_id", "roadmap_id", "id"),
        check_in("roadmap_items", "lane", "now", "next", "later", "unscheduled"),
        check("roadmap_items", "effort_weeks", "effort_weeks > 0"),
        check_in("roadmap_items", "effort_origin", "person", "ai"),
        tenant_fk("roadmap_items", "roadmap_id", "roadmaps", ondelete="CASCADE"),
        tenant_fk("roadmap_items", "opportunity_id", "opportunities"),
    )

    roadmap_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    opportunity_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    lane: Mapped[str] = mapped_column(Text)
    position: Mapped[int] = mapped_column(Integer)
    effort_weeks: Mapped[Decimal | None] = mapped_column(Numeric)
    effort_origin: Mapped[str | None] = mapped_column(Text)
    manual_position: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))


def _same_roadmap_item(column: str) -> ForeignKeyConstraint:
    return ForeignKeyConstraint(
        ["workspace_id", "roadmap_id", column],
        ["roadmap_items.workspace_id", "roadmap_items.roadmap_id", "roadmap_items.id"],
        ondelete="CASCADE",
        name=conv(f"fk_roadmap_dependencies_{column}"),
    )


class RoadmapDependency(Base):
    """Cycles are rejected by SVC-18; self links by the CHECK."""

    __tablename__ = "roadmap_dependencies"
    __table_args__ = (
        check("roadmap_dependencies", "not_self", "item_id <> depends_on_item_id"),
        workspace_fk("roadmap_dependencies"),
        tenant_fk("roadmap_dependencies", "roadmap_id", "roadmaps", ondelete="CASCADE"),
        _same_roadmap_item("item_id"),
        _same_roadmap_item("depends_on_item_id"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    roadmap_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    item_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    depends_on_item_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
