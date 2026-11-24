# 08 · Database ER Diagram and Relationships

The ER diagrams below match the data dictionary in doc 07 (54 tables). Column details, constraints and indexes are in doc 07; here the focus is entities, keys and cardinality. Because 54 tables do not fit legibly in one picture, section 1 shows the whole model with relationships only (printed on an A3 page in the PDF; zoom in for detail) and sections 2 to 6 show every table with its key columns in 14 smaller diagrams, grouped by domain.

Notation: `||--o{` one to zero-or-many, `||--|{` one to one-or-many, `|o--o{` zero-or-one to zero-or-many, `||--||` one to one, `|o--||` zero-or-one to exactly one.

Tenant scoping is not drawn on every line: every table except `users`, `sessions`, `login_attempts` and `prompt_versions` belongs to exactly one workspace, and every tenant-to-tenant foreign key includes `workspace_id` (doc 07 §2).

## 1. Whole model (Diagram 12)

```mermaid
erDiagram
    users ||--o{ sessions : "signs in with"
    users ||--o{ workspace_memberships : "is member via"
    workspaces ||--o{ workspace_memberships : "has members"
    workspaces ||--o{ data_sources : owns
    workspaces ||--o{ analysis_runs : owns
    workspaces ||--o{ jobs : owns
    workspaces ||--o{ audit_logs : records
    data_sources ||--o{ source_files : receives
    data_sources ||--o{ import_jobs : "imported by"
    source_files |o--o{ import_jobs : "parsed by"
    import_jobs ||--o{ import_row_errors : reports
    import_jobs ||--o{ feedback_records : produces
    customers |o--o{ feedback_records : authored
    feedback_records ||--o{ record_embeddings : "embedded as"
    analysis_runs ||--o{ record_classifications : labels
    feedback_records ||--o{ record_classifications : "labelled in"
    analysis_runs ||--o{ theme_memberships : assigns
    themes ||--o{ theme_memberships : contains
    feedback_records ||--o{ theme_memberships : "member of"
    themes ||--o{ theme_overrides : "corrected by"
    themes ||--o{ theme_run_stats : "measured in"
    analysis_runs ||--o{ theme_run_stats : computes
    aggregated_requests ||--o{ request_memberships : groups
    feedback_records ||--o{ request_memberships : "asks in"
    analysis_runs ||--o{ review_items : raises
    metric_definitions ||--o{ metric_observations : "observed as"
    metric_definitions ||--o{ theme_metric_links : "linked by"
    themes |o--o{ theme_metric_links : "linked to"
    themes |o--o| opportunities : "becomes"
    aggregated_requests |o--o| opportunities : "becomes"
    opportunities ||--o{ score_inputs : "scored by"
    scoring_configs ||--o{ score_snapshots : "applied in"
    opportunities |o--o{ documents : "described by"
    documents ||--|{ document_versions : versions
    documents ||--o{ user_stories : contains
    user_stories ||--o{ acceptance_criteria : has
    documents ||--o{ claims : asserts
    claims ||--|{ claim_evidence : cites
    feedback_records ||--o{ claim_evidence : "cited as"
    claims ||--o{ verification_results : "checked by"
    documents ||--o{ approvals : "approved via"
    roadmaps ||--o{ roadmap_items : contains
    opportunities ||--o{ roadmap_items : "planned as"
    roadmap_items ||--o{ roadmap_dependencies : "depends on"
    score_snapshots |o--o{ roadmaps : "basis of"
    chat_sessions ||--o{ chat_messages : contains
    chat_messages ||--o{ tool_call_records : invokes
    chat_messages ||--o{ claims : asserts
    integration_configs ||--o{ integration_actions : performs
    user_stories ||--o{ integration_actions : "exported by"
    user_stories ||--o| external_item_links : "linked to"
    prompt_versions ||--o{ llm_call_records : "used by"
    jobs ||--o{ llm_call_records : makes
    evaluation_datasets ||--o{ evaluation_items : contains
    evaluation_datasets ||--o{ evaluation_runs : "evaluated in"
    workspaces ||--o{ metric_definitions : defines
    workspaces ||--o{ product_releases : records
    workspaces ||--o{ chat_sessions : hosts
    workspaces ||--o{ integration_configs : configures
    workspaces ||--o{ column_mappings : saves
    login_attempts {
        bigint id PK
        text email_lower "global, no FK"
    }
```

> `login_attempts` is global and keyed by e-mail and IP, so it has no relationships.

## 2. Identity, ingestion and feedback

