import { Link } from "react-router";

import { ErrorAlert } from "@/components/layout/ErrorAlert";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { formatWhen, statusLabels, statusVariant } from "@/features/imports/labels";
import { useImports } from "@/features/imports/queries";
import { sourceTypes } from "@/features/sources/fields";

const typeLabel = (value: string) => sourceTypes.find((t) => t.value === value)?.label ?? value;

/** Import history (UI-02): every import of the workspace, newest first. */
export function ImportHistory({ workspaceId }: { workspaceId: string }) {
  const imports = useImports(workspaceId);
  return (
    <section aria-labelledby="history-heading" className="rounded-xl border bg-card">
      <div className="border-b px-6 py-4">
        <h2 id="history-heading" className="text-[15px] font-semibold">
          Import history
        </h2>
      </div>
      <div className="px-6 py-4">
        {imports.isPending && (
          <div className="space-y-2" aria-label="Loading imports">
            <Skeleton className="h-8 w-full" />
            <Skeleton className="h-8 w-full" />
          </div>
        )}
        {imports.isError && <ErrorAlert error={imports.error} title="Imports could not load" />}
        {imports.isSuccess && imports.data.items.length === 0 && (
          <p className="py-4 text-sm text-muted-foreground">No imports yet</p>
        )}
        {imports.isSuccess && imports.data.items.length > 0 && (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>File</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Imported</TableHead>
                <TableHead className="text-right">Rejected</TableHead>
                <TableHead>Started</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {imports.data.items.map((item) => (
                <TableRow key={item.id}>
                  <TableCell className="max-w-56 truncate">
                    <Link
                      to={`/imports/${item.id}`}
                      className="font-medium text-primary hover:underline"
                    >
                      {item.original_filename ?? "Import"}
                    </Link>
                  </TableCell>
                  <TableCell>{typeLabel(item.source_type)}</TableCell>
                  <TableCell>
                    <Badge variant={statusVariant[item.status]}>{statusLabels[item.status]}</Badge>
                  </TableCell>
                  <TableCell className="tabular text-right">
                    {item.report ? item.report.imported.toLocaleString() : "–"}
                  </TableCell>
                  <TableCell className="tabular text-right">
                    {item.report ? item.report.rejected.toLocaleString() : "–"}
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {formatWhen(item.created_at)}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </div>
    </section>
  );
}
