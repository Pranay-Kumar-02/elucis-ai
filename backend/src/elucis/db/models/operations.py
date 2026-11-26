"""Audit and evaluation (D07 §3.11). ``jobs`` is in ``ingestion``; ``llm_call_records`` and
``prompt_versions`` are in ``analysis``."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, Identity, Index, Integer, Text, Uuid, text
from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.orm import Mapped, mapped_column

from elucis.db.base import Base
from elucis.db.models._common import (
    EMPTY_OBJECT,
    NOW,
    Json,
    StdColumns,
    Timestamp,
    check_in,
    std_args,
    tenant_fk,
    workspace_fk,
)


class AuditLog(Base):
    """Append-only (SEC-15): application roles may only INSERT and SELECT.

    ``workspace_id`` is NULL for sign-in events and for ``workspace.deleted``, which must
    outlive the workspace whose other entries are removed with it (A-21, IMP-24).
    """

    __tablename__ = "audit_logs"
    __table_args__ = (
        check_in("audit_logs", "outcome", "success", "failure"),
        workspace_fk("audit_logs"),
        Index("ix_audit_logs_workspace_id_created_at", "workspace_id", text("created_at DESC")),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    action: Mapped[str] = mapped_column(Text)
    target_type: Mapped[str | None] = mapped_column(Text)
    target_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    outcome: Mapped[str] = mapped_column(Text)
    details: Mapped[dict[str, Any]] = mapped_column(Json, server_default=EMPTY_OBJECT)
    ip: Mapped[str | None] = mapped_column(INET)
    created_at: Mapped[datetime] = mapped_column(Timestamp, server_default=NOW)


class EvaluationDataset(StdColumns, Base):
    __tablename__ = "evaluation_datasets"
    __table_args__ = std_args(
        "evaluation_datasets",
        tenant_fk("evaluation_datasets", "source_file_id", "source_files"),
    )

    name: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    source_file_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    split_seed: Mapped[int] = mapped_column(Integer)
    frozen_at: Mapped[datetime | None] = mapped_column(Timestamp)


class EvaluationItem(StdColumns, Base):
    __tablename__ = "evaluation_items"
    __table_args__ = std_args(
        "evaluation_items",
        check_in("evaluation_items", "split", "train", "validation", "test"),
        tenant_fk("evaluation_items", "dataset_id", "evaluation_datasets", ondelete="CASCADE"),
        tenant_fk("evaluation_items", "record_id", "feedback_records"),
    )

    dataset_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    record_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    text_masked: Mapped[str] = mapped_column(Text)
    split: Mapped[str] = mapped_column(Text)
    gold: Mapped[dict[str, Any]] = mapped_column(Json)
    labeller_a: Mapped[dict[str, Any] | None] = mapped_column(Json)
    labeller_b: Mapped[dict[str, Any] | None] = mapped_column(Json)
    adjudicated: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))


class EvaluationRun(StdColumns, Base):
    __tablename__ = "evaluation_runs"
    __table_args__ = std_args(
        "evaluation_runs",
        check_in(
            "evaluation_runs",
            "kind",
            "classification",
            "themes",
            "aggregation",
            "retrieval",
            "generation",
            "assistant",
            "injection",
            "pii",
            "performance",
        ),
        tenant_fk("evaluation_runs", "dataset_id", "evaluation_datasets"),
    )

    dataset_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    kind: Mapped[str] = mapped_column(Text)
    config: Mapped[dict[str, Any]] = mapped_column(Json)
    config_hash: Mapped[str] = mapped_column(Text)
    metrics: Mapped[dict[str, Any] | None] = mapped_column(Json)
    started_at: Mapped[datetime | None] = mapped_column(Timestamp)
    finished_at: Mapped[datetime | None] = mapped_column(Timestamp)
    notes: Mapped[str | None] = mapped_column(Text)
