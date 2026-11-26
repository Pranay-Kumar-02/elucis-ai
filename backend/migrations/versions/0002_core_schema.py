"""Core schema: the 54 tables of D07/D08, row-level security and role grants.

Hand-written DDL, grouped by D07 section. This file never imports the ORM models, so it
stays a frozen record of the schema at this revision; ``tests/test_schema_drift.py`` proves
the models match it.

Conventions (D07 sections 1-2, FOUNDATION_NOTES IMP-22 and IMP-23):

* STD tables: ``id``, ``workspace_id`` (cascade from ``workspaces``), ``created_at`` and
  ``UNIQUE (workspace_id, id)``; references between tenant tables are composite
  ``(workspace_id, x_id)`` foreign keys, so a cross-workspace reference cannot be stored.
* Unspecified ``ON DELETE`` behaviour is NO ACTION. It is checked at the end of the
  statement, so deleting a workspace still cascades through everything.
* Row-level security is enabled and forced on the 48 tenant tables. The six identity and
  global tables (users, sessions, login_attempts, prompt_versions, workspaces,
  workspace_memberships) are reached only through SVC-01 and the model gateway (D07 §5).
* Every privilege is granted explicitly per table, independent of default privileges.

Downgrade drops every object created here and destroys their data: development and test
databases only.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-26
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLES = "app_api, app_worker"
CURRENT_EMBEDDING_MODEL = "qwen3-embedding:0.6b"  # F-02: measured dimension 1024
WORKSPACE = "nullif(current_setting('app.workspace_id', true), '')::uuid"


# ---------------------------------------------------------------- DDL helpers
def _std(name: str, body: str) -> str:
    """CREATE TABLE with the D07 STD columns, key, tenant unique key and workspace FK."""
    return f"""
CREATE TABLE {name} (
    id           uuid        NOT NULL DEFAULT gen_random_uuid(),
    workspace_id uuid        NOT NULL,
    created_at   timestamptz NOT NULL DEFAULT now(),
    {body},
    CONSTRAINT pk_{name} PRIMARY KEY (id),
    CONSTRAINT uq_{name}_workspace_id_id UNIQUE (workspace_id, id),
    CONSTRAINT fk_{name}_workspace_id FOREIGN KEY (workspace_id)
        REFERENCES workspaces (id) ON DELETE CASCADE
)"""


def _ref(table: str, column: str, target: str, action: str = "") -> str:
    """Composite tenant FK (workspace_id, column) -> target (workspace_id, id)."""
    on_delete = {
        "": "",
        "cascade": " ON DELETE CASCADE",
        "set null": f" ON DELETE SET NULL ({column})",
    }[action]
    return (
        f"CONSTRAINT fk_{table}_{column} FOREIGN KEY (workspace_id, {column}) "
        f"REFERENCES {target} (workspace_id, id){on_delete}"
    )


def _user(table: str, column: str) -> str:
    return f"CONSTRAINT fk_{table}_{column} FOREIGN KEY ({column}) REFERENCES users (id)"


def _in(table: str, column: str, *values: str) -> str:
    listed = ", ".join(f"'{v}'" for v in values)
    return f"CONSTRAINT ck_{table}_{column} CHECK ({column} IN ({listed}))"


SOURCE_TYPES = ("review", "ticket", "feature_request", "transcript", "other", "metrics")


# ---------------------------------------------------------------- 3.1 identity
IDENTITY = [
    """
CREATE FUNCTION reject_raw_text_update() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.raw_text IS DISTINCT FROM OLD.raw_text THEN
        RAISE EXCEPTION 'feedback_records.raw_text is immutable (DR-35)'
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END
$$""",
    """
CREATE TABLE users (
    id            uuid        NOT NULL DEFAULT gen_random_uuid(),
    email         text        NOT NULL,
    password_hash text        NOT NULL,
    display_name  text,
    is_active     boolean     NOT NULL DEFAULT true,
    created_at    timestamptz NOT NULL DEFAULT now(),
    last_login_at timestamptz,
    CONSTRAINT pk_users PRIMARY KEY (id)
)""",
    "CREATE UNIQUE INDEX uq_users_email_lower ON users (lower(email))",
    """
CREATE TABLE sessions (
    id              uuid        NOT NULL DEFAULT gen_random_uuid(),
    user_id         uuid        NOT NULL,
    token_hash      bytea       NOT NULL,
    csrf_token_hash bytea       NOT NULL,
    created_at      timestamptz NOT NULL DEFAULT now(),
    last_seen_at    timestamptz NOT NULL DEFAULT now(),
    expires_at      timestamptz NOT NULL,
    ip              inet,
    user_agent      text,
    CONSTRAINT pk_sessions PRIMARY KEY (id),
    CONSTRAINT uq_sessions_token_hash UNIQUE (token_hash),
    CONSTRAINT fk_sessions_user_id FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
)""",
    "CREATE INDEX ix_sessions_user_id ON sessions (user_id)",
    "CREATE INDEX ix_sessions_expires_at ON sessions (expires_at)",
    """
CREATE TABLE login_attempts (
    id           bigint      GENERATED ALWAYS AS IDENTITY,
    email_lower  text        NOT NULL,
    ip           inet,
    succeeded    boolean     NOT NULL,
    attempted_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT pk_login_attempts PRIMARY KEY (id)
)""",
    "CREATE INDEX ix_login_attempts_email_lower_attempted_at"
    " ON login_attempts (email_lower, attempted_at DESC)",
    """
CREATE TABLE workspaces (
    id                      uuid        NOT NULL DEFAULT gen_random_uuid(),
    name                    text        NOT NULL,
    description             text,
    product_name            text,
    product_description     text,
    target_users            text,
    glossary                jsonb       NOT NULL DEFAULT '{}',
    customer_key_secret     bytea       NOT NULL,
    current_analysis_run_id uuid,
    created_by              uuid        NOT NULL,
    created_at              timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT pk_workspaces PRIMARY KEY (id),
    CONSTRAINT ck_workspaces_name_length CHECK (char_length(name) BETWEEN 1 AND 120),
    CONSTRAINT fk_workspaces_created_by FOREIGN KEY (created_by) REFERENCES users (id)
)""",
    f"""
