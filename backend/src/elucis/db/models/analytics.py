"""Product analytics (D07 §3.5): metrics, releases and links to themes or requests."""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import Boolean, Date, Index, Text, Uuid, text
from sqlalchemy.dialects.postgresql import DOUBLE_PRECISION
from sqlalchemy.orm import Mapped, mapped_column

from elucis.db.base import Base
from elucis.db.models._common import StdColumns, check, check_in, std_args, tenant_fk, unique


class MetricDefinition(StdColumns, Base):
    __tablename__ = "metric_definitions"
    __table_args__ = std_args(
        "metric_definitions",
        check_in("metric_definitions", "aggregation", "sum", "avg", "last"),
        Index("uq_metric_definitions_name_lower", "workspace_id", text("lower(name)"), unique=True),
    )

    name: Mapped[str] = mapped_column(Text)
    unit: Mapped[str | None] = mapped_column(Text)
    aggregation: Mapped[str] = mapped_column(Text, server_default=text("'sum'"))
    description: Mapped[str | None] = mapped_column(Text)


class MetricObservation(StdColumns, Base):
    __tablename__ = "metric_observations"
    __table_args__ = std_args(
        "metric_observations",
        unique(
            "metric_observations",
            "metric_day_dimension",
            "workspace_id",
            "metric_id",
            "observed_on",
            "dimension",
        ),
        tenant_fk("metric_observations", "metric_id", "metric_definitions"),
        tenant_fk("metric_observations", "import_job_id", "import_jobs"),
    )

    metric_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    observed_on: Mapped[date] = mapped_column(Date)
    dimension: Mapped[str] = mapped_column(Text, server_default=text("''"))
    value: Mapped[float] = mapped_column(DOUBLE_PRECISION)
    import_job_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)


class ProductRelease(StdColumns, Base):
    __tablename__ = "product_releases"
    __table_args__ = std_args(
        "product_releases",
        unique("product_releases", "workspace_id_version", "workspace_id", "version"),
        Index("ix_product_releases_released_on", "workspace_id", text("released_on DESC")),
    )

    version: Mapped[str] = mapped_column(Text)
    released_on: Mapped[date] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)


class ThemeMetricLink(StdColumns, Base):
    __tablename__ = "theme_metric_links"
    __table_args__ = std_args(
        "theme_metric_links",
        check("theme_metric_links", "one_subject", "(theme_id IS NULL) <> (request_id IS NULL)"),
        check_in("theme_metric_links", "expected_relation", "positive", "negative"),
        check_in("theme_metric_links", "origin", "person", "system_suggestion"),
        tenant_fk("theme_metric_links", "theme_id", "themes"),
        tenant_fk("theme_metric_links", "request_id", "aggregated_requests"),
        tenant_fk("theme_metric_links", "metric_id", "metric_definitions"),
    )

    theme_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    request_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    metric_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    expected_relation: Mapped[str] = mapped_column(Text)
    origin: Mapped[str] = mapped_column(Text)
    accepted: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
