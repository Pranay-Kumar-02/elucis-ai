import { Link } from "react-router";

import { useHealth } from "@/features/system/queries";
import { serviceSummary, type Tone } from "@/features/system/status";
import { cn } from "@/lib/utils";

const dot: Record<Tone, string> = {
  success: "bg-success",
  warning: "bg-warning",
  destructive: "bg-destructive",
  secondary: "bg-muted-foreground",
};

/** Live service summary (polls GET /api/v1/health); opens System status. */
export function StatusIndicator({ className }: { className?: string }) {
  const { data, isError } = useHealth();
  const state = serviceSummary(data, isError);
  return (
    <Link
      to="/settings/system"
      aria-live="polite"
      className={cn(
        "inline-flex items-center gap-2 rounded-md px-2 py-1 text-[13px] text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground",
        className,
      )}
    >
      <span className={cn("size-2 rounded-full", dot[state.tone])} aria-hidden />
      {state.label}
    </Link>
  );
}
