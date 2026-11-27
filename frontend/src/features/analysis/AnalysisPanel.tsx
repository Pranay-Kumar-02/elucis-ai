import { Link } from "react-router";

import { ErrorAlert } from "@/components/layout/ErrorAlert";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  categoryLabels,
  isActive,
  stepLabels,
  useAnalysisStatus,
  useStartAnalysis,
} from "@/features/analysis/queries";
import { formatWhen } from "@/features/imports/labels";
import type { MembershipOut, RunOut } from "@/lib/api/types";

function progressText(run: RunOut): string {
  const step = run.step ? (stepLabels[run.step] ?? run.step) : "Waiting for the worker to start";
  const p = run.progress ?? {};
  const done = Object.entries(p).find(([k, v]) => k !== "step" && typeof v === "number");
  return done ? `${step} (${String(done[1])} done)` : step;
}

/** Analysis progress and results (UI-05 subset): run, follow, and read the outcome. */
export function AnalysisPanel({ membership }: { membership: MembershipOut }) {
  const ws = membership.workspace_id;
  const status = useAnalysisStatus(ws);
  const start = useStartAnalysis(ws);
  const canRun = membership.role === "editor" || membership.role === "owner";

  if (status.isPending) {
    return <Skeleton className="h-28 w-full" aria-label="Loading analysis status" />;
  }
  if (status.isError) {
    return <ErrorAlert error={status.error} title="Analysis status could not load" />;
  }
  const { analysable_records: records, records_since_last_run: since } = status.data;
  const latest = status.data.latest_run;
  const current = status.data.current_run;
  const running = isActive(latest);

  return (
    <section aria-labelledby="analysis-heading" className="rounded-xl border bg-card">
      <div className="flex flex-wrap items-center justify-between gap-4 border-b px-6 py-4">
        <div>
          <h2 id="analysis-heading" className="text-[15px] font-semibold">
            Analysis
          </h2>
          <p className="text-[13px] text-muted-foreground">
            {records === 0
              ? "No analysable records; import data first."
              : `${records.toLocaleString()} analysable records · ${since.toLocaleString()} added since the last run`}
          </p>
        </div>
        {records === 0 ? (
          <Button asChild variant="outline" size="sm">
            <Link to="/imports">Import feedback</Link>
          </Button>
        ) : (
          canRun && (
            <Button
              onClick={() => {
                start.mutate();
              }}
              disabled={running || start.isPending}
            >
              {running ? "Analysis running…" : "Run analysis"}
            </Button>
          )
        )}
      </div>
      <div className="space-y-4 px-6 py-4">
        {start.isError && <ErrorAlert error={start.error} title="The run could not start" />}
        {running && latest && (
          <p className="text-sm" role="status">
            {progressText(latest)}
          </p>
        )}
        {latest?.status === "failed" && (
          <Alert variant="destructive">
            <AlertTitle>The last run failed</AlertTitle>
            <AlertDescription>
              {latest.error ?? "The run stopped before it finished."} Previous results are still
              shown.
            </AlertDescription>
          </Alert>
        )}
        {current?.report ? (
          <dl className="flex flex-wrap gap-x-10 gap-y-3">
            <div>
              <dt className="text-[12px] text-muted-foreground">Last run</dt>
              <dd className="text-sm font-medium">
                {current.finished_at ? formatWhen(current.finished_at) : "–"}
              </dd>
            </div>
            <div>
              <dt className="text-[12px] text-muted-foreground">Records analysed</dt>
              <dd className="tabular text-[22px] font-semibold">
                {current.report.embedded.toLocaleString()}
              </dd>
            </div>
            {current.report.themes !== undefined && (
              <div>
                <dt className="text-[12px] text-muted-foreground">Themes found</dt>
                <dd className="tabular text-[22px] font-semibold">
                  {current.report.themes.toLocaleString()}
                </dd>
              </div>
            )}
            {current.report.unclassified > 0 && (
              <div>
                <dt className="text-[12px] text-muted-foreground">Not labelled</dt>
                <dd className="tabular text-[22px] font-semibold">
                  {current.report.unclassified.toLocaleString()}
                </dd>
              </div>
            )}
            {current.report.embedding_failed > 0 && (
              <div>
                <dt className="text-[12px] text-muted-foreground">Could not be read</dt>
                <dd className="tabular text-[22px] font-semibold">
                  {current.report.embedding_failed.toLocaleString()}
                </dd>
              </div>
            )}
          </dl>
        ) : null}
        {current?.report?.categories && Object.keys(current.report.categories).length > 0 && (
          <div>
            <h3 className="text-[13px] font-semibold">Feedback by type</h3>
            <ul className="mt-1 flex flex-wrap gap-x-6 gap-y-1 text-[13px]">
              {Object.entries(current.report.categories)
                .sort(([, a], [, b]) => b - a)
                .map(([category, n]) => (
                  <li key={category}>
                    {categoryLabels[category] ?? category}:{" "}
                    <span className="tabular font-medium">{n.toLocaleString()}</span>
                  </li>
                ))}
            </ul>
          </div>
        )}
        {!current?.report && !running && records > 0 && (
          <p className="text-[13px] text-muted-foreground">
            No analysis has run yet in this workspace.
          </p>
        )}
      </div>
    </section>
  );
}
