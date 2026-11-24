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

export interface FilePreviewOut {
  original_filename: string;
  size_bytes: number;
  sha256: string;
  detected_format: "csv" | "json" | "txt";
  detected_encoding: string;
  csv_delimiter: string | null;
  transcript_mode: "speaker_turns" | "paragraphs" | null;
  columns: string[];
  preview_rows: string[][];
  total_rows: number;
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
