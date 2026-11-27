import { CheckCircle2 } from "lucide-react";
import type { ReactNode } from "react";

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { fieldLabels, issueLabels } from "@/features/sources/fields";
import { formatOccurredAt } from "@/features/sources/format";
import { WarningList } from "@/features/sources/PreviewCard";
import type { MappingField, ValidationReportOut } from "@/lib/api/types";

function Breakdown({ title, counts }: { title: string; counts: Record<string, number> }) {
  const entries = Object.entries(counts).sort((a, b) => b[1] - a[1]);
  if (entries.length === 0) return null;
  return (
    <div>
      <h3 className="mb-2 text-[13px] font-medium">{title}</h3>
      <ul className="space-y-1 text-[13px]">
        {entries.map(([code, count]) => (
          <li key={code} className="flex justify-between gap-4">
            <span>{issueLabels[code] ?? code}</span>
            <span className="tabular text-muted-foreground">{count.toLocaleString()}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Step 4: the result of applying the mapping and validation rules to every row. */
export function ValidationReport({
  report,
  action,
}: {
  report: ValidationReportOut;
  /** The "Start import" control, owned by the page (it knows the file and the role). */
  action?: ReactNode;
}) {
  const { summary } = report;
  const isMetrics = report.source_type === "metrics";
  const unit = isMetrics ? "rows" : report.file.detected_format === "txt" ? "segments" : "records";
  return (
    <section aria-labelledby="validation-heading" className="rounded-xl border bg-card">
      <div className="flex flex-wrap items-start justify-between gap-4 border-b px-6 py-4">
        <div className="min-w-0 flex-1 basis-72">
          <h2 id="validation-heading" className="text-[15px] font-semibold">
            Records checked
          </h2>
          <p className="text-[13px] text-muted-foreground">
            Every {unit.slice(0, -1)} was read with your column matches and checked against the
            import rules.
          </p>
        </div>
        {action && <div className="flex flex-col items-end gap-1">{action}</div>}
      </div>

      <div className="space-y-6 px-6 py-5">
        <dl className="flex flex-wrap gap-x-10 gap-y-3">
          <div>
            <dt className="text-[12px] text-muted-foreground">Received</dt>
            <dd className="tabular text-[22px] font-semibold">
              {summary.received.toLocaleString()}
            </dd>
          </div>
          <div>
            <dt className="text-[12px] text-muted-foreground">Ready to import</dt>
            <dd className="tabular text-[22px] font-semibold text-success">
              {summary.valid.toLocaleString()}
            </dd>
          </div>
          <div>
            <dt className="text-[12px] text-muted-foreground">Rejected</dt>
            <dd
              className={`tabular text-[22px] font-semibold ${summary.rejected > 0 ? "text-destructive" : ""}`}
            >
              {summary.rejected.toLocaleString()}
            </dd>
          </div>
        </dl>

        {Object.keys(summary.rejected_by_code).length > 0 ||
        Object.keys(summary.flags_by_code).length > 0 ? (
          <div className="grid gap-6 sm:grid-cols-2">
            <Breakdown title="Rejected because" counts={summary.rejected_by_code} />
            <Breakdown title="Kept, with a note" counts={summary.flags_by_code} />
          </div>
        ) : (
          <p className="flex items-center gap-2 text-[13px]">
            <CheckCircle2 className="size-4 text-success" aria-hidden />
            No problems found.
          </p>
        )}

        <WarningList warnings={report.warnings} />

        {report.errors.length > 0 && (
          <div>
            <h3 className="mb-2 text-[13px] font-medium">
              Rejected rows{report.errors_truncated ? ` (first ${report.errors.length})` : ""}
            </h3>
            <div className="max-h-64 overflow-auto rounded-lg border">
              <Table>
                <TableHeader className="sticky top-0 bg-card">
                  <TableRow className="hover:bg-transparent">
                    <TableHead className="w-20">Row</TableHead>
                    <TableHead className="w-40">Field</TableHead>
                    <TableHead>Reason</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {report.errors.map((e) => (
                    <TableRow key={`${e.row_number}-${e.segment_index}-${e.code}`}>
                      <TableCell className="tabular">{e.row_number}</TableCell>
                      <TableCell>
                        {e.field && e.field in fieldLabels
                          ? fieldLabels[e.field as MappingField]
                          : (e.field ?? "Whole row")}
                      </TableCell>
                      <TableCell>{e.message}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </div>
        )}

        {!isMetrics && report.sample_records.length > 0 && (
          <div>
            <h3 className="mb-2 text-[13px] font-medium">How the first records will be stored</h3>
            <div className="overflow-auto rounded-lg border">
              <Table>
                <TableHeader>
                  <TableRow className="hover:bg-transparent">
                    <TableHead className="w-16">Row</TableHead>
                    <TableHead>Feedback</TableHead>
                    <TableHead className="w-44">Date</TableHead>
                    <TableHead className="w-32">Customer</TableHead>
                    <TableHead className="w-20">Rating</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {report.sample_records.map((r) => (
                    <TableRow key={`${r.row_number}-${r.segment_index}`}>
                      <TableCell className="tabular text-muted-foreground">
                        {r.row_number}
                        {r.segment_index > 0 || r.speaker ? `.${r.segment_index + 1}` : ""}
                      </TableCell>
                      <TableCell className="max-w-md">
                        {r.speaker && <span className="font-medium">{r.speaker}: </span>}
                        <span className="line-clamp-2">{r.raw_text}</span>
                      </TableCell>
                      <TableCell title={r.occurred_at_raw ?? undefined}>
                        {r.occurred_at ? (
                          formatOccurredAt(r.occurred_at, r.occurred_at_raw)
                        ) : (
                          <span className="text-muted-foreground">
                            {r.occurred_at_raw ? "Unreadable" : "—"}
                          </span>
                        )}
                      </TableCell>
                      <TableCell>
                        {r.customer_ref ?? <span className="text-muted-foreground">Unknown</span>}
                      </TableCell>
                      <TableCell className="tabular">
                        {r.rating_value !== null ? (
                          `${r.rating_value}${r.rating_out_of ? `/${r.rating_out_of}` : ""}`
                        ) : r.rating_raw ? (
                          <span className="text-muted-foreground">Invalid</span>
                        ) : (
                          "—"
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </div>
        )}

        {isMetrics && report.sample_metrics.length > 0 && (
          <div>
            <h3 className="mb-2 text-[13px] font-medium">How the first rows will be stored</h3>
            <div className="overflow-auto rounded-lg border">
              <Table>
                <TableHeader>
                  <TableRow className="hover:bg-transparent">
                    <TableHead className="w-16">Row</TableHead>
                    <TableHead>Metric</TableHead>
                    <TableHead>Date</TableHead>
                    <TableHead>Dimension</TableHead>
                    <TableHead className="text-right">Value</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {report.sample_metrics.map((m) => (
                    <TableRow key={m.row_number}>
                      <TableCell className="tabular text-muted-foreground">
                        {m.row_number}
                      </TableCell>
                      <TableCell>{m.metric_name}</TableCell>
                      <TableCell className="tabular">{m.observed_on}</TableCell>
                      <TableCell>
                        {m.dimension || <span className="text-muted-foreground">—</span>}
                      </TableCell>
                      <TableCell className="tabular text-right">
                        {m.value.toLocaleString()}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
