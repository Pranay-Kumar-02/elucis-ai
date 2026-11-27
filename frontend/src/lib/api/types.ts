/** Response types mirroring backend Pydantic schemas (elucis/schemas, modules/ingestion). */

export type CheckStatus = "ok" | "unavailable" | "not_configured";
export type OverallStatus = "ok" | "degraded" | "unavailable";

export interface CheckOut {
  status: CheckStatus;
  latency_ms: number | null;
  detail: string | null;
}

export interface HealthOut {
  status: OverallStatus;
  service: string;
  version: string;
  checks: Record<string, CheckOut>;
}

export interface DatabaseHealthOut {
  status: CheckStatus;
  latency_ms: number | null;
  server_version: string | null;
  pgvector_version: string | null;
  database: string | null;
  role: string | null;
  detail: string | null;
}

export interface ModelRuntimeHealthOut {
  status: CheckStatus;
  latency_ms: number | null;
  ollama_version: string | null;
  models: Record<string, boolean> | null;
  detail: string | null;
}

export type SourceType =
  "review" | "ticket" | "feature_request" | "transcript" | "other" | "metrics";

export type MappingField =
  | "text"
  | "occurred_at"
  | "customer_id"
  | "rating"
  | "product_version"
  | "source_record_id"
  | "speaker"
  | "metric_name"
  | "metric_value"
  | "dimension";

export type ColumnMapping = Partial<Record<MappingField, string>>;

export interface FileInfoOut {
  input: "file" | "pasted_text";
  original_filename: string;
  size_bytes: number;
  sha256: string;
  detected_format: "csv" | "json" | "txt";
  detected_encoding: string;
  csv_delimiter: string | null;
  transcript_mode: "speaker_turns" | "paragraphs" | null;
  record_count: number;
}

export interface FilePreviewOut extends FileInfoOut {
  columns: string[];
  preview_rows: string[][];
  total_rows: number;
  warnings: string[];
  source_type: SourceType;
  required_fields: MappingField[];
  suggested_mapping: ColumnMapping;
}

export interface RowErrorOut {
  row_number: number;
  segment_index: number;
  field: string | null;
  code: string;
  message: string;
}

export interface NormalizedRecordOut {
  row_number: number;
  segment_index: number;
  source_type: SourceType;
  raw_text: string;
  text_truncated: boolean;
  source_record_id: string | null;
  occurred_at: string | null;
  occurred_at_raw: string | null;
  occurred_at_missing: boolean;
  customer_ref: string | null;
  rating_raw: string | null;
  rating_value: number | null;
  rating_out_of: number | null;
  product_version_raw: string | null;
  speaker: string | null;
  metadata: Record<string, string>;
  flags: string[];
}

export interface MetricObservationOut {
  row_number: number;
  metric_name: string;
  observed_on: string;
  value: number;
  dimension: string;
  metadata: Record<string, string>;
}

export interface ValidationReportOut {
  file: FileInfoOut;
  source_type: SourceType;
  column_mapping: ColumnMapping;
  date_order: { order: "dmy" | "mdy"; assumed: boolean } | null;
  summary: {
    received: number;
    valid: number;
    rejected: number;
    rejected_by_code: Record<string, number>;
    flags_by_code: Record<string, number>;
    reconciled: boolean;
  };
  errors: RowErrorOut[];
  errors_truncated: boolean;
  sample_records: NormalizedRecordOut[];
  sample_metrics: MetricObservationOut[];
  warnings: string[];
}

export interface SourceInfoOut {
  kind: string;
  label: string;
  status: "implemented" | "designed";
  formats: string[];
  auth: string | null;
  requirement: string | null;
  notes: string | null;
}

// ---- Authentication and workspaces (D09 §4, API-01 to API-13) ----

export type Role = "owner" | "editor" | "viewer";

export interface UserOut {
  id: string;
  email: string;
  display_name: string | null;
  created_at: string;
}

export interface MembershipOut {
  workspace_id: string;
  workspace_name: string;
  role: Role;
}

export interface MeOut {
  user: UserOut;
  memberships: MembershipOut[];
  csrf_token: string;
}

export interface WorkspaceOut {
  id: string;
  name: string;
  description: string | null;
  product_name: string | null;
  product_description: string | null;
  target_users: string | null;
  glossary: Record<string, string>;
  role: Role;
  created_at: string;
}

export interface WorkspacePatch {
  name?: string;
  description?: string | null;
  product_name?: string | null;
  product_description?: string | null;
  target_users?: string | null;
  glossary?: Record<string, string>;
}

export interface MemberOut {
  user_id: string;
  email: string;
  display_name: string | null;
  role: Role;
  added_at: string;
}

export interface Page<T> {
  items: T[];
  next_cursor: string | null;
}

export interface JobRef {
  job_id: string;
  resource_id: string;
  status: "queued";
}

// ---- stored files and imports (API-14 to API-18)
export interface SourceFileOut extends FilePreviewOut {
  id: string;
  duplicate_of_file: { id: string; original_filename: string; uploaded_at: string } | null;
}

export type ImportStatus =
  | "queued"
  | "processing"
  | "completed"
  | "completed_with_errors"
  | "failed"
  | "cancelled";

/** Reconciliation snapshot at completion (D06 §10.1). */
export interface ImportReport {
  received: number;
  imported: number;
  rejected: number;
  duplicates: number;
  filtered: Record<string, number>;
  failed: number;
  reconciled: boolean;
  flags: Record<string, number>;
  pii_masked: Record<string, number>;
  date_range: { from: string | null; to: string | null };
  not_checked: string[];
  error?: string;
}

export interface ImportOut {
  id: string;
  source_type: SourceType;
  status: ImportStatus;
  original_filename: string | null;
  source_file_id: string | null;
  submitted_by: string;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  job_id: string | null;
  progress: { processed: number; total: number } | null;
  error: string | null;
  report: ImportReport | null;
}

export interface StoredRowErrorOut {
  id: string;
  row_number: number;
  kind: "rejected" | "failed";
  stage: string;
  field: string | null;
  code: string;
  message: string;
}