### 2.1 Identity and workspaces

```mermaid
erDiagram
    users {
        uuid id PK
        text email UK "unique on lower(email)"
        text password_hash "Argon2id"
        boolean is_active
    }
    sessions {
        uuid id PK
        uuid user_id FK
        bytea token_hash UK "SHA-256 of cookie"
        timestamptz expires_at
    }
    workspaces {
        uuid id PK
        text name
        text product_name
        bytea customer_key_secret "encrypted"
        uuid current_analysis_run_id FK
    }
    workspace_memberships {
        uuid workspace_id PK, FK
        uuid user_id PK, FK
        text role "owner, editor, viewer"
    }
    login_attempts {
        bigint id PK
        text email_lower "global, no FK"
        inet ip
        boolean succeeded
    }
    chat_sessions {
        uuid id PK
    }
    column_mappings {
        uuid id PK
    }
    data_sources {
        uuid id PK
    }
    users ||--o{ sessions : "has"
    users ||--o{ workspace_memberships : "joins"
    workspaces ||--o{ workspace_memberships : "has"
    workspaces ||--o{ data_sources : "owns"
    workspaces ||--o{ column_mappings : "saves"
    users ||--o{ chat_sessions : "owns"
```

Entities from other areas are shown with their key only: `chat_sessions`, `column_mappings`, `data_sources`.

### 2.2 Sources, files and imports

```mermaid
erDiagram
    data_sources {
        uuid id PK
        uuid workspace_id FK
        text kind "file or connector"
        jsonb sync_state
    }
    source_files {
        uuid id PK
        uuid workspace_id FK
        uuid data_source_id FK
        bytea sha256
        bigint size_bytes "at most 20 MB"
    }
    column_mappings {
        uuid id PK
        uuid workspace_id FK
        text name UK "unique per workspace"
        text source_type
        jsonb mapping
    }
    import_jobs {
        uuid id PK
        uuid workspace_id FK
        uuid source_file_id FK
        text source_type
        text status
        jsonb report "reconciliation counts"
    }
    import_row_errors {
        uuid id PK
        uuid import_job_id FK
        integer row_number
        text kind "rejected or failed"
        text code
    }
    feedback_records {
        uuid id PK
    }
    workspaces {
        uuid id PK
    }
    workspaces ||--o{ data_sources : "owns"
    data_sources ||--o{ source_files : "receives"
    data_sources ||--o{ import_jobs : "runs"
    source_files |o--o{ import_jobs : "parsed by"
    import_jobs ||--o{ import_row_errors : "reports"
    import_jobs ||--o{ feedback_records : "produces"
    workspaces ||--o{ column_mappings : "saves"
```

Entities from other areas are shown with their key only: `feedback_records`, `workspaces`.

### 2.3 Feedback records

```mermaid
erDiagram
    customers {
        uuid id PK
        uuid workspace_id FK
        bytea customer_key UK "HMAC"
    }
    feedback_records {
        uuid id PK
        uuid workspace_id FK
        uuid import_job_id FK
        integer row_number
        integer segment_index
        text raw_text "immutable"
        text processed_text "masked"
        uuid customer_id FK
        timestamptz occurred_at
        boolean analysable
        text exclusion_reason "first reason in pipeline order"
        text spam_status
        uuid duplicate_of FK
        tsvector search_tsv "generated"
    }
    record_embeddings {
        uuid workspace_id PK
        uuid record_id PK, FK
        text model_id PK
        vector embedding "1024 dims, HNSW cosine"
    }
    claim_evidence {
        uuid claim_id PK, FK
        uuid record_id PK, FK
    }
    import_jobs {
        uuid id PK
    }
    record_classifications {
        uuid id PK
    }
    request_memberships {
        uuid id PK
    }
    review_items {
        uuid id PK
    }
    theme_memberships {
        uuid id PK
    }
    import_jobs ||--o{ feedback_records : "produces"
    customers |o--o{ feedback_records : "authored"
    feedback_records |o--o{ feedback_records : "duplicate_of / parent"
    feedback_records ||--o{ record_embeddings : "one per model"
    feedback_records ||--o{ record_classifications : "one per run"
    feedback_records |o--o{ record_classifications : "near duplicate of"
    feedback_records ||--o{ theme_memberships : "at most one per run"
    feedback_records ||--o{ request_memberships : "at most one per run"
    feedback_records |o--o{ review_items : "about"
    feedback_records ||--o{ claim_evidence : "cited as"
```

