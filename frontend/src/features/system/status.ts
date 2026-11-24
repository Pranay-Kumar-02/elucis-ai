import type { CheckOut, CheckStatus, HealthOut } from "@/lib/api/types";

export type Tone = "success" | "warning" | "destructive" | "secondary";

export const checkLabel: Record<CheckStatus, { label: string; tone: Tone }> = {
  ok: { label: "Operational", tone: "success" },
  unavailable: { label: "Unavailable", tone: "destructive" },
  not_configured: { label: "Not set up", tone: "secondary" },
};

export const checkNames: Record<string, string> = {
  database: "Database",
  model_runtime: "AI runtime",
  worker: "Background processing",
};

/** One plain-language summary of service health for the shell and dashboard. */
export function serviceSummary(
  health: HealthOut | undefined,
  failed: boolean,
): { label: string; tone: Tone } {
  if (failed) return { label: "Server not reachable", tone: "destructive" };
  if (!health) return { label: "Checking services", tone: "secondary" };
  if (health.checks["database"]?.status !== "ok")
    return { label: "Database not connected", tone: "destructive" };
  if (health.checks["model_runtime"]?.status !== "ok")
    return { label: "AI features paused", tone: "warning" };
  return { label: "All systems operational", tone: "success" };
}

/** Why AI features are paused, in user terms, or null when they are available. */
export function aiPausedReason(check: CheckOut | undefined): string | null {
  if (!check || check.status === "ok") return null;
  const missing = check.detail?.match(/model not pulled: (.+)$/)?.[1];
  if (missing) return `The ${missing} model isn't installed on this machine yet.`;
  return "The local AI runtime isn't running.";
}