CREATE TABLE workspace_memberships (
    workspace_id uuid        NOT NULL,
    user_id      uuid        NOT NULL,
    role         text        NOT NULL DEFAULT 'viewer',
    added_by     uuid,
    created_at   timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT pk_workspace_memberships PRIMARY KEY (workspace_id, user_id),
    {_in("workspace_memberships", "role", "owner", "editor", "viewer")},
    CONSTRAINT fk_workspace_memberships_workspace_id FOREIGN KEY (workspace_id)
        REFERENCES workspaces (id) ON DELETE CASCADE,
    CONSTRAINT fk_workspace_memberships_user_id FOREIGN KEY (user_id)
        REFERENCES users (id) ON DELETE CASCADE,
    {_user("workspace_memberships", "added_by")}
)""",
]

# ---------------------------------------------------------------- 3.2 sources, ingestion
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

INGESTION = [
    _std(
        "jobs",
        f"""job_type        text        NOT NULL,
    status          text        NOT NULL DEFAULT 'queued',
    priority        smallint    NOT NULL DEFAULT 5,
    payload         jsonb       NOT NULL,
    cursor          jsonb       NOT NULL DEFAULT '{{}}',
    progress        jsonb       NOT NULL DEFAULT '{{}}',
    attempts        smallint    NOT NULL DEFAULT 0,
    max_attempts    smallint    NOT NULL DEFAULT 3,
    run_after       timestamptz NOT NULL DEFAULT now(),
    locked_by       text,
    heartbeat_at    timestamptz,
    started_at      timestamptz,
    finished_at     timestamptz,
    error           text,
    idempotency_key text,
    created_by      uuid,
    {_in("jobs", "job_type", *JOB_TYPES)},
    {_in("jobs", "status", *JOB_STATUSES)},
    {_user("jobs", "created_by")}""",
    ),
    "CREATE UNIQUE INDEX uq_jobs_idempotency_key ON jobs (workspace_id, job_type, idempotency_key)"
    " WHERE idempotency_key IS NOT NULL",
    "CREATE INDEX ix_jobs_runnable ON jobs (status, run_after, priority)"
    " WHERE status IN ('queued', 'retry_wait')",
    _std(
        "integration_configs",
        f"""kind                  text NOT NULL,
    name                  text NOT NULL,
    settings              jsonb NOT NULL DEFAULT '{{}}',
    credentials_encrypted bytea,
    status                text NOT NULL DEFAULT 'not_configured',
    last_checked_at       timestamptz,
    configured_by         uuid NOT NULL,
    {_in("integration_configs", "kind", "jira_rovo_mcp", "jira_selfhosted_mcp", "connector")},
    {_in("integration_configs", "status", "not_configured", "healthy", "needs_attention")},
    {_user("integration_configs", "configured_by")}""",
    ),
    _std(
        "data_sources",
        f"""kind                  text    NOT NULL DEFAULT 'file',
    name                  text    NOT NULL,
    integration_config_id uuid,
    sync_state            jsonb   NOT NULL DEFAULT '{{}}',
    enabled               boolean NOT NULL DEFAULT true,
    last_synced_at        timestamptz,
    CONSTRAINT uq_data_sources_workspace_id_name UNIQUE (workspace_id, name),
    {
            _in(
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
            )
        },
    {_ref("data_sources", "integration_config_id", "integration_configs")}""",
    ),
    _std(
        "source_files",
        f"""data_source_id    uuid   NOT NULL,
    original_filename text   NOT NULL,
    storage_path      text   NOT NULL,
    size_bytes        bigint NOT NULL,
    sha256            bytea  NOT NULL,
    detected_format   text   NOT NULL,
    detected_encoding text,
    uploaded_by       uuid   NOT NULL,
    CONSTRAINT uq_source_files_storage_path UNIQUE (storage_path),
    CONSTRAINT ck_source_files_size_bytes CHECK (size_bytes BETWEEN 0 AND 20971520),
    {_in("source_files", "detected_format", "csv", "json", "txt")},
    {_ref("source_files", "data_source_id", "data_sources")},
    {_user("source_files", "uploaded_by")}""",
    ),
    "CREATE INDEX ix_source_files_workspace_id_sha256 ON source_files (workspace_id, sha256)",
    _std(
        "column_mappings",
        f"""name        text  NOT NULL,
    source_type text  NOT NULL,
    mapping     jsonb NOT NULL,
    created_by  uuid  NOT NULL,
    CONSTRAINT uq_column_mappings_workspace_id_name UNIQUE (workspace_id, name),
    {_in("column_mappings", "source_type", *SOURCE_TYPES)},
    {_user("column_mappings", "created_by")}""",
    ),
    _std(
        "import_jobs",
        f"""data_source_id uuid  NOT NULL,
    source_file_id uuid,
    source_type    text  NOT NULL,
    column_mapping jsonb NOT NULL,
    status         text  NOT NULL DEFAULT 'queued',
    job_id         uuid,
    report         jsonb,
    submitted_by   uuid  NOT NULL,
    started_at     timestamptz,
    finished_at    timestamptz,
    {_in("import_jobs", "source_type", *SOURCE_TYPES)},
    {
            _in(
                "import_jobs",
                "status",
                "queued",
                "processing",
                "completed",
                "completed_with_errors",
                "failed",
                "cancelled",
            )
        },
    {_ref("import_jobs", "data_source_id", "data_sources")},
    {_ref("import_jobs", "source_file_id", "source_files")},
    {_ref("import_jobs", "job_id", "jobs")},
    {_user("import_jobs", "submitted_by")}""",
    ),
    _std(
        "import_row_errors",
        f"""import_job_id uuid    NOT NULL,
    row_number    integer NOT NULL,
    kind          text    NOT NULL,
    stage         text    NOT NULL,
    field         text,
    code          text    NOT NULL,
    message       text    NOT NULL,
    {_in("import_row_errors", "kind", "rejected", "failed")},
    {
            _in(
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
            )
        },
    {_ref("import_row_errors", "import_job_id", "import_jobs", "cascade")}""",
    ),
    "CREATE INDEX ix_import_row_errors_import_job_id_kind"
    " ON import_row_errors (workspace_id, import_job_id, kind)",
]

# ---------------------------------------------------------------- 3.3 feedback
FEEDBACK = [
    _std(
        "customers",
        """customer_key  bytea NOT NULL,
    first_seen_at timestamptz,
    last_seen_at  timestamptz,
    CONSTRAINT uq_customers_workspace_id_customer_key UNIQUE (workspace_id, customer_key)""",
    ),
    _std(
        "feedback_records",
        f"""import_job_id       uuid     NOT NULL,
    row_number          integer  NOT NULL,
    segment_index       integer  NOT NULL DEFAULT 0,
    parent_record_id    uuid,
    source_type         text     NOT NULL,
    source_record_id    text,
    raw_text            text     NOT NULL,
    processed_text      text,
    content_hash        bytea,
    customer_id         uuid,
    speaker             text,
    occurred_at         timestamptz,
    occurred_at_missing boolean  NOT NULL DEFAULT false,
    rating              smallint,
    rating_raw          text,
    product_version     text,
    language            text,
    stage               text     NOT NULL DEFAULT 'captured',
    analysable          boolean  NOT NULL DEFAULT false,
    exclusion_reason    text,
    duplicate_of        uuid,
    spam_score          real,
    spam_reason         text,
    spam_status         text     NOT NULL DEFAULT 'not_checked',
    pii_counts          jsonb    NOT NULL DEFAULT '{{}}',
    flag_overridden_by  uuid,
    critical_signal     boolean  NOT NULL DEFAULT false,
    metadata            jsonb    NOT NULL DEFAULT '{{}}',
    search_tsv          tsvector GENERATED ALWAYS AS
        (to_tsvector('english'::regconfig, coalesce(processed_text, ''))) STORED,
    CONSTRAINT uq_feedback_records_import_row
        UNIQUE (workspace_id, import_job_id, row_number, segment_index),
    {_in("feedback_records", "source_type", *SOURCE_TYPES)},
    CONSTRAINT ck_feedback_records_rating CHECK (rating BETWEEN 1 AND 5),
    {
            _in(
                "feedback_records",
                "stage",
                "captured",
                "cleaned",
                "standardised",
                "masked",
                "prepared",
                "failed",
            )
        },
    {
            _in(
                "feedback_records",
                "exclusion_reason",
                "noise",
                "pii_failed",
                "non_english",
                "duplicate",
                "spam",
                "spam_review",
            )
        },
    {
            _in(
                "feedback_records",
                "spam_status",
                "not_checked",
                "clean",
                "spam",
                "review_required",
            )
        },
    CONSTRAINT ck_feedback_records_analysable_not_excluded
        CHECK (NOT analysable OR exclusion_reason IS NULL),
    CONSTRAINT ck_feedback_records_duplicate_reason
        CHECK (duplicate_of IS NULL OR exclusion_reason IS NOT DISTINCT FROM 'duplicate'),
    CONSTRAINT ck_feedback_records_spam_review_status
        CHECK (exclusion_reason IS DISTINCT FROM 'spam_review' OR spam_status = 'review_required'),
    CONSTRAINT ck_feedback_records_analysable_prepared
        CHECK (NOT analysable OR stage = 'prepared'),
    {_ref("feedback_records", "import_job_id", "import_jobs")},
    {_ref("feedback_records", "parent_record_id", "feedback_records")},
    {_ref("feedback_records", "customer_id", "customers")},
    {_ref("feedback_records", "duplicate_of", "feedback_records")},
    {_user("feedback_records", "flag_overridden_by")}""",
    ),
    "CREATE INDEX ix_feedback_records_analysable_occurred_at"
    " ON feedback_records (workspace_id, analysable, occurred_at)",
    "CREATE INDEX ix_feedback_records_content_hash ON feedback_records (workspace_id, content_hash)",
    "CREATE INDEX ix_feedback_records_customer_id ON feedback_records (workspace_id, customer_id)",
    "CREATE INDEX ix_feedback_records_import_job_id"
    " ON feedback_records (workspace_id, import_job_id)",
    "CREATE INDEX ix_feedback_records_search_tsv ON feedback_records USING gin (search_tsv)",
    "CREATE TRIGGER trg_feedback_records_raw_text_immutable"
    " BEFORE UPDATE OF raw_text ON feedback_records"
    " FOR EACH ROW EXECUTE FUNCTION reject_raw_text_update()",
]

# ---------------------------------------------------------------- 3.4 AI analysis
ANALYSIS = [
    """
