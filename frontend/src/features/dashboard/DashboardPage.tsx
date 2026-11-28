import { CheckCircle2, CircleAlert, CircleDashed } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router";

import { PageHeader } from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { product } from "@/config/product";
import { AnalysisPanel } from "@/features/analysis/AnalysisPanel";
import { isActive, useAnalysisStatus } from "@/features/analysis/queries";
import { InsightsView } from "@/features/insights/InsightsView";
import { useHealth } from "@/features/system/queries";
import { aiPausedReason } from "@/features/system/status";
import { useActiveWorkspace } from "@/features/workspaces/active";
import { cn } from "@/lib/utils";

type StepState = "done" | "action" | "waiting";

interface SetupStep {
  title: string;
  detail: string;
  state: StepState;
  action?: ReactNode;
}

const stateMeta: Record<
  StepState,
  { icon: typeof CheckCircle2; label: string; className: string }
> = {
  done: { icon: CheckCircle2, label: "Done", className: "text-success" },
  action: { icon: CircleAlert, label: "Needs attention", className: "text-warning" },
  waiting: {
    icon: CircleDashed,
    label: "Waiting on an earlier step",
    className: "text-muted-foreground",
  },
};

/**
 * Dashboard (UI-11). With a successful analysis it is the Insights page; before that it is
 * the empty state D12 §4 asks for ("Import and analyse feedback to see insights"): why it
 * is empty and the next action. Every status shown comes from the live API.
 */
export function DashboardPage() {
  const health = useHealth();
  const db = health.data?.checks["database"];
  const ai = health.data?.checks["model_runtime"];
  const dbReady = db?.status === "ok";
  const aiReason = aiPausedReason(ai);
  const { active } = useActiveWorkspace();
  const analysis = useAnalysisStatus(dbReady ? active?.workspace_id : undefined);
  const currentRun = analysis.data?.current_run;

  if (active && currentRun) {
    return (
      <>
        <PageHeader
          title="Insights"
          description="Pain points, themes and feature requests from your customers' feedback. Every figure links back to the records behind it."
        />
        <div className="space-y-8">
          <AnalysisPanel membership={active} />
          <InsightsView ws={active.workspace_id} rerunning={isActive(analysis.data?.latest_run)} />
        </div>
      </>
    );
  }

  const steps: SetupStep[] = [
    {
      title: "Connect the database",
      detail: dbReady
        ? "Feedback, analysis results and decisions are stored securely."
        : "Needed to store feedback, analysis results and decisions. An administrator sets this up once.",
      state: dbReady ? "done" : "action",
    },
    {
      title: "Create a workspace",
      detail: active
        ? `You are working in “${active.workspace_name}”.`
        : "A workspace holds one product’s feedback and decisions. Invite your team to it.",
      state: active ? "done" : dbReady ? "action" : "waiting",
      ...(!active &&
        dbReady && {
          action: (
            <Button asChild size="sm" variant="outline">
              <Link to="/workspaces">Create a workspace</Link>
            </Button>
          ),
        }),
    },
    {
      title: "Install the AI models",
      detail: aiReason
        ? `${aiReason} Classification, themes and document drafting need it.`
        : "The local models are installed and responding.",
      state: aiReason ? "action" : "done",
    },
    {
      title: "Import your first feedback",
      detail: dbReady
        ? "Upload reviews, tickets or interview notes as CSV, JSON or text."
        : "You can check a file's format and columns now. Importing starts once the database is connected.",
      state: dbReady ? "action" : "waiting",
      action: (
        <Button asChild size="sm" variant="outline">
          <Link to="/imports">{dbReady ? "Import feedback" : "Check a file"}</Link>
        </Button>
      ),
    },
  ];

  return (
    <div className="space-y-10">
      <section className="max-w-2xl">
        <h1 className="text-[32px] leading-[1.15] font-semibold tracking-[-0.02em]">
          Welcome to {product.name}
        </h1>
        <p className="mt-3 text-[16px] leading-relaxed text-muted-foreground">
          Import customer feedback to see the pain points, trends and opportunities worth building
          next. Every figure links back to the feedback behind it, so each decision has evidence.
        </p>
        <div className="mt-6 flex flex-wrap gap-2">
          <Button asChild>
            <Link to="/imports">Import feedback</Link>
          </Button>
          <Button asChild variant="ghost">
            <Link to="/settings/system">View system status</Link>
          </Button>
        </div>
      </section>

      {active && dbReady && <AnalysisPanel membership={active} />}

      <section aria-labelledby="setup-heading" className="rounded-xl border bg-card">
        <div className="flex flex-wrap items-baseline justify-between gap-2 border-b px-6 py-4">
          <h2 id="setup-heading" className="text-[15px] font-semibold">
            Set up your workspace
          </h2>
          {health.data && (
            <p className="text-[13px] text-muted-foreground">
              {steps.filter((s) => s.state === "done").length} of {steps.length} complete
            </p>
          )}
        </div>
        {health.isPending ? (
          <div className="space-y-3 p-6">
            <Skeleton className="h-12" />
            <Skeleton className="h-12" />
            <Skeleton className="h-12" />
          </div>
        ) : health.isError ? (
          <p className="px-6 py-5 text-destructive">
            The server isn't responding, so setup status can't be checked. Start the backend and
            reload.
          </p>
        ) : (
          <ol className="divide-y">
            {steps.map((step, index) => {
              const meta = stateMeta[step.state];
              const Icon = meta.icon;
              return (
                <li
                  key={step.title}
                  className="flex flex-wrap items-center gap-x-4 gap-y-3 px-6 py-4"
                >
                  <div className="flex min-w-0 flex-1 basis-72 items-start gap-3">
                    <span className="tabular mt-0.5 w-4 text-[13px] text-muted-foreground">
                      {index + 1}
                    </span>
                    <Icon
                      className={cn("mt-0.5 size-5 shrink-0", meta.className)}
                      aria-label={meta.label}
                    />
                    <div className="min-w-0">
                      <p className="font-medium">{step.title}</p>
                      <p className="text-[13px] text-muted-foreground">{step.detail}</p>
                    </div>
                  </div>
                  {step.action}
                </li>
              );
            })}
          </ol>
        )}
      </section>
    </div>
  );
}
