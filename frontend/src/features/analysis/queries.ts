import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api/endpoints";
import type { RunOut } from "@/lib/api/types";

export const analysisKeys = {
  status: (ws: string) => ["analysis", ws, "status"] as const,
};

export const isActive = (run: RunOut | null | undefined) =>
  run?.status === "queued" || run?.status === "running";

export function useAnalysisStatus(ws: string | undefined) {
  return useQuery({
    queryKey: analysisKeys.status(ws ?? "none"),
    queryFn: ({ signal }) => api.analysisStatus(ws ?? "", signal),
    enabled: Boolean(ws),
    refetchInterval: (query) => (isActive(query.state.data?.latest_run) ? 2_000 : false),
  });
}

export function useStartAnalysis(ws: string) {
  const client = useQueryClient();
  return useMutation({
    // A fresh key per click: the server refuses a second run while one is active (409).
    mutationFn: () => api.startAnalysis(ws, crypto.randomUUID()),
    onSettled: () => client.invalidateQueries({ queryKey: ["analysis", ws] }),
  });
}

/** Plain names for the analysis steps (D06 §1), shown while a run is in progress. */
export const stepLabels: Record<string, string> = {
  embed: "Reading the meaning of each record",
  classify: "Labelling issues, requests and sentiment",
  cluster: "Grouping feedback into themes",
  name: "Naming themes from their evidence",
  requests: "Grouping feature requests",
  stats: "Counting customers and weekly trends",
};
