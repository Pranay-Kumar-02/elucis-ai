"""Sources and ingestion (D07 §3.2), plus ``jobs`` and ``integration_configs``, which the
ingestion tables reference (§3.11, §3.10)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, Index, Integer, SmallInteger, Text, Uuid, text
from sqlalchemy.dialects.postgresql import BYTEA
from sqlalchemy.orm import Mapped, mapped_column

from elucis.db.base import Base
from elucis.db.models._common import (
    EMPTY_OBJECT,
    NOW,
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

JOB_TYPES = (
    "ingest",
    "analysis",
    "generate_document",
    "suggest_inputs",
    "source_sync",
    "reembed",
    "reprocess",
    "jira_batch",
    "delete_import",
    "delete_workspace",
    "evaluation",
)
JOB_STATUSES = (
    "queued",
    "running",
    "retry_wait",
    "succeeded",
    "succeeded_with_errors",
    "failed",
    "cancelled",
)


class Job(StdColumns, Base):
    __tablename__ = "jobs"
    __table_args__ = std_args(
        "jobs",
        check_in("jobs", "job_type", *JOB_TYPES),
        check_in("jobs", "status", *JOB_STATUSES),
        user_fk("jobs", "created_by"),
        Index(
            "uq_jobs_idempotency_key",
            "workspace_id",
            "job_type",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
        ),
        Index(
            "ix_jobs_runnable",
            "status",
            "run_after",
            "priority",
            postgresql_where=text("status IN ('queued', 'retry_wait')"),
        ),
    )

    job_type: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default=text("'queued'"))
    priority: Mapped[int] = mapped_column(SmallInteger, server_default=text("5"))
    payload: Mapped[dict[str, Any]] = mapped_column(Json)
    cursor: Mapped[dict[str, Any]] = mapped_column(Json, server_default=EMPTY_OBJECT)
    progress: Mapped[dict[str, Any]] = mapped_column(Json, server_default=EMPTY_OBJECT)
    attempts: Mapped[int] = mapped_column(SmallInteger, server_default=text("0"))
    max_attempts: Mapped[int] = mapped_column(SmallInteger, server_default=text("3"))
    run_after: Mapped[datetime] = mapped_column(Timestamp, server_default=NOW)
    locked_by: Mapped[str | None] = mapped_column(Text)
    heartbeat_at: Mapped[datetime | None] = mapped_column(Timestamp)
    started_at: Mapped[datetime | None] = mapped_column(Timestamp)
    finished_at: Mapped[datetime | None] = mapped_column(Timestamp)
    error: Mapped[str | None] = mapped_column(Text)
    idempotency_key: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid)


class IntegrationConfig(StdColumns, Base):
    __tablename__ = "integration_configs"
    __table_args__ = std_args(
        "integration_configs",
        check_in(
            "integration_configs", "kind", "jira_rovo_mcp", "jira_selfhosted_mcp", "connector"
        ),
        check_in("integration_configs", "status", "not_configured", "healthy", "needs_attention"),
        user_fk("integration_configs", "configured_by"),
    )

    kind: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text)
    settings: Mapped[dict[str, Any]] = mapped_column(Json, server_default=EMPTY_OBJECT)
    credentials_encrypted: Mapped[bytes | None] = mapped_column(BYTEA)  # Fernet (AGR-16)
    status: Mapped[str] = mapped_column(Text, server_default=text("'not_configured'"))
    last_checked_at: Mapped[datetime | None] = mapped_column(Timestamp)
    configured_by: Mapped[uuid.UUID] = mapped_column(Uuid)


class DataSource(StdColumns, Base):
    __tablename__ = "data_sources"
    __table_args__ = std_args(
        "data_sources",
        unique("data_sources", "workspace_id_name", "workspace_id", "name"),
        check_in(
            "data_sources",
            "kind",
            "file",
            "google_play",
            "app_store",
            "zendesk",
            "mixpanel",
            "amplitude",
            "ms_graph_transcripts",
            "other",
        ),
        tenant_fk("data_sources", "integration_config_id", "integration_configs"),
    )

    kind: Mapped[str] = mapped_column(Text, server_default=text("'file'"))
    name: Mapped[str] = mapped_column(Text)
    integration_config_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    sync_state: Mapped[dict[str, Any]] = mapped_column(Json, server_default=EMPTY_OBJECT)
    enabled: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    last_synced_at: Mapped[datetime | None] = mapped_column(Timestamp)


class SourceFile(StdColumns, Base):
    __tablename__ = "source_files"
    __table_args__ = std_args(
        "source_files",
        unique("source_files", "storage_path", "storage_path"),
        check("source_files", "size_bytes", "size_bytes BETWEEN 0 AND 20971520"),
        check_in("source_files", "detected_format", "csv", "json", "txt"),
        tenant_fk("source_files", "data_source_id", "data_sources"),
        user_fk("source_files", "uploaded_by"),
        Index("ix_source_files_workspace_id_sha256", "workspace_id", "sha256"),
    )

    data_source_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    original_filename: Mapped[str] = mapped_column(Text)  # display only, never a path
    storage_path: Mapped[str] = mapped_column(Text)
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    sha256: Mapped[bytes] = mapped_column(BYTEA)
    detected_format: Mapped[str] = mapped_column(Text)
    detected_encoding: Mapped[str | None] = mapped_column(Text)
    uploaded_by: Mapped[uuid.UUID] = mapped_column(Uuid)


class ColumnMapping(StdColumns, Base):
    __tablename__ = "column_mappings"
    __table_args__ = std_args(
        "column_mappings",
        unique("column_mappings", "workspace_id_name", "workspace_id", "name"),
        check_in("column_mappings", "source_type", *SOURCE_TYPES),
        user_fk("column_mappings", "created_by"),
    )

    name: Mapped[str] = mapped_column(Text)
    source_type: Mapped[str] = mapped_column(Text)
    mapping: Mapped[dict[str, Any]] = mapped_column(Json)
    created_by: Mapped[uuid.UUID] = mapped_column(Uuid)


class ImportJob(StdColumns, Base):
    __tablename__ = "import_jobs"
    __table_args__ = std_args(
        "import_jobs",
        check_in("import_jobs", "source_type", *SOURCE_TYPES),
        check_in(
            "import_jobs",
            "status",
            "queued",
            "processing",
            "completed",
            "completed_with_errors",
            "failed",
            "cancelled",
        ),
        tenant_fk("import_jobs", "data_source_id", "data_sources"),
        tenant_fk("import_jobs", "source_file_id", "source_files"),
        tenant_fk("import_jobs", "job_id", "jobs"),
        user_fk("import_jobs", "submitted_by"),
    )

    data_source_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    source_file_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    source_type: Mapped[str] = mapped_column(Text)
    column_mapping: Mapped[dict[str, Any]] = mapped_column(Json)
    status: Mapped[str] = mapped_column(Text, server_default=text("'queued'"))
    job_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    report: Mapped[dict[str, Any] | None] = mapped_column(Json)
    submitted_by: Mapped[uuid.UUID] = mapped_column(Uuid)
    started_at: Mapped[datetime | None] = mapped_column(Timestamp)
    finished_at: Mapped[datetime | None] = mapped_column(Timestamp)


class ImportRowError(StdColumns, Base):
    __tablename__ = "import_row_errors"
    __table_args__ = std_args(
        "import_row_errors",
        check_in("import_row_errors", "kind", "rejected", "failed"),
        check_in(
            "import_row_errors",
            "stage",
            "validation",
            "cleaning",
            "noise",
            "standardisation",
            "pii",
            "language",
            "duplicate",
            "spam",
            "other",
        ),
        tenant_fk("import_row_errors", "import_job_id", "import_jobs", ondelete="CASCADE"),
        Index("ix_import_row_errors_import_job_id_kind", "workspace_id", "import_job_id", "kind"),
    )

    import_job_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    row_number: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(Text)
    stage: Mapped[str] = mapped_column(Text)
    field: Mapped[str | None] = mapped_column(Text)
    code: Mapped[str] = mapped_column(Text)
    message: Mapped[str] = mapped_column(Text)