CREATE TABLE prompt_versions (
    id            uuid        NOT NULL DEFAULT gen_random_uuid(),
    call_id       text        NOT NULL,
    version       text        NOT NULL,
    content_hash  bytea       NOT NULL,
    template      text        NOT NULL,
    output_schema jsonb,
    examples      jsonb       NOT NULL DEFAULT '[]',
    created_at    timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT pk_prompt_versions PRIMARY KEY (id),
    CONSTRAINT uq_prompt_versions_call_id_version UNIQUE (call_id, version)
)""",
    f"""
CREATE TABLE llm_call_records (
    id                bigint      GENERATED ALWAYS AS IDENTITY,
    workspace_id      uuid        NOT NULL,
    call_id           text        NOT NULL,
    model_tag         text        NOT NULL,
    prompt_version_id uuid,
    input_hash        bytea       NOT NULL,
    prompt_tokens     integer,
    output_tokens     integer,
    prompt_eval_ms    integer,
    eval_ms           integer,
    total_ms          integer,
    attempt           smallint    NOT NULL DEFAULT 1,
    outcome           text        NOT NULL,
    job_id            uuid,
    created_at        timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT pk_llm_call_records PRIMARY KEY (id),
    CONSTRAINT uq_llm_call_records_workspace_id_id UNIQUE (workspace_id, id),
    {_in("llm_call_records", "outcome", "ok", "invalid_output", "timeout", "error")},
    CONSTRAINT fk_llm_call_records_workspace_id FOREIGN KEY (workspace_id)
        REFERENCES workspaces (id) ON DELETE CASCADE,
    CONSTRAINT fk_llm_call_records_prompt_version_id FOREIGN KEY (prompt_version_id)
        REFERENCES prompt_versions (id),
    {_ref("llm_call_records", "job_id", "jobs")}
)""",
    "CREATE INDEX ix_llm_call_records_workspace_id_created_at"
    " ON llm_call_records (workspace_id, created_at)",
    "CREATE INDEX ix_llm_call_records_input_hash_prompt_version_id"
    " ON llm_call_records (input_hash, prompt_version_id)",
    _std(
        "analysis_runs",
        f"""status             text  NOT NULL DEFAULT 'queued',
    config             jsonb NOT NULL,
    config_hash        text  NOT NULL,
    embedding_model_id text  NOT NULL,
    previous_run_id    uuid,
    job_id             uuid,
    triggered_by       uuid,
    report             jsonb,
    started_at         timestamptz,
    finished_at        timestamptz,
    {_in("analysis_runs", "status", "queued", "running", "succeeded", "failed", "cancelled")},
    {_ref("analysis_runs", "previous_run_id", "analysis_runs")},
    {_ref("analysis_runs", "job_id", "jobs")},
    {_user("analysis_runs", "triggered_by")}""",
    ),
    """
