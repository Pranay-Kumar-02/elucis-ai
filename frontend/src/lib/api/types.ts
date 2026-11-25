/** Response types mirroring backend Pydantic schemas (copilot/schemas, modules/ingestion). */

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
