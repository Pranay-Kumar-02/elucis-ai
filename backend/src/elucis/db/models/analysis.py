"""AI analysis (D07 §3.4), plus the model-call log and prompt registry it references (§3.11).

Results are versioned by ``analysis_run_id``: a re-run never overwrites a previous run.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    ForeignKeyConstraint,
    Identity,
    Index,
    Integer,
    SmallInteger,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import BYTEA, REAL
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql.elements import conv

from elucis.db.base import Base
from elucis.db.models._common import (
    CURRENT_EMBEDDING_MODEL,
    EMPTY_ARRAY,
    EMPTY_OBJECT,
    NOW,
    Embedding,
    Json,
    StdColumns,
    Timestamp,
    UuidArray,
    check,
    check_in,
    std_args,
    tenant_fk,
    unique,
    user_fk,
    workspace_fk,
)


class PromptVersion(Base):
    """Global registry of prompt templates (D07 §3.11); not tenant-scoped."""

    __tablename__ = "prompt_versions"
    __table_args__ = (unique("prompt_versions", "call_id_version", "call_id", "version"),)

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    call_id: Mapped[str] = mapped_column(Text)
    version: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[bytes] = mapped_column(BYTEA)
    template: Mapped[str] = mapped_column(Text)
    output_schema: Mapped[dict[str, Any] | None] = mapped_column(Json)
    examples: Mapped[list[Any]] = mapped_column(Json, server_default=text("'[]'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(Timestamp, server_default=NOW)


class LlmCallRecord(Base):
    """Append-only model-call log (D07 §3.11). Prompt and response text are not stored."""

    __tablename__ = "llm_call_records"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name=conv("uq_llm_call_records_workspace_id_id")),
        check_in("llm_call_records", "outcome", "ok", "invalid_output", "timeout", "error"),
        check_in("llm_call_records", "provider", "ollama", "gemini"),  # migration 0004
        workspace_fk("llm_call_records"),
        ForeignKeyConstraint(
            ["prompt_version_id"],
            ["prompt_versions.id"],
            name=conv("fk_llm_call_records_prompt_version_id"),
        ),
        tenant_fk("llm_call_records", "job_id", "jobs"),
        Index("ix_llm_call_records_workspace_id_created_at", "workspace_id", "created_at"),
        Index(
            "ix_llm_call_records_input_hash_prompt_version_id", "input_hash", "prompt_version_id"
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    call_id: Mapped[str] = mapped_column(Text)  # 'CP-01' ... 'CP-10', 'EMBED'
    model_tag: Mapped[str] = mapped_column(Text)
    prompt_version_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    input_hash: Mapped[bytes] = mapped_column(BYTEA)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    prompt_eval_ms: Mapped[int | None] = mapped_column(Integer)
    eval_ms: Mapped[int | None] = mapped_column(Integer)
    total_ms: Mapped[int | None] = mapped_column(Integer)
    attempt: Mapped[int] = mapped_column(SmallInteger, server_default=text("1"))
    outcome: Mapped[str] = mapped_column(Text)
    provider: Mapped[str] = mapped_column(Text, server_default=text("'ollama'"))  # IMP-38
    job_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    created_at: Mapped[datetime] = mapped_column(Timestamp, server_default=NOW)


class AnalysisRun(StdColumns, Base):
    __tablename__ = "analysis_runs"
    __table_args__ = std_args(
        "analysis_runs",
        check_in(
            "analysis_runs", "status", "queued", "running", "succeeded", "failed", "cancelled"
        ),
        tenant_fk("analysis_runs", "previous_run_id", "analysis_runs"),
        tenant_fk("analysis_runs", "job_id", "jobs"),
        user_fk("analysis_runs", "triggered_by"),
    )

    status: Mapped[str] = mapped_column(Text, server_default=text("'queued'"))
    config: Mapped[dict[str, Any]] = mapped_column(Json)
    config_hash: Mapped[str] = mapped_column(Text)
    embedding_model_id: Mapped[str] = mapped_column(Text)
    previous_run_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    job_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    triggered_by: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    report: Mapped[dict[str, Any] | None] = mapped_column(Json)
    started_at: Mapped[datetime | None] = mapped_column(Timestamp)
    finished_at: Mapped[datetime | None] = mapped_column(Timestamp)


RC = "record_classifications"


class RecordClassification(StdColumns, Base):
    __tablename__ = RC
    __table_args__ = std_args(
        RC,
        unique(RC, "run_record", "analysis_run_id", "record_id"),
        check_in(RC, "status", "classified", "near_duplicate", "unclassified", "embedding_failed"),
        check_in(
            RC,
            "category",
            "bug_report",
            "feature_request",
            "usability_issue",
            "performance_issue",
            "praise",
            "question",
            "other",
        ),
        check_in(RC, "sentiment", "positive", "neutral", "negative", "mixed"),
        check_in(RC, "method", "classifier", "llm", "human"),
        check(RC, "confidence", "confidence BETWEEN 0 AND 1"),
        check(
            RC,
            "classified_fields",
            "status <> 'classified' OR (category IS NOT NULL AND sentiment IS NOT NULL"
            " AND method IS NOT NULL)",
        ),
        check(
            RC,
            "near_duplicate_link",
            "(status = 'near_duplicate') = (near_duplicate_of IS NOT NULL)",
        ),
        tenant_fk(RC, "analysis_run_id", "analysis_runs", ondelete="CASCADE"),
        tenant_fk(RC, "record_id", "feedback_records"),
        tenant_fk(RC, "near_duplicate_of", "feedback_records"),
        tenant_fk(RC, "llm_call_id", "llm_call_records", ondelete="SET NULL"),
        Index(
            "ix_record_classifications_run_status_category",
            "workspace_id",
            "analysis_run_id",
            "status",
            "category",
        ),
    )

    analysis_run_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    record_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    status: Mapped[str] = mapped_column(Text, server_default=text("'classified'"))
    near_duplicate_of: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    category: Mapped[str | None] = mapped_column(Text)
    sentiment: Mapped[str | None] = mapped_column(Text)
    sarcasm: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    method: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float | None] = mapped_column(REAL)
    calibrated: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    llm_call_id: Mapped[int | None] = mapped_column(BigInteger)


class RecordEmbedding(Base):
    """One L2-normalised vector per record per embedding model (DR-26)."""

    __tablename__ = "record_embeddings"
    __table_args__ = (
        workspace_fk("record_embeddings"),
        tenant_fk("record_embeddings", "record_id", "feedback_records", ondelete="CASCADE"),
        Index(
            "ix_record_embeddings_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
            postgresql_where=text(f"model_id = '{CURRENT_EMBEDDING_MODEL}'"),
        ),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    record_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    model_id: Mapped[str] = mapped_column(Text, primary_key=True)
    embedding: Mapped[list[float]] = mapped_column(Embedding)
    created_at: Mapped[datetime] = mapped_column(Timestamp, server_default=NOW)


class Theme(StdColumns, Base):
    __tablename__ = "themes"
    __table_args__ = std_args(
        "themes",
        check("themes", "name_length", "char_length(name) BETWEEN 1 AND 60"),
        check("themes", "description_length", "char_length(description) <= 200"),
        check_in("themes", "size_class", "normal", "small"),
        check_in("themes", "status", "active", "merged", "archived"),
        tenant_fk("themes", "merged_into", "themes"),
        tenant_fk("themes", "first_run_id", "analysis_runs"),
        tenant_fk("themes", "last_run_id", "analysis_runs"),
    )

    name: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    name_locked: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    size_class: Mapped[str] = mapped_column(Text, server_default=text("'normal'"))
    status: Mapped[str] = mapped_column(Text, server_default=text("'active'"))
    merged_into: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    centroid: Mapped[list[float] | None] = mapped_column(Embedding)
    first_run_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    last_run_id: Mapped[uuid.UUID] = mapped_column(Uuid)


class ThemeMembership(StdColumns, Base):
    __tablename__ = "theme_memberships"
    __table_args__ = std_args(
        "theme_memberships",
        unique("theme_memberships", "run_record", "analysis_run_id", "record_id"),
        check_in("theme_memberships", "source", "cluster", "override"),
        tenant_fk("theme_memberships", "analysis_run_id", "analysis_runs", ondelete="CASCADE"),
        tenant_fk("theme_memberships", "theme_id", "themes"),
        tenant_fk("theme_memberships", "record_id", "feedback_records"),
        Index("ix_theme_memberships_run_theme", "analysis_run_id", "theme_id"),
    )

    analysis_run_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    theme_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    record_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    source: Mapped[str] = mapped_column(Text, server_default=text("'cluster'"))
    probability: Mapped[float | None] = mapped_column(REAL)


class ThemeOverride(StdColumns, Base):
    __tablename__ = "theme_overrides"
    __table_args__ = std_args(
        "theme_overrides",
        check_in(
            "theme_overrides", "kind", "rename", "merge", "split", "pin_record", "exclude_record"
        ),
        tenant_fk("theme_overrides", "theme_id", "themes"),
        tenant_fk("theme_overrides", "target_theme_id", "themes"),
        tenant_fk("theme_overrides", "record_id", "feedback_records"),
        user_fk("theme_overrides", "created_by"),
    )

    kind: Mapped[str] = mapped_column(Text)
    theme_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    target_theme_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    record_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    payload: Mapped[dict[str, Any]] = mapped_column(Json, server_default=EMPTY_OBJECT)
    active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    created_by: Mapped[uuid.UUID] = mapped_column(Uuid)


class ThemeRunStats(StdColumns, Base):
    """Derived statistics per theme per run, written only by services (D07 §1)."""

    __tablename__ = "theme_run_stats"
    __table_args__ = std_args(
        "theme_run_stats",
        unique("theme_run_stats", "run_theme", "analysis_run_id", "theme_id"),
        check("theme_run_stats", "share", "share BETWEEN 0 AND 1"),
        check_in("theme_run_stats", "trend", "up", "flat", "down"),
        tenant_fk("theme_run_stats", "analysis_run_id", "analysis_runs", ondelete="CASCADE"),
        tenant_fk("theme_run_stats", "theme_id", "themes"),
    )

    analysis_run_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    theme_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    record_count: Mapped[int] = mapped_column(Integer)
    known_customers: Mapped[int] = mapped_column(Integer)
    unknown_identity_records: Mapped[int] = mapped_column(Integer)
    identity_coverage: Mapped[float] = mapped_column(REAL)
    share: Mapped[float] = mapped_column(REAL)
    sentiment: Mapped[dict[str, Any]] = mapped_column(Json)
    weekly: Mapped[list[Any]] = mapped_column(Json)
    trend: Mapped[str] = mapped_column(Text)
    top_customer_share: Mapped[float | None] = mapped_column(REAL)
    vocal_flag: Mapped[bool | None] = mapped_column(Boolean)  # NULL = not assessable (A-11)
    emerging: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    # Records CP-03 cited when naming the theme (migration 0003, IMP-33).
    cited_record_ids: Mapped[list[uuid.UUID]] = mapped_column(UuidArray, server_default=EMPTY_ARRAY)


class AggregatedRequest(StdColumns, Base):
    __tablename__ = "aggregated_requests"
    __table_args__ = std_args(
        "aggregated_requests",
        check_in("aggregated_requests", "status", "active", "merged", "archived"),
        tenant_fk("aggregated_requests", "merged_into", "aggregated_requests"),
        tenant_fk("aggregated_requests", "first_run_id", "analysis_runs"),
        tenant_fk("aggregated_requests", "last_run_id", "analysis_runs"),
    )

    title: Mapped[str] = mapped_column(Text)
    title_locked: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    status: Mapped[str] = mapped_column(Text, server_default=text("'active'"))
    merged_into: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    first_run_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    last_run_id: Mapped[uuid.UUID] = mapped_column(Uuid)


class RequestMembership(StdColumns, Base):
    __tablename__ = "request_memberships"
    __table_args__ = std_args(
        "request_memberships",
        unique("request_memberships", "run_record", "analysis_run_id", "record_id"),
        check(
            "request_memberships",
            "canonical_ask_words",
            r"cardinality(regexp_split_to_array(btrim(canonical_ask), '\s+')) <= 12",
        ),
        check_in("request_memberships", "source", "cluster", "override", "llm_split"),
        tenant_fk("request_memberships", "analysis_run_id", "analysis_runs", ondelete="CASCADE"),
        tenant_fk("request_memberships", "request_id", "aggregated_requests"),
        tenant_fk("request_memberships", "record_id", "feedback_records"),
    )

    analysis_run_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    request_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    record_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    canonical_ask: Mapped[str] = mapped_column(Text)  # at most 12 words
    source: Mapped[str] = mapped_column(Text, server_default=text("'cluster'"))
    low_confidence: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))


class ReviewItem(StdColumns, Base):
    __tablename__ = "review_items"
    __table_args__ = std_args(
        "review_items",
        check_in(
            "review_items",
            "kind",
            "low_confidence_label",
            "sarcasm",
            "borderline_request_pair",
            "spam_uncertain",
            "other",
        ),
        check_in("review_items", "status", "open", "resolved", "dismissed"),
        tenant_fk("review_items", "analysis_run_id", "analysis_runs"),
        tenant_fk("review_items", "record_id", "feedback_records"),
        user_fk("review_items", "resolved_by"),
        Index("ix_review_items_status_kind", "workspace_id", "status", "kind"),
    )

    analysis_run_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    record_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    kind: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict[str, Any]] = mapped_column(Json)
    status: Mapped[str] = mapped_column(Text, server_default=text("'open'"))
    resolution: Mapped[dict[str, Any] | None] = mapped_column(Json)
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    resolved_at: Mapped[datetime | None] = mapped_column(Timestamp)