ALTER TABLE workspaces ADD CONSTRAINT fk_workspaces_current_analysis_run_id
    FOREIGN KEY (id, current_analysis_run_id) REFERENCES analysis_runs (workspace_id, id)
    ON DELETE SET NULL (current_analysis_run_id) DEFERRABLE INITIALLY DEFERRED""",
    _std(
        "record_classifications",
        f"""analysis_run_id   uuid    NOT NULL,
    record_id         uuid    NOT NULL,
    status            text    NOT NULL DEFAULT 'classified',
    near_duplicate_of uuid,
    category          text,
    sentiment         text,
    sarcasm           boolean NOT NULL DEFAULT false,
    method            text,
    confidence        real,
    calibrated        boolean NOT NULL DEFAULT false,
    llm_call_id       bigint,
    CONSTRAINT uq_record_classifications_run_record UNIQUE (analysis_run_id, record_id),
    {
            _in(
                "record_classifications",
                "status",
                "classified",
                "near_duplicate",
                "unclassified",
                "embedding_failed",
            )
        },
    {
            _in(
                "record_classifications",
                "category",
                "bug_report",
                "feature_request",
                "usability_issue",
                "performance_issue",
                "praise",
                "question",
                "other",
            )
        },
    {_in("record_classifications", "sentiment", "positive", "neutral", "negative", "mixed")},
    {_in("record_classifications", "method", "classifier", "llm", "human")},
    CONSTRAINT ck_record_classifications_confidence CHECK (confidence BETWEEN 0 AND 1),
    CONSTRAINT ck_record_classifications_classified_fields CHECK (status <> 'classified'
        OR (category IS NOT NULL AND sentiment IS NOT NULL AND method IS NOT NULL)),
    CONSTRAINT ck_record_classifications_near_duplicate_link
        CHECK ((status = 'near_duplicate') = (near_duplicate_of IS NOT NULL)),
    {_ref("record_classifications", "analysis_run_id", "analysis_runs", "cascade")},
    {_ref("record_classifications", "record_id", "feedback_records")},
    {_ref("record_classifications", "near_duplicate_of", "feedback_records")},
    {_ref("record_classifications", "llm_call_id", "llm_call_records", "set null")}""",
    ),
    "CREATE INDEX ix_record_classifications_run_status_category"
    " ON record_classifications (workspace_id, analysis_run_id, status, category)",
    f"""
