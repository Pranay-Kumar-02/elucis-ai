import { AlertTriangle } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { formatBytes } from "@/features/sources/format";
import type { FilePreviewOut } from "@/lib/api/types";

const formatNames = { csv: "CSV", json: "JSON", txt: "Text" } as const;

function describeDelimiter(value: string | null): string | null {
  if (value === null) return null;
  if (value === "\t") return "Tab";
  return { ",": "Comma", ";": "Semicolon", "|": "Pipe" }[value] ?? `"${value}"`;
}

export function WarningList({ warnings, title }: { warnings: string[]; title?: string }) {
  if (warnings.length === 0) return null;
  return (
    <Alert>
      <AlertTriangle className="text-warning" aria-hidden />
      <AlertTitle>
        {title ??
          (warnings.length === 1 ? "1 thing to check" : `${warnings.length} things to check`)}
      </AlertTitle>
      <AlertDescription>
        <ul className="list-disc pl-4">
          {warnings.map((w) => (
            <li key={w}>{w}</li>
          ))}
        </ul>
      </AlertDescription>
    </Alert>
  );
}

/** Step 2: what the reader found in the file and its first rows. */
export function PreviewCard({ result }: { result: FilePreviewOut }) {
  const facts: [string, string | null][] = [
    ["Format", formatNames[result.detected_format]],
    ["Encoding", result.detected_encoding.toUpperCase()],
    ["Delimiter", describeDelimiter(result.csv_delimiter)],
    [
      "Layout",
      result.transcript_mode === "speaker_turns"
        ? "Speaker turns"
        : result.transcript_mode === "paragraphs"
          ? "Paragraphs"
          : null,
    ],
    [result.detected_format === "txt" ? "Segments" : "Rows", result.total_rows.toLocaleString()],
    ["Columns", String(result.columns.length)],
    ["Size", formatBytes(result.size_bytes)],
  ];
  const title = result.input === "pasted_text" ? "Pasted text" : result.original_filename;
  return (
    <section aria-labelledby="preview-heading" className="rounded-xl border bg-card">
      <div className="border-b px-6 py-4">
        <h2 id="preview-heading" className="truncate text-[15px] font-semibold">
          {title}
        </h2>
        <p className="text-[13px] text-muted-foreground">
          Showing {result.preview_rows.length} of {result.total_rows.toLocaleString()}{" "}
          {result.detected_format === "txt" ? "segments" : "rows"}
        </p>
      </div>
      <div className="space-y-5 px-6 py-5">
        <dl className="grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-4 lg:grid-cols-7">
          {facts
            .filter((f): f is [string, string] => f[1] !== null)
            .map(([label, value]) => (
              <div key={label}>
                <dt className="text-[12px] text-muted-foreground">{label}</dt>
                <dd className="font-medium">{value}</dd>
              </div>
            ))}
        </dl>
        <WarningList warnings={result.warnings} />
      </div>
      <div className="max-h-[24rem] overflow-auto border-t">
        <Table>
          <TableHeader className="sticky top-0 z-10 bg-card">
            <TableRow className="hover:bg-transparent">
              <TableHead className="w-12 text-right text-muted-foreground">#</TableHead>
              {result.columns.map((c) => (
                <TableHead key={c}>{c}</TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {result.preview_rows.map((row, i) => (
              <TableRow key={i}>
                <TableCell className="text-right text-muted-foreground">{i + 1}</TableCell>
                {row.map((cell, j) => (
                  <TableCell key={j} className="max-w-80 break-words whitespace-pre-wrap">
                    {cell === "" ? <span className="text-muted-foreground/60">empty</span> : cell}
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </section>
  );
}
