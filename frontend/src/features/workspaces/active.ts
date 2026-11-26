import { useSyncExternalStore } from "react";

import { useMe } from "@/features/auth/queries";
import type { MembershipOut } from "@/lib/api/types";

/**
 * The workspace the user is working in (FR-AUTH-10). Only a remembered preference: the
 * server checks membership on every request and derives the workspace from the URL and
 * the session (SEC-04), so a stale or edited value can never grant access.
 */
const STORAGE_KEY = "elucis.activeWorkspace";
const listeners = new Set<() => void>();

function read(): string | null {
  try {
    return localStorage.getItem(STORAGE_KEY);
  } catch {
    return null; // storage disabled: fall back to the first membership
  }
}

export function rememberWorkspace(id: string | null): void {
  try {
    if (id) localStorage.setItem(STORAGE_KEY, id);
    else localStorage.removeItem(STORAGE_KEY);
  } catch {
    // Not remembered across reloads; the choice still applies in this tab.
  }
  for (const notify of listeners) notify();
}

function subscribe(notify: () => void): () => void {
  listeners.add(notify);
  return () => {
    listeners.delete(notify);
  };
}

export interface ActiveWorkspace {
  active: MembershipOut | null;
  memberships: MembershipOut[];
  select: (id: string) => void;
}

export function useActiveWorkspace(): ActiveWorkspace {
  const remembered = useSyncExternalStore(subscribe, read, () => null);
  const memberships = useMe().data?.memberships ?? [];
  const active = memberships.find((m) => m.workspace_id === remembered) ?? memberships[0] ?? null;
  return { active, memberships, select: rememberWorkspace };
}