CREATE TABLE record_embeddings (
    workspace_id uuid         NOT NULL,
    record_id    uuid         NOT NULL,
    model_id     text         NOT NULL,
    embedding    vector(1024) NOT NULL,
    created_at   timestamptz  NOT NULL DEFAULT now(),
    CONSTRAINT pk_record_embeddings PRIMARY KEY (workspace_id, record_id, model_id),
    CONSTRAINT fk_record_embeddings_workspace_id FOREIGN KEY (workspace_id)
        REFERENCES workspaces (id) ON DELETE CASCADE,
    {_ref("record_embeddings", "record_id", "feedback_records", "cascade")}
)""",
    "CREATE INDEX ix_record_embeddings_embedding_hnsw ON record_embeddings"
    f" USING hnsw (embedding vector_cosine_ops) WHERE model_id = '{CURRENT_EMBEDDING_MODEL}'",
    _std(
        "themes",
        f"""name         text    NOT NULL,
    description  text,
    name_locked  boolean NOT NULL DEFAULT false,
    size_class   text    NOT NULL DEFAULT 'normal',
    status       text    NOT NULL DEFAULT 'active',
    merged_into  uuid,
    centroid     vector(1024),
    first_run_id uuid    NOT NULL,
    last_run_id  uuid    NOT NULL,
    CONSTRAINT ck_themes_name_length CHECK (char_length(name) BETWEEN 1 AND 60),
    CONSTRAINT ck_themes_description_length CHECK (char_length(description) <= 200),
    {_in("themes", "size_class", "normal", "small")},
    {_in("themes", "status", "active", "merged", "archived")},
    {_ref("themes", "merged_into", "themes")},
    {_ref("themes", "first_run_id", "analysis_runs")},
    {_ref("themes", "last_run_id", "analysis_runs")}""",
    ),
    _std(
        "theme_memberships",
        f"""analysis_run_id uuid NOT NULL,
    theme_id        uuid NOT NULL,
    record_id       uuid NOT NULL,
    source          text NOT NULL DEFAULT 'cluster',
    probability     real,
    CONSTRAINT uq_theme_memberships_run_record UNIQUE (analysis_run_id, record_id),
    {_in("theme_memberships", "source", "cluster", "override")},
    {_ref("theme_memberships", "analysis_run_id", "analysis_runs", "cascade")},
    {_ref("theme_memberships", "theme_id", "themes")},
    {_ref("theme_memberships", "record_id", "feedback_records")}""",
    ),
    "CREATE INDEX ix_theme_memberships_run_theme ON theme_memberships (analysis_run_id, theme_id)",
    _std(
        "theme_overrides",
        f"""kind            text    NOT NULL,
    theme_id        uuid    NOT NULL,
    target_theme_id uuid,
    record_id       uuid,
    payload         jsonb   NOT NULL DEFAULT '{{}}',
    active          boolean NOT NULL DEFAULT true,
    created_by      uuid    NOT NULL,
    {
            _in(
                "theme_overrides",
                "kind",
                "rename",
                "merge",
                "split",
                "pin_record",
                "exclude_record",
            )
        },
    {_ref("theme_overrides", "theme_id", "themes")},
    {_ref("theme_overrides", "target_theme_id", "themes")},
    {_ref("theme_overrides", "record_id", "feedback_records")},
    {_user("theme_overrides", "created_by")}""",
    ),
    _std(
        "theme_run_stats",
        f"""analysis_run_id          uuid    NOT NULL,
    theme_id                 uuid    NOT NULL,
    record_count             integer NOT NULL,
    known_customers          integer NOT NULL,
    unknown_identity_records integer NOT NULL,
    identity_coverage        real    NOT NULL,
    share                    real    NOT NULL,
    sentiment                jsonb   NOT NULL,
    weekly                   jsonb   NOT NULL,
    trend                    text    NOT NULL,
    top_customer_share       real,
    vocal_flag               boolean,
    emerging                 boolean NOT NULL DEFAULT false,
    CONSTRAINT uq_theme_run_stats_run_theme UNIQUE (analysis_run_id, theme_id),
    CONSTRAINT ck_theme_run_stats_share CHECK (share BETWEEN 0 AND 1),
    {_in("theme_run_stats", "trend", "up", "flat", "down")},
    {_ref("theme_run_stats", "analysis_run_id", "analysis_runs", "cascade")},
    {_ref("theme_run_stats", "theme_id", "themes")}""",
    ),
    _std(
        "aggregated_requests",
        f"""title        text    NOT NULL,
    title_locked boolean NOT NULL DEFAULT false,
    status       text    NOT NULL DEFAULT 'active',
    merged_into  uuid,
    first_run_id uuid    NOT NULL,
    last_run_id  uuid    NOT NULL,
    {_in("aggregated_requests", "status", "active", "merged", "archived")},
    {_ref("aggregated_requests", "merged_into", "aggregated_requests")},
    {_ref("aggregated_requests", "first_run_id", "analysis_runs")},
    {_ref("aggregated_requests", "last_run_id", "analysis_runs")}""",
    ),
    _std(
        "request_memberships",
        rf"""analysis_run_id uuid    NOT NULL,
    request_id      uuid    NOT NULL,
    record_id       uuid    NOT NULL,
    canonical_ask   text    NOT NULL,
    source          text    NOT NULL DEFAULT 'cluster',
    low_confidence  boolean NOT NULL DEFAULT false,
    CONSTRAINT uq_request_memberships_run_record UNIQUE (analysis_run_id, record_id),
    CONSTRAINT ck_request_memberships_canonical_ask_words
        CHECK (cardinality(regexp_split_to_array(btrim(canonical_ask), '\s+')) <= 12),
    {_in("request_memberships", "source", "cluster", "override", "llm_split")},
    {_ref("request_memberships", "analysis_run_id", "analysis_runs", "cascade")},
    {_ref("request_memberships", "request_id", "aggregated_requests")},
    {_ref("request_memberships", "record_id", "feedback_records")}""",
    ),
    _std(
        "review_items",
        f"""analysis_run_id uuid,
    record_id       uuid,
    kind            text  NOT NULL,
    payload         jsonb NOT NULL,
    status          text  NOT NULL DEFAULT 'open',
    resolution      jsonb,
    resolved_by     uuid,
    resolved_at     timestamptz,
    {
            _in(
                "review_items",
                "kind",
                "low_confidence_label",
                "sarcasm",
                "borderline_request_pair",
                "spam_uncertain",
                "other",
            )
        },
    {_in("review_items", "status", "open", "resolved", "dismissed")},
    {_ref("review_items", "analysis_run_id", "analysis_runs")},
    {_ref("review_items", "record_id", "feedback_records")},
    {_user("review_items", "resolved_by")}""",
    ),
    "CREATE INDEX ix_review_items_status_kind ON review_items (workspace_id, status, kind)",
]

# ---------------------------------------------------------------- 3.5 analytics
ANALYTICS = [
    _std(
        "metric_definitions",
        f"""name        text NOT NULL,
    unit        text,
    aggregation text NOT NULL DEFAULT 'sum',
    description text,
    {_in("metric_definitions", "aggregation", "sum", "avg", "last")}""",
    ),
    "CREATE UNIQUE INDEX uq_metric_definitions_name_lower"
    " ON metric_definitions (workspace_id, lower(name))",
    _std(
        "metric_observations",
        f"""metric_id     uuid             NOT NULL,
    observed_on   date             NOT NULL,
    dimension     text             NOT NULL DEFAULT '',
    value         double precision NOT NULL,
    import_job_id uuid,
    CONSTRAINT uq_metric_observations_metric_day_dimension
        UNIQUE (workspace_id, metric_id, observed_on, dimension),
    {_ref("metric_observations", "metric_id", "metric_definitions")},
    {_ref("metric_observations", "import_job_id", "import_jobs")}""",
    ),
    _std(
        "product_releases",
        """version     text NOT NULL,
    released_on date NOT NULL,
    notes       text,
    CONSTRAINT uq_product_releases_workspace_id_version UNIQUE (workspace_id, version)""",
    ),
    "CREATE INDEX ix_product_releases_released_on"
    " ON product_releases (workspace_id, released_on DESC)",
    _std(
        "theme_metric_links",
        f"""theme_id          uuid,
    request_id        uuid,
    metric_id         uuid    NOT NULL,
    expected_relation text    NOT NULL,
    origin            text    NOT NULL,
    accepted          boolean NOT NULL DEFAULT false,
    CONSTRAINT ck_theme_metric_links_one_subject CHECK ((theme_id IS NULL) <> (request_id IS NULL)),
    {_in("theme_metric_links", "expected_relation", "positive", "negative")},
    {_in("theme_metric_links", "origin", "person", "system_suggestion")},
    {_ref("theme_metric_links", "theme_id", "themes")},
    {_ref("theme_metric_links", "request_id", "aggregated_requests")},
    {_ref("theme_metric_links", "metric_id", "metric_definitions")}""",
    ),
]

# ---------------------------------------------------------------- 3.6 prioritisation
PRIORITISATION = [
    _std(
        "scoring_configs",
        f"""framework           text    NOT NULL,
    impact_scale        jsonb   NOT NULL,
    confidence_rules    jsonb   NOT NULL,
    lane_capacity_weeks real    NOT NULL DEFAULT 6,
    version             integer NOT NULL DEFAULT 1,
    is_active           boolean NOT NULL DEFAULT false,
    {_in("scoring_configs", "framework", "rice", "ice")}""",
    ),
    "CREATE UNIQUE INDEX uq_scoring_configs_active ON scoring_configs (workspace_id)"
    " WHERE is_active",
    _std(
        "opportunities",
        f"""source_kind     text NOT NULL,
    theme_id        uuid,
    request_id      uuid,
    title           text NOT NULL,
    description     text,
    status          text NOT NULL DEFAULT 'open',
    decision_reason text,
    decided_by      uuid,
    decided_at      timestamptz,
    {_in("opportunities", "source_kind", "theme", "request")},
    {_in("opportunities", "status", "open", "accepted", "deferred", "rejected")},
    CONSTRAINT ck_opportunities_one_source CHECK ((theme_id IS NULL) <> (request_id IS NULL)),
    CONSTRAINT ck_opportunities_source_matches_kind
        CHECK ((source_kind = 'theme') = (theme_id IS NOT NULL)),
    {_ref("opportunities", "theme_id", "themes")},
    {_ref("opportunities", "request_id", "aggregated_requests")},
    {_user("opportunities", "decided_by")}""",
    ),
    "CREATE UNIQUE INDEX uq_opportunities_theme ON opportunities (workspace_id, theme_id)"
    " WHERE theme_id IS NOT NULL",
    "CREATE UNIQUE INDEX uq_opportunities_request ON opportunities (workspace_id, request_id)"
    " WHERE request_id IS NOT NULL",
    _std(
        "score_inputs",
        f"""opportunity_id uuid    NOT NULL,
    framework      text,
    input_name     text    NOT NULL,
    value          numeric NOT NULL,
    origin         text    NOT NULL,
    rationale      text,
    evidence_ids   uuid[]  NOT NULL DEFAULT '{{}}',
    llm_call_id    bigint,
    set_by         uuid,
    is_current     boolean NOT NULL DEFAULT true,
    superseded_at  timestamptz,
    {_in("score_inputs", "framework", "rice", "ice")},
    {_in("score_inputs", "input_name", "reach", "impact", "confidence", "effort", "ease")},
    {_in("score_inputs", "origin", "data", "ai", "person")},
    CONSTRAINT ck_score_inputs_framework_or_effort
        CHECK (framework IS NOT NULL OR input_name = 'effort'),
    CONSTRAINT ck_score_inputs_ai_rationale CHECK (origin <> 'ai' OR rationale IS NOT NULL),
    {_ref("score_inputs", "opportunity_id", "opportunities", "cascade")},
    {_ref("score_inputs", "llm_call_id", "llm_call_records", "set null")},
    {_user("score_inputs", "set_by")}""",
    ),
    "CREATE UNIQUE INDEX uq_score_inputs_current"
    " ON score_inputs (opportunity_id, coalesce(framework, '-'), input_name) WHERE is_current",
    _std(
        "score_snapshots",
        f"""scoring_config_id uuid        NOT NULL,
    config_hash       text        NOT NULL,
    ranking           jsonb       NOT NULL,
    trigger           text        NOT NULL,
    computed_at       timestamptz NOT NULL DEFAULT now(),
    {_in("score_snapshots", "trigger", "recompute", "input_change", "config_change")},
    {_ref("score_snapshots", "scoring_config_id", "scoring_configs")}""",
    ),
]

# ---------------------------------------------------------------- 3.7 documents
DOCUMENTS = [
    _std(
        "documents",
        f"""opportunity_id   uuid,
    doc_type         text    NOT NULL,
    title            text    NOT NULL,
    status           text    NOT NULL DEFAULT 'generating',
    current_version  integer NOT NULL DEFAULT 0,
    approved_version integer,
    job_id           uuid,
    created_by       uuid    NOT NULL,
    {_in("documents", "doc_type", "prd", "executive_summary")},
    {_in("documents", "status", "generating", "draft", "approved", "generation_failed")},
    {_ref("documents", "opportunity_id", "opportunities")},
    {_ref("documents", "job_id", "jobs")},
    {_user("documents", "created_by")}""",
    ),
    _std(
        "document_versions",
        f"""document_id     uuid    NOT NULL,
    version         integer NOT NULL,
    content         jsonb   NOT NULL,
    evidence_pack   jsonb   NOT NULL,
    model_tags      jsonb   NOT NULL,
    prompt_versions jsonb   NOT NULL,
    created_by      uuid,
    change_note     text,
    CONSTRAINT uq_document_versions_document_id_version UNIQUE (document_id, version),
    {_ref("document_versions", "document_id", "documents", "cascade")},
    {_user("document_versions", "created_by")}""",
    ),
    _std(
        "user_stories",
        f"""document_id      uuid    NOT NULL,
    document_version integer NOT NULL,
    position         integer NOT NULL,
    title            text    NOT NULL,
    as_a             text    NOT NULL,
    i_want           text    NOT NULL,
    so_that          text    NOT NULL,
    status           text    NOT NULL DEFAULT 'draft',
    CONSTRAINT uq_user_stories_document_version_position
        UNIQUE (document_id, document_version, position),
    {_in("user_stories", "status", "draft", "approved")},
    {_ref("user_stories", "document_id", "documents")}""",
    ),
    _std(
        "acceptance_criteria",
        f"""story_id   uuid    NOT NULL,
    position   integer NOT NULL,
    given_text text    NOT NULL,
    when_text  text    NOT NULL,
    then_text  text    NOT NULL,
    {_ref("acceptance_criteria", "story_id", "user_stories", "cascade")}""",
    ),
]

# ---------------------------------------------------------------- 3.8 roadmaps
ROADMAPS = [
    _std(
        "roadmaps",
        f"""name                    text NOT NULL,
    status                  text NOT NULL DEFAULT 'draft',
    capacity_per_lane_weeks real NOT NULL DEFAULT 6,
    score_snapshot_id       uuid,
    {_in("roadmaps", "status", "draft", "approved")},
    {_ref("roadmaps", "score_snapshot_id", "score_snapshots")}""",
    ),
    _std(
        "roadmap_items",
        f"""roadmap_id      uuid    NOT NULL,
    opportunity_id  uuid    NOT NULL,
    lane            text    NOT NULL,
    position        integer NOT NULL,
    effort_weeks    numeric,
    effort_origin   text,
    manual_position boolean NOT NULL DEFAULT false,
    CONSTRAINT uq_roadmap_items_roadmap_id_opportunity_id UNIQUE (roadmap_id, opportunity_id),
    CONSTRAINT uq_roadmap_items_workspace_roadmap_id UNIQUE (workspace_id, roadmap_id, id),
    {_in("roadmap_items", "lane", "now", "next", "later", "unscheduled")},
    CONSTRAINT ck_roadmap_items_effort_weeks CHECK (effort_weeks > 0),
    {_in("roadmap_items", "effort_origin", "person", "ai")},
    {_ref("roadmap_items", "roadmap_id", "roadmaps", "cascade")},
    {_ref("roadmap_items", "opportunity_id", "opportunities")}""",
    ),
    f"""
