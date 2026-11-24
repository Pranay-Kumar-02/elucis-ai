import { QueryClient } from "@tanstack/react-query";

import { ApiError } from "@/lib/api/client";

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 15_000,
        refetchOnWindowFocus: false,
        // Retry network problems once; never retry 4xx responses (they will not change).
        retry: (failureCount, error) =>
          !(error instanceof ApiError && error.status >= 400 && error.status < 500) &&
          failureCount < 1,
      },
    },
  });
}
