import { CheckCircle2, XCircle } from "lucide-react";
import { useId, useState } from "react";
import { Link, useParams } from "react-router";

import { ErrorAlert } from "@/components/layout/ErrorAlert";
import { PageHeader } from "@/components/layout/PageHeader";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { NativeSelect } from "@/components/ui/native-select";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  filteredLabels,
  formatDay,
  formatWhen,
  piiLabels,
  stageLabels,
  statusLabels,
  statusVariant,
} from "@/features/imports/labels";
import { isFinal, useImport, useImportErrors } from "@/features/imports/queries";
import { issueLabels } from "@/features/sources/fields";
import { useActiveWorkspace } from "@/features/workspaces/active";
import { NoWorkspace } from "@/features/workspaces/NoWorkspace";
import type { ImportOut, ImportReport } from "@/lib/api/types";

function Progress({ item }: { item: ImportOut }) {
  const total = item.progress?.total ?? 0;
  const done = item.progress?.processed ?? 0;
  const percent = total > 0 ? Math.round((done / total) * 100) : 0;
  return (
    <section aria-label="Progress" className="rounded-xl border bg-card px-6 py-5">
      <p className="text-sm font-medium">
        {item.status === "queued"
          ? "Waiting for the worker to start…"
          : "Reading and storing rows…"}
      </p>
      <div
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={percent}
        className="mt-3 h-2 overflow-hidden rounded-full bg-muted"
      >
        <div className="h-full bg-primary transition-all" style={{ width: `${percent}%` }} />
      </div>
      <p className="tabular mt-2 text-[13px] text-muted-foreground">
        {total > 0 ? `${done.toLocaleString()} of ${total.toLocaleString()} rows` : "Starting"}
      </p>
    </section>
  );
}

function Figure({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <dt className="text-[12px] text-muted-foreground">{label}</dt>
      <dd className="tabular text-[22px] font-semibold">{value.toLocaleString()}</dd>
    </div>
  );
}