CREATE TABLE roadmap_dependencies (
    workspace_id       uuid NOT NULL,
    roadmap_id         uuid NOT NULL,
    item_id            uuid NOT NULL,
    depends_on_item_id uuid NOT NULL,
    CONSTRAINT pk_roadmap_dependencies PRIMARY KEY (item_id, depends_on_item_id),
    CONSTRAINT ck_roadmap_dependencies_not_self CHECK (item_id <> depends_on_item_id),
    CONSTRAINT fk_roadmap_dependencies_workspace_id FOREIGN KEY (workspace_id)
        REFERENCES workspaces (id) ON DELETE CASCADE,
    {_ref("roadmap_dependencies", "roadmap_id", "roadmaps", "cascade")},
    CONSTRAINT fk_roadmap_dependencies_item_id FOREIGN KEY (workspace_id, roadmap_id, item_id)
        REFERENCES roadmap_items (workspace_id, roadmap_id, id) ON DELETE CASCADE,
    CONSTRAINT fk_roadmap_dependencies_depends_on_item_id
        FOREIGN KEY (workspace_id, roadmap_id, depends_on_item_id)
        REFERENCES roadmap_items (workspace_id, roadmap_id, id) ON DELETE CASCADE
)""",
]

# ---------------------------------------------------------------- 3.9 assistant
ASSISTANT = [
    _std(
        "chat_sessions",
        f"""user_id        uuid        NOT NULL,
    title          text,
    last_active_at timestamptz NOT NULL DEFAULT now(),
    {_user("chat_sessions", "user_id")}""",
    ),
    _std(
        "chat_messages",
        f"""session_id   uuid    NOT NULL,
    role         text    NOT NULL,
    content      text    NOT NULL,
    status       text    NOT NULL,
    insufficient boolean NOT NULL DEFAULT false,
    feedback     text,
    {_in("chat_messages", "role", "user", "assistant")},
    {_in("chat_messages", "status", "complete", "partial", "failed")},
    {_in("chat_messages", "feedback", "helpful", "incorrect")},
    {_ref("chat_messages", "session_id", "chat_sessions", "cascade")}""",
    ),
    _std(
        "tool_call_records",
        f"""message_id     uuid   NOT NULL,
    tool_name      text   NOT NULL,
    arguments      jsonb  NOT NULL,
    outcome        text   NOT NULL,
    result_summary jsonb,
    evidence_ids   uuid[] NOT NULL DEFAULT '{{}}',
    duration_ms    integer,
    {
            _in(
                "tool_call_records",
                "outcome",
                "ok",
                "invalid_args",
                "error",
                "refused",
                "duplicate",
                "timeout",
            )
        },
    {_ref("tool_call_records", "message_id", "chat_messages", "cascade")}""",
    ),
]

# ---------------------------------------------------------------- 3.7 claims and approvals
CLAIMS = [
    _std(
        "claims",
        f"""document_id       uuid,
    document_version  integer,
    chat_message_id   uuid,
    score_input_id    uuid,
    section           text,
    position          integer NOT NULL,
    claim_type        text    NOT NULL,
    text              text    NOT NULL,
    quote             text,
    individual_report boolean NOT NULL DEFAULT false,
    CONSTRAINT ck_claims_one_parent
        CHECK (num_nonnulls(document_id, chat_message_id, score_input_id) = 1),
    {
            _in(
                "claims",
                "claim_type",
                "quantitative",
                "qualitative",
                "quotation",
                "recommendation",
            )
        },
    {_ref("claims", "document_id", "documents")},
    {_ref("claims", "chat_message_id", "chat_messages")},
    {_ref("claims", "score_input_id", "score_inputs")}""",
    ),
    f"""
