import { Sparkles } from "lucide-react";
import { Link } from "react-router";

import { useHealth } from "@/features/system/queries";
import { aiPausedReason } from "@/features/system/status";

/** D12 §2: when the AI runtime is unavailable, say so once and keep the rest usable. */
export function AiRuntimeBanner() {
  const { data } = useHealth();
  const reason = aiPausedReason(data?.checks["model_runtime"]);
  if (!reason) return null;
  return (
    <div
      role="status"
      className="flex flex-wrap items-center gap-x-3 gap-y-1 border-b border-warning/25 bg-warning/10 px-4 py-2 text-[13px] md:px-8"
    >
      <Sparkles className="size-4 text-warning" aria-hidden />
      <span>
        <strong className="font-medium">AI features are paused.</strong> {reason} Everything else
        works.
      </span>
      <Link
        to="/settings/system"
        className="font-medium text-primary underline-offset-4 hover:underline"
      >
        View details
      </Link>
    </div>
  );
}
