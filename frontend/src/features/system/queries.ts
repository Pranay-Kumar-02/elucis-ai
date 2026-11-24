import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api/endpoints";

export const healthKeys = {
  all: ["health"] as const,
  overall: () => [...healthKeys.all, "overall"] as const,
  database: () => [...healthKeys.all, "database"] as const,
  modelRuntime: () => [...healthKeys.all, "model-runtime"] as const,
};

export function useHealth() {
  return useQuery({
    queryKey: healthKeys.overall(),
    queryFn: ({ signal }) => api.health(signal),
    refetchInterval: 30_000,
  });
}

export function useDatabaseHealth() {
  return useQuery({
    queryKey: healthKeys.database(),
    queryFn: ({ signal }) => api.databaseHealth(signal),
  });
}

export function useModelRuntimeHealth() {
  return useQuery({
    queryKey: healthKeys.modelRuntime(),
    queryFn: ({ signal }) => api.modelRuntimeHealth(signal),
  });
}