CREATE TABLE claim_evidence (
    workspace_id uuid NOT NULL,
    claim_id     uuid NOT NULL,
    record_id    uuid NOT NULL,
    CONSTRAINT pk_claim_evidence PRIMARY KEY (claim_id, record_id),
    CONSTRAINT fk_claim_evidence_workspace_id FOREIGN KEY (workspace_id)
        REFERENCES workspaces (id) ON DELETE CASCADE,
    {_ref("claim_evidence", "claim_id", "claims", "cascade")},
    {_ref("claim_evidence", "record_id", "feedback_records")}
)""",
    _std(
        "verification_results",
        f"""claim_id    uuid        NOT NULL,
    check_kind  text        NOT NULL,
    outcome     text        NOT NULL,
    detail      text,
    llm_call_id bigint,
    checked_at  timestamptz NOT NULL DEFAULT now(),
    {
            _in(
                "verification_results",
                "check_kind",
                "evidence_ids",
                "quotation",
                "numbers",
                "customer_minimum",
                "support",
            )
        },
    {
            _in(
                "verification_results",
                "outcome",
                "pass",
                "fail",
                "supported",
                "partly",
                "unsupported",
                "not_checked",
            )
        },
    {_ref("verification_results", "claim_id", "claims", "cascade")},
    {_ref("verification_results", "llm_call_id", "llm_call_records", "set null")}""",
    ),
    _std(
        "approvals",
        f"""subject_kind           text        NOT NULL,
    subject_id             uuid        NOT NULL,
    subject_version        integer,
    decision               text        NOT NULL,
    approved_by            uuid        NOT NULL,
    approved_at            timestamptz NOT NULL DEFAULT now(),
    payload_hash           bytea,
    acknowledged_claim_ids uuid[]      NOT NULL DEFAULT '{{}}',
    note                   text,
    {_in("approvals", "subject_kind", "document", "jira_batch", "roadmap")},
    {_in("approvals", "decision", "approved", "rejected")},
    {_user("approvals", "approved_by")}""",
    ),
]

# ---------------------------------------------------------------- 3.10 integrations
INTEGRATIONS = [
    _std(
        "integration_actions",
        f"""integration_config_id uuid  NOT NULL,
    approval_id           uuid,
    story_id              uuid,
    action                text  NOT NULL DEFAULT 'create_issue',
    payload               jsonb NOT NULL,
    payload_hash          bytea NOT NULL,
    status                text  NOT NULL DEFAULT 'previewed',
    external_key          text,
    error                 text,
    attempted_at          timestamptz,
    {_in("integration_actions", "action", "create_issue")},
    {
            _in(
                "integration_actions",
                "status",
                "previewed",
                "approved",
                "rejected",
                "sending",
                "created",
                "failed",
                "unknown",
            )
        },
    {_ref("integration_actions", "integration_config_id", "integration_configs")},
    {_ref("integration_actions", "approval_id", "approvals")},
    {_ref("integration_actions", "story_id", "user_stories")}""",
    ),
    _std(
        "external_item_links",
        f"""story_id              uuid NOT NULL,
    integration_config_id uuid NOT NULL,
    external_system       text NOT NULL,
    external_key          text NOT NULL,
    external_url          text NOT NULL,
    CONSTRAINT uq_external_item_links_story_system
        UNIQUE (workspace_id, story_id, external_system),
    CONSTRAINT uq_external_item_links_config_key UNIQUE (integration_config_id, external_key),
    {_in("external_item_links", "external_system", "jira")},
    {_ref("external_item_links", "story_id", "user_stories")},
    {_ref("external_item_links", "integration_config_id", "integration_configs")}""",
    ),
]

# ---------------------------------------------------------------- 3.11 audit and evaluation
OPERATIONS = [
    f"""