Entities from other areas are shown with their key only: `claim_evidence`, `import_jobs`, `record_classifications`, `request_memberships`, `review_items`, `theme_memberships`.

## 3. AI analysis

### 3.1 Analysis runs and per-record outcomes

```mermaid
erDiagram
    analysis_runs {
        uuid id PK
        uuid workspace_id FK
        text status
        jsonb config "models, prompts, thresholds"
        text embedding_model_id
        uuid previous_run_id FK
    }
    record_classifications {
        uuid id PK
        uuid analysis_run_id FK
        uuid record_id FK
        text status "classified, near_duplicate, unclassified, embedding_failed"
        uuid near_duplicate_of FK
        text category "SRS taxonomy, no intent field"
        text sentiment
        boolean sarcasm
        text method "classifier, llm, human"
        real confidence
    }
    review_items {
        uuid id PK
        uuid analysis_run_id FK
        uuid record_id FK
        text kind
        text status
    }
    feedback_records {
        uuid id PK
    }
    theme_memberships {
        uuid id PK
    }
    theme_run_stats {
        uuid id PK
    }
    analysis_runs |o--o{ analysis_runs : "previous run"
    analysis_runs ||--o{ record_classifications : "labels"
    feedback_records ||--o{ record_classifications : "one per run"
    feedback_records |o--o{ record_classifications : "near duplicate of"
    analysis_runs ||--o{ theme_memberships : "assigns"
    analysis_runs ||--o{ theme_run_stats : "computes"
    analysis_runs ||--o{ review_items : "raises"
    feedback_records |o--o{ review_items : "about"
```

Entities from other areas are shown with their key only: `feedback_records`, `theme_memberships`, `theme_run_stats`.

### 3.2 Themes

```mermaid
erDiagram
    themes {
        uuid id PK
        uuid workspace_id FK
        text name
        boolean name_locked
        text size_class "normal or small"
        uuid merged_into FK
        vector centroid
    }
    theme_memberships {
        uuid id PK
        uuid analysis_run_id FK
        uuid theme_id FK
        uuid record_id FK
        text source "cluster or override"
    }
    theme_overrides {
        uuid id PK
        uuid theme_id FK
        uuid target_theme_id FK
        uuid record_id FK
        text kind "rename, merge, split, pin, exclude"
        boolean active
    }
    theme_run_stats {
        uuid id PK
        uuid analysis_run_id FK
        uuid theme_id FK
        integer record_count
        integer known_customers
        integer unknown_identity_records
        real identity_coverage
        boolean vocal_flag "NULL = not assessable"
        boolean emerging
    }
    analysis_runs {
        uuid id PK
    }
    feedback_records {
        uuid id PK
    }
    opportunities {
        uuid id PK
    }
    theme_metric_links {
        uuid id PK
    }
    analysis_runs ||--o{ theme_memberships : "assigns"
    themes ||--o{ theme_memberships : "contains"
    feedback_records ||--o{ theme_memberships : "at most one per run"
    themes ||--o{ theme_overrides : "corrected by"
    analysis_runs ||--o{ theme_run_stats : "computes"
    themes ||--o{ theme_run_stats : "one per run"
    themes |o--o{ themes : "merged into"
    themes |o--o{ theme_metric_links : "theme side"
    themes |o--o| opportunities : "source"
```

Entities from other areas are shown with their key only: `analysis_runs`, `feedback_records`, `opportunities`, `theme_metric_links`.

### 3.3 Feature requests

```mermaid
erDiagram
    aggregated_requests {
        uuid id PK
        text title
        uuid merged_into FK
    }
    request_memberships {
        uuid id PK
        uuid analysis_run_id FK
        uuid request_id FK
        uuid record_id FK
        text canonical_ask
    }
    feedback_records {
        uuid id PK
    }
    opportunities {
        uuid id PK
    }
    theme_metric_links {
        uuid id PK
    }
    aggregated_requests ||--o{ request_memberships : "groups"
    feedback_records ||--o{ request_memberships : "at most one per run"
    aggregated_requests |o--o{ theme_metric_links : "request side"
    aggregated_requests |o--o| opportunities : "source"
```

Entities from other areas are shown with their key only: `feedback_records`, `opportunities`, `theme_metric_links`.

## 4. Analytics, prioritisation and roadmaps

### 4.1 Product analytics

