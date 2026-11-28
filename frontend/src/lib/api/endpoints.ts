import { apiRequest } from "@/lib/api/client";
import type {
  AnalysisStatusOut,
  ColumnMapping,
  DatabaseHealthOut,
  FilePreviewOut,
  HealthOut,
  ImportOut,
  InsightsFilters,
  InsightsOut,
  ImportStatus,
  JobRef,
  MemberOut,
  MeOut,
  ModelRuntimeHealthOut,
  Page,
  RequestOut,
  Role,
  SourceFileOut,
  SourceInfoOut,
  SourceType,
  StoredRowErrorOut,
  ThemeOut,
  UserOut,
  ValidationReportOut,
  WorkspaceOut,
  WorkspacePatch,
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

  // ---- authentication (API-01 to API-04)
  register: (body: { email: string; password: string; display_name?: string }) =>
    apiRequest<UserOut>("/auth/register", { method: "POST", body }),
  login: (body: { email: string; password: string }) =>
    apiRequest<MeOut>("/auth/login", { method: "POST", body }),
  logout: () => apiRequest<null>("/auth/logout", { method: "POST" }),
  me: (signal?: AbortSignal) => apiRequest<MeOut>("/auth/me", { ...(signal && { signal }) }),
  // ---- workspaces (API-05 to API-09)
  workspaces: (signal?: AbortSignal) =>
    apiRequest<Page<WorkspaceOut>>("/workspaces?limit=200", { ...(signal && { signal }) }),
  createWorkspace: (body: { name: string; description?: string }) =>
    apiRequest<WorkspaceOut>("/workspaces", { method: "POST", body }),
  workspace: (id: string, signal?: AbortSignal) =>
    apiRequest<WorkspaceOut>(`/workspaces/${id}`, { ...(signal && { signal }) }),
  updateWorkspace: (id: string, body: WorkspacePatch) =>
    apiRequest<WorkspaceOut>(`/workspaces/${id}`, { method: "PATCH", body }),
  deleteWorkspace: (id: string, confirmName: string, idempotencyKey: string) =>
    apiRequest<JobRef>(`/workspaces/${id}`, {
      method: "DELETE",
      body: { confirm_name: confirmName },
      headers: { "Idempotency-Key": idempotencyKey },
    }),
  // ---- members (API-10 to API-13)
  members: (id: string, signal?: AbortSignal) =>
    apiRequest<Page<MemberOut>>(`/workspaces/${id}/members?limit=200`, {
      ...(signal && { signal }),
    }),
  addMember: (id: string, body: { email: string; role: Role }) =>
    apiRequest<MemberOut>(`/workspaces/${id}/members`, { method: "POST", body }),
  changeRole: (id: string, userId: string, role: Role) =>
    apiRequest<MemberOut>(`/workspaces/${id}/members/${userId}`, {
      method: "PATCH",
      body: { role },
    }),
  removeMember: (id: string, userId: string) =>
    apiRequest<null>(`/workspaces/${id}/members/${userId}`, { method: "DELETE" }),

  // ---- stored files and imports (API-14 to API-18)
  uploadFile: (ws: string, input: SourceInput, sourceType: SourceType) =>
    apiRequest<SourceFileOut>(`/workspaces/${ws}/files`, {
      method: "POST",
      body: sourceForm(input, sourceType),
      timeoutMs: 120_000,
    }),
  checkFile: (ws: string, fileId: string, sourceType: SourceType, mapping: ColumnMapping) =>
    apiRequest<ValidationReportOut>(`/workspaces/${ws}/files/${fileId}/check`, {
      method: "POST",
      body: { source_type: sourceType, column_mapping: mapping },
      timeoutMs: 120_000,
    }),
  startImport: (
    ws: string,
    body: { source_file_id: string; source_type: SourceType; column_mapping: ColumnMapping },
    idempotencyKey: string,
  ) =>
    apiRequest<JobRef>(`/workspaces/${ws}/imports`, {
      method: "POST",
      body,
      headers: { "Idempotency-Key": idempotencyKey },
      timeoutMs: 120_000,
    }),
  imports: (ws: string, signal?: AbortSignal, status?: ImportStatus) =>
    apiRequest<Page<ImportOut>>(
      `/workspaces/${ws}/imports?limit=50${status ? `&status=${status}` : ""}`,
      { ...(signal && { signal }) },
    ),
  importDetail: (ws: string, id: string, signal?: AbortSignal) =>
    apiRequest<ImportOut>(`/workspaces/${ws}/imports/${id}`, { ...(signal && { signal }) }),
  importErrors: (
    ws: string,
    id: string,
    filters: { kind?: string; stage?: string },
    signal?: AbortSignal,
  ) => {
    const query = new URLSearchParams({ limit: "200" });
    if (filters.kind) query.set("kind", filters.kind);
    if (filters.stage) query.set("stage", filters.stage);
    return apiRequest<Page<StoredRowErrorOut>>(
      `/workspaces/${ws}/imports/${id}/errors?${query.toString()}`,
      { ...(signal && { signal }) },
    );
  },

  // ---- analysis runs (API-31, API-32)
  analysisStatus: (ws: string, signal?: AbortSignal) =>
    apiRequest<AnalysisStatusOut>(`/workspaces/${ws}/analysis`, { ...(signal && { signal }) }),
  startAnalysis: (ws: string, idempotencyKey: string) =>
    apiRequest<JobRef>(`/workspaces/${ws}/analysis-runs`, {
      method: "POST",
      body: {},
      headers: { "Idempotency-Key": idempotencyKey },
      timeoutMs: 30_000,
    }),

  // ---- insights (IMP-35, API-34, API-38)
  insights: (ws: string, filters: InsightsFilters, signal?: AbortSignal) =>
    apiRequest<InsightsOut>(`/workspaces/${ws}/insights?${insightsQuery(filters)}`, {
      ...(signal && { signal }),
      timeoutMs: 60_000,
    }),
  themeDetail: (ws: string, id: string, filters: InsightsFilters, signal?: AbortSignal) =>
    apiRequest<ThemeOut>(`/workspaces/${ws}/themes/${id}?${insightsQuery(filters)}`, {
      ...(signal && { signal }),
    }),
  requestDetail: (ws: string, id: string, filters: InsightsFilters, signal?: AbortSignal) =>
    apiRequest<RequestOut>(`/workspaces/${ws}/requests/${id}?${insightsQuery(filters)}`, {
      ...(signal && { signal }),
    }),
};

/** Period, source and pain-point filters as query parameters (IMP-35). */
export function insightsQuery(filters: InsightsFilters): string {
  const query = new URLSearchParams();
  if (filters.from) query.set("from", filters.from);
  if (filters.to) query.set("to", filters.to);
  if (filters.source_type) query.set("source_type", filters.source_type);
  if (filters.pain_points_only) query.set("pain_points_only", "true");
  return query.toString();
}