/** DR-40 identity, in the report's own terms (D06 §10.1). */
function Reconciliation({ report }: { report: ImportReport }) {
  const filtered = Object.entries(report.filtered).filter(([, n]) => n > 0);
  const filteredTotal = Object.values(report.filtered).reduce((a, b) => a + b, 0);
  const pii = Object.entries(report.pii_masked).filter(([, n]) => n > 0);
  return (
    <section aria-labelledby="report-heading" className="rounded-xl border bg-card">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b px-6 py-4">
        <h2 id="report-heading" className="text-[15px] font-semibold">
          Import report
        </h2>
        {report.reconciled ? (
          <span className="flex items-center gap-1.5 text-[13px] text-success">
            <CheckCircle2 className="size-4" aria-hidden /> Every row is accounted for
          </span>
        ) : (
          <span className="flex items-center gap-1.5 text-[13px] text-destructive">
            <XCircle className="size-4" aria-hidden /> Counts do not add up
          </span>
        )}
      </div>
      <div className="space-y-6 px-6 py-5">
        <dl className="flex flex-wrap gap-x-10 gap-y-3">
          <Figure label="Received" value={report.received} />
          <Figure label="Imported" value={report.imported} />
          <Figure label="Rejected" value={report.rejected} />
          <Figure label="Duplicates" value={report.duplicates} />
          <Figure label="Filtered" value={filteredTotal} />
          <Figure label="Failed" value={report.failed} />
        </dl>
        <p className="tabular text-[13px] text-muted-foreground">
          {report.received.toLocaleString()} received = {report.imported.toLocaleString()} imported
          + {report.rejected.toLocaleString()} rejected + {report.duplicates.toLocaleString()}{" "}
          duplicates + {filteredTotal.toLocaleString()} filtered + {report.failed.toLocaleString()}{" "}
          failed
        </p>
        <div className="grid gap-6 sm:grid-cols-2">
          <div>
            <h3 className="text-[13px] font-semibold">Filtered out</h3>
            {filtered.length === 0 ? (
              <p className="text-[13px] text-muted-foreground">Nothing was filtered out.</p>
            ) : (
              <ul className="mt-1 space-y-0.5 text-[13px]">
                {filtered.map(([reason, n]) => (
                  <li key={reason}>
                    {filteredLabels[reason] ?? reason}: {n.toLocaleString()}
                  </li>
                ))}
              </ul>
            )}
          </div>
          <div>
            <h3 className="text-[13px] font-semibold">Personal data masked</h3>
            {pii.length === 0 ? (
              <p className="text-[13px] text-muted-foreground">No personal data was found.</p>
            ) : (
              <ul className="mt-1 space-y-0.5 text-[13px]">
                {pii.map(([type, n]) => (
                  <li key={type}>
                    {piiLabels[type] ?? type}: {n.toLocaleString()}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
        {(report.date_range.from ?? report.date_range.to) && (
          <p className="text-[13px] text-muted-foreground">
            Feedback dated {report.date_range.from ? formatDay(report.date_range.from) : "?"} to{" "}
            {report.date_range.to ? formatDay(report.date_range.to) : "?"}
          </p>
        )}
        {Object.keys(report.flags).length > 0 && (
          <div>
            <h3 className="text-[13px] font-semibold">Kept with a note</h3>
            <ul className="mt-1 space-y-0.5 text-[13px]">
              {Object.entries(report.flags).map(([code, n]) => (
                <li key={code}>
                  {issueLabels[code] ?? code}: {n.toLocaleString()}
                </li>
              ))}
            </ul>
          </div>
        )}
        {report.not_checked.length > 0 && (
          <p className="text-[12px] text-muted-foreground">
            Not checked in this version: {report.not_checked.join(" and ")}.
          </p>
        )}
      </div>
    </section>
  );
}

function RowErrors({ ws, id }: { ws: string; id: string }) {
  const [kind, setKind] = useState("");
  const [stage, setStage] = useState("");
  const errors = useImportErrors(ws, id, { kind, stage }, true);
  const kindId = useId();
  const stageId = useId();
  return (
    <section aria-labelledby="errors-heading" className="rounded-xl border bg-card">
      <div className="flex flex-wrap items-end justify-between gap-4 border-b px-6 py-4">
        <h2 id="errors-heading" className="text-[15px] font-semibold">
          Rejected and failed rows
        </h2>
        <div className="flex gap-3">
          <div className="space-y-1">
            <label htmlFor={kindId} className="text-[12px] text-muted-foreground">
              Kind
            </label>
            <NativeSelect
              id={kindId}
              value={kind}
              onChange={(e) => {
                setKind(e.target.value);
              }}
            >
              <option value="">All</option>
              <option value="rejected">Rejected</option>
              <option value="failed">Failed</option>
            </NativeSelect>
          </div>
          <div className="space-y-1">
            <label htmlFor={stageId} className="text-[12px] text-muted-foreground">
              Stage
            </label>
            <NativeSelect
              id={stageId}
              value={stage}
              onChange={(e) => {
                setStage(e.target.value);
              }}
            >
              <option value="">All</option>
              {Object.entries(stageLabels).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </NativeSelect>
          </div>
        </div>
      </div>
      <div className="px-6 py-4">
        {errors.isPending && <Skeleton className="h-8 w-full" />}
        {errors.isError && <ErrorAlert error={errors.error} title="Rows could not load" />}
        {errors.isSuccess && errors.data.items.length === 0 && (
          <p className="py-2 text-sm text-muted-foreground">No rejected or failed rows</p>
        )}
        {errors.isSuccess && errors.data.items.length > 0 && (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Row</TableHead>
                <TableHead>Kind</TableHead>
                <TableHead>Stage</TableHead>
                <TableHead>Reason</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {errors.data.items.map((e) => (
                <TableRow key={e.id}>
                  <TableCell className="tabular">{e.row_number}</TableCell>
                  <TableCell>{e.kind === "rejected" ? "Rejected" : "Failed"}</TableCell>
                  <TableCell>{stageLabels[e.stage] ?? e.stage}</TableCell>
                  <TableCell>{issueLabels[e.code] ?? e.message}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
        {errors.isSuccess && errors.data.next_cursor && (
          <p className="pt-3 text-[12px] text-muted-foreground">Showing the first 200 rows.</p>
        )}
      </div>
    </section>
  );
}

/** Import report and progress (UI-04): status while running, then the reconciliation. */
export function ImportDetailPage() {
  const { importId } = useParams();
  const { active } = useActiveWorkspace();
  const ws = active?.workspace_id;
  const item = useImport(ws, importId);

  if (!active) return <NoWorkspace />;
  const back = (
    <Button variant="outline" asChild>
      <Link to="/imports">Back to imports</Link>
    </Button>
  );

  if (item.isPending) {
    return (
      <div className="space-y-4" aria-label="Loading import">
        <Skeleton className="h-10 w-72" />
        <Skeleton className="h-32 w-full" />
      </div>
    );
  }
  if (item.isError) {
    return (
      <>
        <PageHeader title="Import" actions={back} />
        <ErrorAlert error={item.error} title="This import could not load" />
      </>
    );
  }
  const data = item.data;
  return (
    <>
      <PageHeader
        title={data.original_filename ?? "Import"}
        description={`Started ${formatWhen(data.created_at)}`}
        actions={back}
      />
      <div className="space-y-6">
        <div className="flex items-center gap-2">
          <Badge variant={statusVariant[data.status]}>{statusLabels[data.status]}</Badge>
        </div>
        {!isFinal(data.status) && <Progress item={data} />}
        {data.status === "failed" && (
          <Alert variant="destructive">
            <XCircle aria-hidden />
            <AlertTitle>The import failed</AlertTitle>
            <AlertDescription>
              {data.error ?? "The import stopped before it finished."}
            </AlertDescription>
          </Alert>
        )}
        {data.report && "received" in data.report && <Reconciliation report={data.report} />}
        {isFinal(data.status) && ws && importId && <RowErrors ws={ws} id={importId} />}
      </div>
    </>
  );
}
