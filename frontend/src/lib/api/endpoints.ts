import { apiRequest } from "@/lib/api/client";
import type {
  ColumnMapping,
  DatabaseHealthOut,
  FilePreviewOut,
  HealthOut,
  ModelRuntimeHealthOut,
  SourceInfoOut,
  SourceType,
  ValidationReportOut,
} from "@/lib/api/types";

/** Feedback comes from an uploaded file or from pasted text (FR-ING-10). */
export type SourceInput = { kind: "file"; file: File } | { kind: "text"; text: string };

function sourceForm(input: SourceInput, sourceType: SourceType, mapping?: ColumnMapping): FormData {
  const form = new FormData();
  if (input.kind === "file") form.append("file", input.file);
  else form.append("pasted_text", input.text);
  form.append("source_type", sourceType);
  if (mapping) form.append("mapping", JSON.stringify(mapping));
  return form;
}

// Health endpoints return 503 with a normal body when a dependency is down.
const HEALTH_STATUSES = [503] as const;

export const api = {
  health: (signal?: AbortSignal) =>
    apiRequest<HealthOut>("/health", {
      acceptStatuses: HEALTH_STATUSES,
      ...(signal && { signal }),
    }),
  databaseHealth: (signal?: AbortSignal) =>
    apiRequest<DatabaseHealthOut>("/health/database", {
      acceptStatuses: HEALTH_STATUSES,
      ...(signal && { signal }),
    }),
  modelRuntimeHealth: (signal?: AbortSignal) =>
    apiRequest<ModelRuntimeHealthOut>("/health/model-runtime", {
      acceptStatuses: HEALTH_STATUSES,
      ...(signal && { signal }),
    }),
  sourceAdapters: (signal?: AbortSignal) =>
    apiRequest<SourceInfoOut[]>("/dev/sources/adapters", { ...(signal && { signal }) }),
  previewSource: (input: SourceInput, sourceType: SourceType, rows = 20) =>
    apiRequest<FilePreviewOut>(`/dev/sources/preview?rows=${rows}`, {
      method: "POST",
      body: sourceForm(input, sourceType),
      timeoutMs: 60_000,
    }),
  validateSource: (input: SourceInput, sourceType: SourceType, mapping: ColumnMapping) =>
    apiRequest<ValidationReportOut>("/dev/sources/validate", {
      method: "POST",
      body: sourceForm(input, sourceType, mapping),
      timeoutMs: 120_000,
    }),
};
