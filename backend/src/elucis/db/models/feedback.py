"""Feedback (D07 §3.3): pseudonymous customers and the evidence base."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, Computed, Index, Integer, SmallInteger, Text, Uuid, text
from sqlalchemy.dialects.postgresql import BYTEA, REAL, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from elucis.db.base import Base
from elucis.db.models._common import (
    EMPTY_OBJECT,
    SOURCE_TYPES,
    Json,
    StdColumns,
    Timestamp,
    check,
    check_in,
    std_args,
    tenant_fk,
    unique,
    user_fk,
)

T = "feedback_records"


class Customer(StdColumns, Base):
    __tablename__ = "customers"
    __table_args__ = std_args(
        "customers",
        unique("customers", "workspace_id_customer_key", "workspace_id", "customer_key"),
    )

    customer_key: Mapped[bytes] = mapped_column(BYTEA)  # HMAC of the source identifier
    first_seen_at: Mapped[datetime | None] = mapped_column(Timestamp)
    last_seen_at: Mapped[datetime | None] = mapped_column(Timestamp)


class FeedbackRecord(StdColumns, Base):
    """``raw_text`` is immutable: a trigger rejects any change (DR-35)."""

    __tablename__ = T
    __table_args__ = std_args(
        T,
        unique(T, "import_row", "workspace_id", "import_job_id", "row_number", "segment_index"),
        check_in(T, "source_type", *SOURCE_TYPES),
        check(T, "rating", "rating BETWEEN 1 AND 5"),
        check_in(T, "stage", "captured", "cleaned", "standardised", "masked", "prepared", "failed"),
        check_in(
            T,
            "exclusion_reason",
            "noise",
            "pii_failed",
            "non_english",
            "duplicate",
            "spam",
            "spam_review",
        ),
        check_in(T, "spam_status", "not_checked", "clean", "spam", "review_required"),
        check(T, "analysable_not_excluded", "NOT analysable OR exclusion_reason IS NULL"),
        check(
            T,
            "duplicate_reason",
            "duplicate_of IS NULL OR exclusion_reason IS NOT DISTINCT FROM 'duplicate'",
        ),
        check(
            T,
            "spam_review_status",
            "exclusion_reason IS DISTINCT FROM 'spam_review' OR spam_status = 'review_required'",
        ),
        check(T, "analysable_prepared", "NOT analysable OR stage = 'prepared'"),
        tenant_fk(T, "import_job_id", "import_jobs"),
        tenant_fk(T, "parent_record_id", T),
        tenant_fk(T, "customer_id", "customers"),
        tenant_fk(T, "duplicate_of", T),
        user_fk(T, "flag_overridden_by"),
        Index(
            "ix_feedback_records_analysable_occurred_at",
            "workspace_id",
            "analysable",
            "occurred_at",
        ),
        Index("ix_feedback_records_content_hash", "workspace_id", "content_hash"),
        Index("ix_feedback_records_customer_id", "workspace_id", "customer_id"),
        Index("ix_feedback_records_import_job_id", "workspace_id", "import_job_id"),
        Index("ix_feedback_records_search_tsv", "search_tsv", postgresql_using="gin"),
    )

    import_job_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    row_number: Mapped[int] = mapped_column(Integer)
    segment_index: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    parent_record_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    source_type: Mapped[str] = mapped_column(Text)
    source_record_id: Mapped[str | None] = mapped_column(Text)
    raw_text: Mapped[str] = mapped_column(Text)
    processed_text: Mapped[str | None] = mapped_column(Text)
    content_hash: Mapped[bytes | None] = mapped_column(BYTEA)
    customer_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)  # NULL = unknown (CR-18)
    speaker: Mapped[str | None] = mapped_column(Text)
    occurred_at: Mapped[datetime | None] = mapped_column(Timestamp)
    occurred_at_missing: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    rating: Mapped[int | None] = mapped_column(SmallInteger)
    rating_raw: Mapped[str | None] = mapped_column(Text)
    product_version: Mapped[str | None] = mapped_column(Text)
    language: Mapped[str | None] = mapped_column(Text)
    stage: Mapped[str] = mapped_column(Text, server_default=text("'captured'"))
    analysable: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    exclusion_reason: Mapped[str | None] = mapped_column(Text)
    duplicate_of: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    spam_score: Mapped[float | None] = mapped_column(REAL)
    spam_reason: Mapped[str | None] = mapped_column(Text)
    spam_status: Mapped[str] = mapped_column(Text, server_default=text("'not_checked'"))
    pii_counts: Mapped[dict[str, Any]] = mapped_column(Json, server_default=EMPTY_OBJECT)
    flag_overridden_by: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    critical_signal: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    # "metadata" is reserved by SQLAlchemy's declarative base, hence the attribute name.
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", Json, server_default=EMPTY_OBJECT)
    search_tsv: Mapped[str] = mapped_column(
        TSVECTOR,
        Computed("to_tsvector('english'::regconfig, COALESCE(processed_text, ''::text))"),
    )