```mermaid
erDiagram
    metric_definitions {
        uuid id PK
        text name UK
        text aggregation
    }
    metric_observations {
        uuid id PK
        uuid metric_id FK
        date observed_on
        text dimension
        float8 value
    }
    product_releases {
        uuid id PK
        text version UK
        date released_on
    }
    theme_metric_links {
        uuid id PK
        uuid theme_id FK
        uuid request_id FK
        uuid metric_id FK
        text origin "person or system_suggestion"
    }
    aggregated_requests {
        uuid id PK
    }
    themes {
        uuid id PK
    }
    metric_definitions ||--o{ metric_observations : "observed as"
    metric_definitions ||--o{ theme_metric_links : "linked by"
    themes |o--o{ theme_metric_links : "theme side"
    aggregated_requests |o--o{ theme_metric_links : "request side"
```

Entities from other areas are shown with their key only: `aggregated_requests`, `themes`.

### 4.2 Prioritisation

```mermaid
erDiagram
    opportunities {
        uuid id PK
        text source_kind "theme or request"
        uuid theme_id FK
        uuid request_id FK
        text status "open, accepted, deferred, rejected"
    }
    scoring_configs {
        uuid id PK
        text framework "rice or ice"
        boolean is_active
    }
    score_inputs {
        uuid id PK
        uuid opportunity_id FK
        text input_name
        numeric value
        text origin "data, ai, person"
        uuid_array evidence_ids
        boolean is_current
    }
    score_snapshots {
        uuid id PK
        uuid scoring_config_id FK
        jsonb ranking
    }
    aggregated_requests {
        uuid id PK
    }
    claims {
        uuid id PK
    }
    documents {
        uuid id PK
    }
    roadmap_items {
        uuid id PK
    }
    roadmaps {
        uuid id PK
    }
    themes {
        uuid id PK
    }
    themes |o--o| opportunities : "source"
    aggregated_requests |o--o| opportunities : "source"
    opportunities ||--o{ score_inputs : "has inputs"
    scoring_configs ||--o{ score_snapshots : "produces"
    score_snapshots |o--o{ roadmaps : "basis"
    opportunities ||--o{ roadmap_items : "at most one per roadmap"
    opportunities |o--o{ documents : "described by"
    score_inputs |o--o{ claims : "rationale"
```

Entities from other areas are shown with their key only: `aggregated_requests`, `claims`, `documents`, `roadmap_items`, `roadmaps`, `themes`.

### 4.3 Roadmaps

```mermaid
erDiagram
    roadmaps {
        uuid id PK
        uuid score_snapshot_id FK
        text status
    }
    roadmap_items {
        uuid id PK
        uuid roadmap_id FK
        uuid opportunity_id FK
        text lane "now, next, later, unscheduled"
        numeric effort_weeks
    }
    roadmap_dependencies {
        uuid item_id PK, FK
        uuid depends_on_item_id PK, FK
    }
    opportunities {
        uuid id PK
    }
    score_snapshots {
        uuid id PK
    }
    score_snapshots |o--o{ roadmaps : "basis"
    roadmaps ||--o{ roadmap_items : "contains"
    opportunities ||--o{ roadmap_items : "at most one per roadmap"
    roadmap_items ||--o{ roadmap_dependencies : "depends on"
```

Entities from other areas are shown with their key only: `opportunities`, `score_snapshots`.

## 5. Documents, evidence and approvals

### 5.1 Documents, stories and approvals

```mermaid
erDiagram
    documents {
        uuid id PK
        uuid opportunity_id FK
        text doc_type "prd or executive_summary"
        text status
        integer current_version
        integer approved_version
    }
    document_versions {
        uuid id PK
        uuid document_id FK
        integer version
        jsonb content
        jsonb evidence_pack "E-code to record ID"
    }
    user_stories {
        uuid id PK
        uuid document_id FK
        integer document_version
        text as_a
        text i_want
        text so_that
    }
    acceptance_criteria {
        uuid id PK
        uuid story_id FK
        text given_text
        text when_text
        text then_text
    }
    approvals {
        uuid id PK
        text subject_kind "document, jira_batch, roadmap"
        uuid subject_id
        integer subject_version
        uuid approved_by FK
        bytea payload_hash
    }
    claims {
        uuid id PK
    }
    external_item_links {
        uuid id PK
    }
    integration_actions {
        uuid id PK
    }
    opportunities {
        uuid id PK
    }
    opportunities |o--o{ documents : "described by"
    documents ||--|{ document_versions : "versions"
    documents ||--o{ user_stories : "contains"
    user_stories ||--o{ acceptance_criteria : "has"
    documents |o--o{ claims : "asserts"
    documents ||--o{ approvals : "approved via"
    approvals |o--o{ integration_actions : "authorises"
    user_stories ||--o{ integration_actions : "exported by"
    user_stories ||--o| external_item_links : "at most one Jira issue"
```

