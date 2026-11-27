import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, type SourceInput } from "@/lib/api/endpoints";
import type { ColumnMapping, ImportOut, ImportStatus, SourceType } from "@/lib/api/types";

export const importKeys = {
  list: (ws: string) => ["imports", ws, "list"] as const,
  detail: (ws: string, id: string) => ["imports", ws, "detail", id] as const,
  errors: (ws: string, id: string, kind: string, stage: string) =>
    ["imports", ws, "errors", id, kind, stage] as const,
};

const FINAL: ImportStatus[] = ["completed", "completed_with_errors", "failed", "cancelled"];
export const isFinal = (status: ImportStatus) => FINAL.includes(status);
const POLL_MS = 2_000;

export function useUploadFile(ws: string) {
  return useMutation({
    mutationFn: ({ input, sourceType }: { input: SourceInput; sourceType: SourceType }) =>
      api.uploadFile(ws, input, sourceType),
  });
}

export function useCheckFile(ws: string) {
  return useMutation({
    mutationFn: (v: { fileId: string; sourceType: SourceType; mapping: ColumnMapping }) =>
      api.checkFile(ws, v.fileId, v.sourceType, v.mapping),
  });
}

/** The key is chosen per file and mapping by the caller, so a double click or a retry never
 * starts a second import (Idempotency-Key, D09 §1). */
export function useStartImport(ws: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (v: {
      fileId: string;
      sourceType: SourceType;
      mapping: ColumnMapping;
      key: string;
    }) =>
      api.startImport(
        ws,
        { source_file_id: v.fileId, source_type: v.sourceType, column_mapping: v.mapping },
        v.key,
      ),
    onSuccess: () => client.invalidateQueries({ queryKey: importKeys.list(ws) }),
  });
}

function anyRunning(items: ImportOut[] | undefined) {
  return items?.some((i) => !isFinal(i.status)) ?? false;
}

export function useImports(ws: string | undefined) {
  return useQuery({
    queryKey: importKeys.list(ws ?? "none"),
    queryFn: ({ signal }) => api.imports(ws ?? "", signal),
    enabled: Boolean(ws),
    refetchInterval: (query) => (anyRunning(query.state.data?.items) ? POLL_MS : false),
  });
}

export function useImport(ws: string | undefined, id: string | undefined) {
  return useQuery({
    queryKey: importKeys.detail(ws ?? "none", id ?? "none"),
    queryFn: ({ signal }) => api.importDetail(ws ?? "", id ?? "", signal),
    enabled: Boolean(ws && id),
    refetchInterval: (query) => {
      const data = query.state.data;
      return data && isFinal(data.status) ? false : POLL_MS;
    },
  });
}

export function useImportErrors(
  ws: string | undefined,
  id: string | undefined,
  filters: { kind: string; stage: string },
  enabled: boolean,
) {
  return useQuery({
    queryKey: importKeys.errors(ws ?? "none", id ?? "none", filters.kind, filters.stage),
    queryFn: ({ signal }) =>
      api.importErrors(
        ws ?? "",
        id ?? "",
        {
          ...(filters.kind && { kind: filters.kind }),
          ...(filters.stage && { stage: filters.stage }),
        },
        signal,
      ),
    enabled: Boolean(ws && id) && enabled,
  });
}