CREATE TABLE audit_logs (
    id            bigint      GENERATED ALWAYS AS IDENTITY,
    workspace_id  uuid,
    actor_user_id uuid,
    action        text        NOT NULL,
    target_type   text,
    target_id     uuid,
    outcome       text        NOT NULL,
    details       jsonb       NOT NULL DEFAULT '{{}}',
    ip            inet,
    created_at    timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT pk_audit_logs PRIMARY KEY (id),
    {_in("audit_logs", "outcome", "success", "failure")},
    CONSTRAINT fk_audit_logs_workspace_id FOREIGN KEY (workspace_id)
        REFERENCES workspaces (id) ON DELETE CASCADE
)""",
    "CREATE INDEX ix_audit_logs_workspace_id_created_at ON audit_logs (workspace_id, created_at DESC)",
    _std(
        "evaluation_datasets",
        f"""name           text    NOT NULL,
    description    text,
    source_file_id uuid,
    split_seed     integer NOT NULL,
    frozen_at      timestamptz,
    {_ref("evaluation_datasets", "source_file_id", "source_files")}""",
    ),
    _std(
        "evaluation_items",
        f"""dataset_id  uuid    NOT NULL,
    record_id   uuid,
    text_masked text    NOT NULL,
    split       text    NOT NULL,
    gold        jsonb   NOT NULL,
    labeller_a  jsonb,
    labeller_b  jsonb,
    adjudicated boolean NOT NULL DEFAULT false,
    {_in("evaluation_items", "split", "train", "validation", "test")},
    {_ref("evaluation_items", "dataset_id", "evaluation_datasets", "cascade")},
    {_ref("evaluation_items", "record_id", "feedback_records")}""",
    ),
    _std(
        "evaluation_runs",
        f"""dataset_id  uuid  NOT NULL,
    kind        text  NOT NULL,
    config      jsonb NOT NULL,
    config_hash text  NOT NULL,
    metrics     jsonb,
    started_at  timestamptz,
    finished_at timestamptz,
    notes       text,
    {
            _in(
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
            )
        },
    {_ref("evaluation_runs", "dataset_id", "evaluation_datasets")}""",
    ),
]

# ---------------------------------------------------------------- tables, in creation order
TENANT_TABLES = (
    "jobs",
    "integration_configs",
    "data_sources",
    "source_files",
    "column_mappings",
    "import_jobs",
    "import_row_errors",
    "customers",
    "feedback_records",
    "llm_call_records",
    "analysis_runs",
    "record_classifications",
    "record_embeddings",
    "themes",
    "theme_memberships",
    "theme_overrides",
    "theme_run_stats",
    "aggregated_requests",
    "request_memberships",
    "review_items",
    "metric_definitions",
    "metric_observations",
    "product_releases",
    "theme_metric_links",
    "scoring_configs",
    "opportunities",
    "score_inputs",
    "score_snapshots",
    "documents",
    "document_versions",
    "user_stories",
    "acceptance_criteria",
    "roadmaps",
    "roadmap_items",
    "roadmap_dependencies",
    "chat_sessions",
    "chat_messages",
    "tool_call_records",
    "claims",
    "claim_evidence",
    "verification_results",
    "approvals",
    "integration_actions",
    "external_item_links",
    "audit_logs",
    "evaluation_datasets",
    "evaluation_items",
    "evaluation_runs",
)
# Creation order for the downgrade (reverse): identity, then tenant tables as created above.
CREATION_ORDER = (
    "users",
    "sessions",
    "login_attempts",
    "workspaces",
    "workspace_memberships",
    *TENANT_TABLES[:9],
    "prompt_versions",
    *TENANT_TABLES[9:],
)


# ---------------------------------------------------------------- privileges and RLS
def _grants() -> list[str]:
    statements = [f"REVOKE ALL ON TABLE {t} FROM PUBLIC, {APP_ROLES}" for t in CREATION_ORDER]
    full = "SELECT, INSERT, UPDATE, DELETE"
    special = {"audit_logs", "llm_call_records", "score_inputs", "login_attempts", "prompt_versions"}
    for table in (*TENANT_TABLES, "users", "sessions", "workspaces", "workspace_memberships"):
        if table not in special:
            statements.append(f"GRANT {full} ON TABLE {table} TO {APP_ROLES}")
    statements += [
        # SEC-15: users cannot edit or delete audit entries.
        f"GRANT SELECT, INSERT ON TABLE audit_logs TO {APP_ROLES}",
        # Append-only call log; only the worker purges it (D07 section 8, 90 days).
        f"GRANT SELECT, INSERT ON TABLE llm_call_records TO {APP_ROLES}",
        "GRANT DELETE ON TABLE llm_call_records TO app_worker",
        # Throttling log; only the worker purges it (30 days).
        f"GRANT SELECT, INSERT ON TABLE login_attempts TO {APP_ROLES}",
        "GRANT DELETE ON TABLE login_attempts TO app_worker",
        # Prompt versions are immutable once registered.
        f"GRANT SELECT, INSERT ON TABLE prompt_versions TO {APP_ROLES}",
        # FR-PRI-04: rows are never updated except is_current and superseded_at.
        f"GRANT SELECT, INSERT ON TABLE score_inputs TO {APP_ROLES}",
        f"GRANT UPDATE (is_current, superseded_at) ON TABLE score_inputs TO {APP_ROLES}",
        f"GRANT USAGE ON SEQUENCE login_attempts_id_seq, llm_call_records_id_seq,"
        f" audit_logs_id_seq TO {APP_ROLES}",
        "REVOKE ALL ON FUNCTION reject_raw_text_update() FROM PUBLIC",
    ]
    return statements


def _row_level_security() -> list[str]:
    statements: list[str] = []
    for table in TENANT_TABLES:
        statements += [
            f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY",
            f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY",
        ]
        if table != "audit_logs":
            statements.append(
                f"CREATE POLICY tenant_isolation ON {table}"
                f" USING (workspace_id = {WORKSPACE}) WITH CHECK (workspace_id = {WORKSPACE})"
            )
    statements += [
        # The claim, heartbeat and finish queries run before a workspace is known (D07 §5).
        "CREATE POLICY worker_queue_read ON jobs FOR SELECT TO app_worker USING (true)",
        "CREATE POLICY worker_queue_update ON jobs FOR UPDATE TO app_worker"
        " USING (true) WITH CHECK (true)",
        # Audit: a workspace reads its own entries; sign-in events and workspace.deleted
        # have no workspace and are readable only by the administrative owner role.
        f"CREATE POLICY audit_read ON audit_logs FOR SELECT USING (workspace_id = {WORKSPACE})",
        "CREATE POLICY audit_insert ON audit_logs FOR INSERT"
        f" WITH CHECK (workspace_id = {WORKSPACE} OR workspace_id IS NULL)",
        "CREATE POLICY audit_global_read ON audit_logs FOR SELECT TO app_owner"
        " USING (workspace_id IS NULL)",
    ]
    return statements


SECTIONS = (
    IDENTITY,
    INGESTION,
    FEEDBACK,
    ANALYSIS,
    ANALYTICS,
    PRIORITISATION,
    DOCUMENTS,
    ROADMAPS,
    ASSISTANT,
    CLAIMS,
    INTEGRATIONS,
    OPERATIONS,
)


def upgrade() -> None:
    for section in SECTIONS:
        for statement in section:
            op.execute(statement)
    for statement in (*_grants(), *_row_level_security()):
        op.execute(statement)


def downgrade() -> None:
    for table in reversed(CREATION_ORDER):
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
    op.execute("DROP FUNCTION IF EXISTS reject_raw_text_update()")
