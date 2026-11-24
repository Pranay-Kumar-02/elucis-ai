import { RefreshCw } from "lucide-react";
import type { ReactNode } from "react";

import { PageHeader } from "@/components/layout/PageHeader";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useDatabaseHealth, useHealth, useModelRuntimeHealth } from "@/features/system/queries";
import { aiPausedReason, checkLabel } from "@/features/system/status";
import type { CheckStatus } from "@/lib/api/types";

function ServiceRow({
  name,
  purpose,
  status,
  statusLabel,
  loading,
  children,
}: {
  name: string;
  purpose: string;
  status: CheckStatus | undefined;
  statusLabel?: string | undefined;
  loading: boolean;
  children?: ReactNode;
}) {
  return (
    <li className="grid gap-4 px-6 py-5 md:grid-cols-[17rem_minmax(0,1fr)]">
      <div>
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="font-semibold">{name}</h2>
          {status && (
            <Badge variant={checkLabel[status].tone}>
              {statusLabel ?? checkLabel[status].label}
            </Badge>
          )}
        </div>
        <p className="mt-1 text-[13px] text-muted-foreground">{purpose}</p>
      </div>
      <div className="min-w-0">{loading ? <Skeleton className="h-16" /> : children}</div>
    </li>
  );
}

function Facts({ items }: { items: [string, ReactNode][] }) {
  const shown = items.filter(([, v]) => v !== null && v !== undefined && v !== "");
  if (shown.length === 0) return null;
  return (
    <dl className="grid grid-cols-[max-content_minmax(0,1fr)] gap-x-6 gap-y-1.5 text-[13px]">
      {shown.map(([label, value]) => (
        <div key={label} className="contents">
          <dt className="text-muted-foreground">{label}</dt>
          <dd className="font-medium break-words">{value}</dd>
        </div>
      ))}
    </dl>
  );
}

/** Settings › System status: live checks of everything the product depends on. */
export function SystemStatusPage() {
  const overall = useHealth();
  const db = useDatabaseHealth();
  const model = useModelRuntimeHealth();
  const worker = overall.data?.checks["worker"];
  const refreshing = overall.isFetching || db.isFetching || model.isFetching;
  const refresh = () => {
    void overall.refetch();
    void db.refetch();
    void model.refetch();
  };
  const aiReason = aiPausedReason(model.data);

  return (
    <>
      <PageHeader
        title="System status"
        description="Live checks of the services the product depends on. Refreshes every 30 seconds."
        actions={
          <Button variant="outline" size="sm" onClick={refresh} disabled={refreshing}>
            <RefreshCw className={refreshing ? "animate-spin" : undefined} aria-hidden />
            Refresh
          </Button>
        }
      />
      {overall.isError && (
        <Alert variant="destructive" className="mb-6">
          <AlertTitle>The server isn't responding</AlertTitle>
          <AlertDescription>Start the backend, then refresh this page.</AlertDescription>
        </Alert>
      )}
      <ul className="divide-y rounded-xl border bg-card">
        <ServiceRow
          name="Database"
          purpose="Stores feedback, analysis results and decisions."
          status={db.data?.status}
          statusLabel={db.data && db.data.status !== "ok" ? "Not connected" : undefined}
          loading={db.isPending}
        >
          {db.data?.status === "ok" ? (
            <Facts
              items={[
                ["PostgreSQL", db.data.server_version],
                [
                  "Vector search",
                  db.data.pgvector_version && `pgvector ${db.data.pgvector_version}`,
                ],
                ["Database", db.data.database],
                ["Response time", db.data.latency_ms !== null ? `${db.data.latency_ms} ms` : null],
              ]}
            />
          ) : (
            <p className="text-[13px]">
              Feedback can't be imported or analysed until an administrator connects PostgreSQL.
            </p>
          )}
        </ServiceRow>
        <ServiceRow
          name="AI runtime"
          purpose="Runs the local models for classification, themes and drafting."
          status={model.data?.status}
          loading={model.isPending}
        >
          <div className="space-y-3">
            {aiReason && (
              <p className="text-[13px]">{aiReason} AI features stay paused until then.</p>
            )}
            <Facts
              items={[
                ["Ollama", model.data?.ollama_version],
                ...Object.entries(model.data?.models ?? {}).map(
                  ([name, present]): [string, ReactNode] => [
                    name,
                    present ? "Installed" : "Not installed",
                  ],
                ),
                [
                  "Response time",
                  model.data?.latency_ms != null ? `${model.data.latency_ms} ms` : null,
                ],
              ]}
            />
          </div>
        </ServiceRow>
        <ServiceRow
          name="Background processing"
          purpose="Runs imports, analysis and document generation without blocking you."
          status={worker?.status}
          loading={overall.isPending}
        >
          <p className="text-[13px]">
            {worker?.status === "ok"
              ? "Processing jobs normally."
              : "Starts working once the database is connected and its tables are created."}
          </p>
        </ServiceRow>
      </ul>
    </>
  );
}
