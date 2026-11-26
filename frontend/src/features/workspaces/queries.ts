import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { meKey } from "@/features/auth/queries";
import { ApiError } from "@/lib/api/client";
import { api } from "@/lib/api/endpoints";
import type { Role, WorkspacePatch } from "@/lib/api/types";

export const workspaceKeys = {
  all: ["workspaces"] as const,
  one: (id: string) => ["workspaces", id] as const,
  members: (id: string) => ["workspaces", id, "members"] as const,
};

export function useWorkspaces() {
  return useQuery({
    queryKey: workspaceKeys.all,
    queryFn: ({ signal }) => api.workspaces(signal),
  });
}

export function useWorkspace(id: string | undefined, options: { pollUntilGone?: boolean } = {}) {
  return useQuery({
    queryKey: workspaceKeys.one(id ?? "none"),
    queryFn: ({ signal }) => api.workspace(id ?? "", signal),
    enabled: Boolean(id),
    // While a deletion runs, poll until the workspace answers 404 (API-09, IMP-28).
    refetchInterval: (query) =>
      options.pollUntilGone && !(query.state.error instanceof ApiError) ? 1500 : false,
  });
}

/** Workspace changes also change the memberships shown everywhere (``/auth/me``). */
function useRefreshAfter() {
  const client = useQueryClient();
  return async (id?: string) => {
    await Promise.all([
      client.invalidateQueries({ queryKey: meKey }),
      client.invalidateQueries({ queryKey: id ? workspaceKeys.one(id) : workspaceKeys.all }),
      client.invalidateQueries({ queryKey: workspaceKeys.all, exact: true }),
    ]);
  };
}

export function useCreateWorkspace() {
  const refresh = useRefreshAfter();
  return useMutation({ mutationFn: api.createWorkspace, onSuccess: () => refresh() });
}

export function useUpdateWorkspace(id: string) {
  const refresh = useRefreshAfter();
  return useMutation({
    mutationFn: (patch: WorkspacePatch) => api.updateWorkspace(id, patch),
    onSuccess: () => refresh(id),
  });
}

export function useDeleteWorkspace(id: string) {
  // One key for the life of the confirmation form, so a retried click or a repeated request
  // never queues a second deletion (Idempotency-Key, D09 §1).
  const [key] = useState(() => crypto.randomUUID());
  return useMutation({
    mutationFn: (confirmName: string) => api.deleteWorkspace(id, confirmName, key),
  });
}

export function useMembers(id: string | undefined) {
  return useQuery({
    queryKey: workspaceKeys.members(id ?? "none"),
    queryFn: ({ signal }) => api.members(id ?? "", signal),
    enabled: Boolean(id),
  });
}

function useMemberMutation<T>(id: string, fn: (input: T) => Promise<unknown>) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: async () => {
      await Promise.all([
        client.invalidateQueries({ queryKey: workspaceKeys.members(id) }),
        client.invalidateQueries({ queryKey: meKey }),
      ]);
    },
  });
}

export function useAddMember(id: string) {
  return useMemberMutation(id, (input: { email: string; role: Role }) => api.addMember(id, input));
}

export function useChangeRole(id: string) {
  return useMemberMutation(id, (input: { userId: string; role: Role }) =>
    api.changeRole(id, input.userId, input.role),
  );
}

export function useRemoveMember(id: string) {
  return useMemberMutation(id, (userId: string) => api.removeMember(id, userId));
}