Entities from other areas are shown with their key only: `claims`, `external_item_links`, `integration_actions`, `opportunities`.

### 5.2 Claims and verification

```mermaid
erDiagram
    claims {
        uuid id PK
        uuid document_id FK
        uuid chat_message_id FK
        uuid score_input_id FK
        text claim_type
        text text
        boolean individual_report
    }
    claim_evidence {
        uuid claim_id PK, FK
        uuid record_id PK, FK
    }
    verification_results {
        uuid id PK
        uuid claim_id FK
        text check_kind
        text outcome
    }
    chat_messages {
        uuid id PK
    }
    documents {
        uuid id PK
    }
    feedback_records {
        uuid id PK
    }
    score_inputs {
        uuid id PK
    }
    documents |o--o{ claims : "asserts"
    chat_messages |o--o{ claims : "asserts"
    score_inputs |o--o{ claims : "rationale"
    claims ||--o{ claim_evidence : "cites"
    feedback_records ||--o{ claim_evidence : "cited as"
    claims ||--o{ verification_results : "checked by"
    claims ||--|{ claim_evidence : cites
```

Entities from other areas are shown with their key only: `chat_messages`, `documents`, `feedback_records`, `score_inputs`.

## 6. Assistant, integrations, operations and evaluation

### 6.1 Conversational assistant

```mermaid
erDiagram
    chat_sessions {
        uuid id PK
        uuid user_id FK
        text title
    }
    chat_messages {
        uuid id PK
        uuid session_id FK
        text role
        text status
        boolean insufficient
    }
    tool_call_records {
        uuid id PK
        uuid message_id FK
        text tool_name
        jsonb arguments
        text outcome
    }
    claims {
        uuid id PK
    }
    users {
        uuid id PK
    }
    chat_messages |o--o{ claims : "asserts"
    chat_sessions ||--o{ chat_messages : "contains"
    chat_messages ||--o{ tool_call_records : "invokes"
    users ||--o{ chat_sessions : "owns"
```

Entities from other areas are shown with their key only: `claims`, `users`.

### 6.2 Jira integration

```mermaid
erDiagram
    integration_configs {
        uuid id PK
        text kind "rovo or self-hosted MCP"
        jsonb settings
        bytea credentials_encrypted "Fernet"
    }
    integration_actions {
        uuid id PK
        uuid integration_config_id FK
        uuid approval_id FK
        uuid story_id FK
        bytea payload_hash
        text status
        text external_key
    }
    external_item_links {
        uuid id PK
        uuid story_id FK "unique per system"
        uuid integration_config_id FK
        text external_key
    }
    approvals {
        uuid id PK
    }
    user_stories {
        uuid id PK
    }
    integration_configs ||--o{ integration_actions : "performs"
    approvals |o--o{ integration_actions : "authorises"
    user_stories ||--o{ integration_actions : "exported by"
    user_stories ||--o| external_item_links : "at most one Jira issue"
    integration_configs ||--o{ external_item_links : "hosts"
```

Entities from other areas are shown with their key only: `approvals`, `user_stories`.

### 6.3 Operations, audit and evaluation

```mermaid
erDiagram
    jobs {
        uuid id PK
        text job_type
        text status
        jsonb cursor
        text idempotency_key
        timestamptz heartbeat_at
        smallint attempts
    }
    llm_call_records {
        bigint id PK
        uuid workspace_id FK
        text call_id "CP-01 to CP-10"
        uuid prompt_version_id FK
        uuid job_id FK
        text outcome
    }
    prompt_versions {
        uuid id PK
        text call_id
        text version
    }
    audit_logs {
        bigint id PK
        uuid workspace_id
        text action
        text outcome
    }
    evaluation_datasets {
        uuid id PK
        text name
        timestamptz frozen_at
    }
    evaluation_items {
        uuid id PK
        uuid dataset_id FK
        text split "train, validation, test"
        jsonb gold
    }
    evaluation_runs {
        uuid id PK
        uuid dataset_id FK
        text kind
        jsonb metrics
    }
    prompt_versions ||--o{ llm_call_records : "used by"
    jobs |o--o{ llm_call_records : "makes"
    evaluation_datasets ||--o{ evaluation_items : "contains"
    evaluation_datasets ||--o{ evaluation_runs : "evaluated in"
    jobs ||--o{ llm_call_records : makes
```



