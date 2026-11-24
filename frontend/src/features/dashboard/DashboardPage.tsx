import { ArrowRight, CheckCircle2, CircleDashed } from "lucide-react";
import { Link } from "react-router";

import { PageHeader } from "@/components/layout/PageHeader";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useHealth } from "@/features/system/queries";
import { checkLabel, checkNames, overallLabel } from "@/features/system/status";

/** Foundation progress shown honestly: what is built now and what the next tasks deliver. */
const milestones = [
  { label: "Environment, backend and frontend foundation", done: true },
  { label: "File source adapter: CSV, JSON, TXT detection and preview", done: true },
  { label: "Database schema (54 tables, D07/D08) and migrations", done: false },
  { label: "Authentication and workspaces (Module 1)", done: false },
  { label: "Import pipeline with reconciliation report (Module 2)", done: false },
];

export function DashboardPage() {
  const health = useHealth();
  return (
    <>
      <PageHeader
        title="Dashboard"
        description="Pain points, trends and top opportunities appear here after the first import is analysed."
      />
      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>System readiness</CardTitle>
            <CardDescription>From GET /api/v1/health</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {health.isPending && <Skeleton className="h-20" />}
            {health.isError && (
              <p className="text-sm text-destructive">
                The API is not reachable. Start the backend.
              </p>
            )}
            {health.data && (
              <>
                <Badge variant={overallLabel[health.data.status].tone}>
                  {overallLabel[health.data.status].label}
                </Badge>
                <ul className="space-y-2">
                  {Object.entries(health.data.checks).map(([name, check]) => (
                    <li key={name} className="flex items-center justify-between text-sm">
                      <span>{checkNames[name] ?? name}</span>
                      <Badge variant={checkLabel[check.status].tone}>
                        {checkLabel[check.status].label}
                      </Badge>
                    </li>
                  ))}
                </ul>
              </>
            )}
            <Button asChild variant="link" className="px-0">
              <Link to="/system">
                Details <ArrowRight aria-hidden />
              </Link>
            </Button>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Build progress</CardTitle>
            <CardDescription>Milestone 1 (weeks 1–2)</CardDescription>
          </CardHeader>
          <CardContent>
            <ul className="space-y-2">
              {milestones.map((m) => (
                <li key={m.label} className="flex items-start gap-2 text-sm">
                  {m.done ? (
                    <CheckCircle2
                      className="mt-0.5 size-4 shrink-0 text-success"
                      aria-label="done"
                    />
                  ) : (
                    <CircleDashed
                      className="mt-0.5 size-4 shrink-0 text-muted-foreground"
                      aria-label="next"
                    />
                  )}
                  <span className={m.done ? "" : "text-muted-foreground"}>{m.label}</span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      </div>
    </>
  );
}
