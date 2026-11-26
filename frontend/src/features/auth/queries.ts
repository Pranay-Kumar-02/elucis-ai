import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError, setCsrfToken } from "@/lib/api/client";
import { api } from "@/lib/api/endpoints";
import type { MeOut } from "@/lib/api/types";

export const meKey = ["auth", "me"] as const;

/** The signed-in user (API-04). A 401 means "not signed in", which the guard handles. */
export function useMe() {
  return useQuery({
    queryKey: meKey,
    queryFn: async ({ signal }) => {
      const me = await api.me(signal);
      setCsrfToken(me.csrf_token);
      return me;
    },
    staleTime: 60_000,
  });
}

function useAcceptSession() {
  const client = useQueryClient();
  return (me: MeOut) => {
    setCsrfToken(me.csrf_token);
    client.setQueryData(meKey, me);
  };
}

export function useSignIn() {
  const accept = useAcceptSession();
  return useMutation({ mutationFn: api.login, onSuccess: accept });
}

export function useRegister() {
  const accept = useAcceptSession();
  return useMutation({
    mutationFn: async (input: { email: string; password: string; display_name?: string }) => {
      await api.register(input);
      return api.login({ email: input.email, password: input.password });
    },
    onSuccess: accept,
  });
}

export function useSignOut() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: api.logout,
    onSettled: () => {
      setCsrfToken(null);
      // Drop every cached response so nothing from this session is shown to the next user.
      client.clear();
    },
  });
}

/** Minutes until sign-in is allowed again after A-08 throttling, or null. */
export function retryAfterMinutes(error: unknown): number | null {
  if (!(error instanceof ApiError) || error.code !== "too_many_attempts") return null;
  const seconds = Number(error.details.find((d) => d.field === "retry_after_s")?.issue);
  return Number.isFinite(seconds) && seconds > 0 ? Math.ceil(seconds / 60) : null;
}

/** Only same-site paths are accepted as a return target after sign-in. */
export function safeNext(next: string | null): string {
  return next?.startsWith("/") && !next.startsWith("//") ? next : "/";
}
