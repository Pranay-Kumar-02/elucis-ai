import { cn } from "@/lib/utils";
import { useHealth } from "@/features/system/queries";
import { overallLabel } from "@/features/system/status";

const dot: Record<string, string> = {
  success: "bg-success",
  warning: "bg-warning",
  destructive: "bg-destructive",
  secondary: "bg-muted-foreground",
};

/** Small live indicator of backend readiness (polls GET /api/v1/health). */
export function StatusIndicator({ compact = false }: { compact?: boolean }) {
  const { data, isPending, isError } = useHealth();
  const state = isPending
    ? { label: "Checking…", tone: "secondary" }
    : isError
      ? { label: "API not reachable", tone: "destructive" }
      : overallLabel[data.status];
  return (
    <div className="flex items-center gap-2 text-xs text-muted-foreground" aria-live="polite">
      <span className={cn("size-2 rounded-full", dot[state.tone])} aria-hidden />
      {compact ? <span className="sr-only">{state.label}</span> : <span>{state.label}</span>}
    </div>
  );
}