## 7. Cardinality explanation

| Relationship | Cardinality | Why | Enforced by |
|---|---|---|---|
| users – workspaces | Many to many through `workspace_memberships` | A person can belong to several workspaces with a role in each (SEC-21) | Composite PK (workspace_id, user_id) |
| import_jobs – feedback_records | One to many | Each stored record comes from exactly one import row (or transcript segment) | UNIQUE (workspace_id, import_job_id, row_number, segment_index) |
| feedback_records – feedback_records | Self, zero-or-one to many | `duplicate_of` points to the kept original; `parent_record_id` links transcript segments to their transcript | CHECK on duplicate_of; FK |
| customers – feedback_records | Zero-or-one to many | Many sources have no customer identifier; such records have unknown identity and are never counted as customers; statistics report known customers, unknown-identity records and coverage (CR-18) | Nullable FK |
| feedback_records – record_embeddings | One to many | One vector per embedding model, so a model change can be re-embedded side by side (DR-34) | PK (workspace_id, record_id, model_id) |
| analysis_runs – record_classifications | One to many, exactly one row per eligible record per run | Every eligible record ends the run with a status (classified, near duplicate, unclassified, embedding failed); runs are versions, not overwrites | UNIQUE (analysis_run_id, record_id) |
| feedback_records – record_classifications (near duplicate) | Zero-or-one to many | A near duplicate points to the earlier record of the same customer, for that run only; the import report is not changed | CHECK (status = 'near_duplicate' ⇔ near_duplicate_of not null) |
| themes – theme_memberships | One to many, at most one theme per record per run | Clustering gives each record one theme or noise; noise records have no row | UNIQUE (analysis_run_id, record_id) |
| themes – themes | Self, zero-or-one | `merged_into` keeps history after a merge override | FK |
| themes or aggregated_requests – opportunities | Zero-or-one to zero-or-one | An opportunity has exactly one source; each theme or request yields at most one opportunity | CHECK (exactly one source) plus partial unique indexes |
| opportunities – score_inputs | One to many, one current row per input | History of input changes kept; `is_current` selects the live value | Partial UNIQUE (opportunity_id, framework, input_name) WHERE is_current |
| documents – document_versions | One to one-or-many | Every edit or regeneration creates a version; approval points to an exact version | UNIQUE (document_id, version) |
| claims – parent | Exactly one of document, chat message, score input | The same claim and evidence model serves PRDs, chat answers and AI score rationales | CHECK (one non-null parent) |
| claims – feedback_records | Many to many through `claim_evidence` | A claim cites several records; a record supports many claims | PK (claim_id, record_id) |
| roadmaps – opportunities | Many to many through `roadmap_items` | An opportunity appears at most once per roadmap | UNIQUE (roadmap_id, opportunity_id) |
| roadmap_items – roadmap_items | Many to many through `roadmap_dependencies` | Dependencies inside one roadmap; no self links; cycles rejected by SVC-18 | CHECK (item_id <> depends_on_item_id) |
| user_stories – external_item_links | One to zero-or-one per external system | Prevents duplicate Jira issues on retry (AGR-23) | UNIQUE (workspace_id, story_id, external_system) |
| jobs – llm_call_records | Zero-or-one to many | Assistant calls run in-request, so they have no job | Nullable FK |

## 8. Design rationale

- **Composite tenant foreign keys.** RLS hides rows from other workspaces, and composite foreign keys also make it impossible to *store* a cross-workspace reference. Both are cheap and cover different failure modes (a missing `SET LOCAL`, a bug passing the wrong ID).
- **Results keyed by run.** Classifications, memberships and statistics are versioned by `analysis_run_id`, so a re-run never destroys the previous result and dashboards can compare runs. `workspaces.current_analysis_run_id` marks the version shown.
- **Overrides as rows.** Human corrections live in `theme_overrides`, `score_inputs` (origin 'person') and `review_items.resolution`, and are re-applied by every run (FR-THM-12, CR-05).
- **One claim model.** PRDs, chat answers and score rationales all store claims with evidence, so verification and the "show evidence" view work the same everywhere.
- **Derived tables are explicit.** `theme_run_stats` and `score_snapshots` repeat computable facts on purpose: dashboards stay fast and rankings stay reproducible. Only services write them, and each row records the run or configuration it came from.
- **Vectors beside records.** Keeping embeddings in PostgreSQL lets one SQL query join vector search with workspace scope, analysable flag and date filters (doc 05).
