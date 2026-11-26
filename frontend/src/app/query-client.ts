import { MutationCache, QueryCache, QueryClient, type QueryKey } from "@tanstack/react-query";

import { meKey } from "@/features/auth/queries";
import { ApiError } from "@/lib/api/client";

function isMe(key: QueryKey | undefined): boolean {
  return JSON.stringify(key) === JSON.stringify(meKey);
}

export function createQueryClient(): QueryClient {
  // A 401 anywhere means the session ended (sign-out elsewhere, idle timeout, A-07): check
  // the session again so the guard sends the user to sign-in. The session query itself is
  // excluded, or a 401 there would trigger itself forever.
  const onError = (error: unknown, key?: QueryKey) => {
    if (error instanceof ApiError && error.status === 401 && !isMe(key)) {
      void client.invalidateQueries({ queryKey: meKey });
    }
  };
  const client: QueryClient = new QueryClient({
    queryCache: new QueryCache({
      onError: (error, query) => {
        onError(error, query.queryKey);
      },
    }),
    mutationCache: new MutationCache({
      onError: (error) => {
        onError(error);
      },
    }),
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
  return client;
}
