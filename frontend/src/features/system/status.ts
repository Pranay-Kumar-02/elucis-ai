import type { CheckStatus, OverallStatus } from "@/lib/api/types";

type Tone = "success" | "warning" | "destructive" | "secondary";

export const overallLabel: Record<OverallStatus, { label: string; tone: Tone }> = {
  ok: { label: "All systems ready", tone: "success" },
  degraded: { label: "Degraded", tone: "warning" },
  unavailable: { label: "Unavailable", tone: "destructive" },
};

export const checkLabel: Record<CheckStatus, { label: string; tone: Tone }> = {
  ok: { label: "Ready", tone: "success" },
  unavailable: { label: "Unavailable", tone: "destructive" },
  not_configured: { label: "Not set up yet", tone: "secondary" },
};

export const checkNames: Record<string, string> = {
  database: "Database (PostgreSQL + pgvector)",
  model_runtime: "Model runtime (Ollama)",
  worker: "Background worker",
};
