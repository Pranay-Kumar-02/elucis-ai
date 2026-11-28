import { keepPreviousData, useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api/endpoints";
import type { InsightsFilters } from "@/lib/api/types";

export const insightsKeys = {
  summary: (ws: string, filters: InsightsFilters) => ["insights", ws, "summary", filters] as const,
  theme: (ws: string, id: string, filters: InsightsFilters) =>
    ["insights", ws, "theme", id, filters] as const,
  request: (ws: string, id: string, filters: InsightsFilters) =>
    ["insights", ws, "request", id, filters] as const,
};

/** Dashboard data; the previous result stays on screen while a new filter loads. */
export function useInsights(ws: string | undefined, filters: InsightsFilters, enabled = true) {
  return useQuery({
    queryKey: insightsKeys.summary(ws ?? "none", filters),
    queryFn: ({ signal }) => api.insights(ws ?? "", filters, signal),
    enabled: Boolean(ws) && enabled,
    placeholderData: keepPreviousData,
  });
}

export function useThemeDetail(ws: string, id: string, filters: InsightsFilters, open: boolean) {
  return useQuery({
    queryKey: insightsKeys.theme(ws, id, filters),
    queryFn: ({ signal }) => api.themeDetail(ws, id, filters, signal),
    enabled: open,
  });
}

export function useRequestDetail(ws: string, id: string, filters: InsightsFilters, open: boolean) {
  return useQuery({
    queryKey: insightsKeys.request(ws, id, filters),
    queryFn: ({ signal }) => api.requestDetail(ws, id, filters, signal),
    enabled: open,
  });
}
