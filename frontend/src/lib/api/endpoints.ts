import { apiRequest } from "@/lib/api/client";
import type {
  DatabaseHealthOut,
  FilePreviewOut,
  HealthOut,
  ModelRuntimeHealthOut,
  SourceInfoOut,
} from "@/lib/api/types";

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
  previewFile: (file: File, rows = 20) => {
    const form = new FormData();
    form.append("file", file);
    return apiRequest<FilePreviewOut>(`/dev/sources/preview?rows=${rows}`, {
      method: "POST",
      body: form,
      timeoutMs: 60_000,
    });
  },
};
