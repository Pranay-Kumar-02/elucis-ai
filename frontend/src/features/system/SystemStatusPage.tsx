import { Database, Cpu, RefreshCw, Workflow } from "lucide-react";
import type { ReactNode } from "react";

import { PageHeader } from "@/components/layout/PageHeader";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useDatabaseHealth, useHealth, useModelRuntimeHealth } from "@/features/system/queries";
import { checkLabel } from "@/features/system/status";

function Row({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex justify-between gap-4 py-1.5 text-sm">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="text-right font-medium">{value ?? "—"}</dd>
    </div>
  );
}

export function SystemStatusPage() {
  const overall = useHealth();
  const db = useDatabaseHealth();
  const model = useModelRuntimeHealth();
  const refresh = () => {
    void overall.refetch();
    void db.refetch();
    void model.refetch();
  };

  return (
    <>
      <PageHeader
        title="System status"
        description="Live checks of the services this application depends on."
        actions={
          <Button variant="outline" size="sm" onClick={refresh}>
            <RefreshCw aria-hidden /> Refresh
          </Button>
        }
      />
      {overall.isError && (
        <Alert variant="destructive" className="mb-6">
          <AlertTitle>The API is not reachable</AlertTitle>
          <AlertDescription>Start the backend, then refresh this page.</AlertDescription>
        </Alert>
      )}
      <div className="grid gap-4 lg:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Database className="size-4" aria-hidden /> Database
            </CardTitle>
            <CardDescription>PostgreSQL with pgvector</CardDescription>
          </CardHeader>
          <CardContent>
            {db.isPending ? (
              <Skeleton className="h-24" />
            ) : db.data ? (
              <dl>
                <Row
                  label="Status"
                  value={
                    <Badge variant={checkLabel[db.data.status].tone}>
                      {checkLabel[db.data.status].label}
                    </Badge>
                  }
                />
                <Row label="PostgreSQL" value={db.data.server_version} />
                <Row label="pgvector" value={db.data.pgvector_version} />
                <Row label="Database" value={db.data.database} />
                <Row
                  label="Latency"
                  value={db.data.latency_ms !== null ? `${db.data.latency_ms} ms` : null}
                />
                {db.data.detail && <Row label="Detail" value={db.data.detail} />}
              </dl>
            ) : (
              <p className="text-sm text-muted-foreground">No data.</p>
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Cpu className="size-4" aria-hidden /> Model runtime
            </CardTitle>
            <CardDescription>Ollama on this machine</CardDescription>
          </CardHeader>
          <CardContent>
            {model.isPending ? (
              <Skeleton className="h-24" />
            ) : model.data ? (
              <dl>
                <Row
                  label="Status"
                  value={
                    <Badge variant={checkLabel[model.data.status].tone}>
                      {checkLabel[model.data.status].label}
                    </Badge>
                  }
                />
                <Row label="Ollama" value={model.data.ollama_version} />
                {Object.entries(model.data.models ?? {}).map(([name, present]) => (
                  <Row key={name} label={name} value={present ? "installed" : "not pulled"} />
                ))}
                {model.data.detail && <Row label="Detail" value={model.data.detail} />}
              </dl>
            ) : (
              <p className="text-sm text-muted-foreground">No data.</p>
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Workflow className="size-4" aria-hidden /> Background worker
            </CardTitle>
            <CardDescription>PostgreSQL job queue</CardDescription>
          </CardHeader>
          <CardContent>
            {overall.data?.checks["worker"] ? (
              <dl>
                <Row
                  label="Status"
                  value={
                    <Badge variant={checkLabel[overall.data.checks["worker"].status].tone}>
                      {checkLabel[overall.data.checks["worker"].status].label}
                    </Badge>
                  }
                />
                <Row label="Detail" value={overall.data.checks["worker"].detail} />
              </dl>
            ) : (
              <Skeleton className="h-24" />
            )}
          </CardContent>
        </Card>
      </div>
    </>
  );
}
