import { AlertTriangle, FileUp, Info } from "lucide-react";
import { useId, useRef, useState, type DragEvent } from "react";

import { PageHeader } from "@/components/layout/PageHeader";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useHealth } from "@/features/system/queries";
import {
  ACCEPTED_EXTENSIONS,
  ACCEPTED_FILES,
  MAX_UPLOAD_BYTES,
  formatBytes,
} from "@/features/sources/format";
import { useFilePreview } from "@/features/sources/queries";
import { SourceList } from "@/features/sources/SourceList";
import { ApiError } from "@/lib/api/client";
import type { FilePreviewOut } from "@/lib/api/types";
import { cn } from "@/lib/utils";

const formatNames = { csv: "CSV", json: "JSON", txt: "Text" } as const;

function describeDelimiter(value: string | null): string | null {
  if (value === null) return null;
  if (value === "\t") return "Tab";
  return { ",": "Comma", ";": "Semicolon", "|": "Pipe" }[value] ?? `"${value}"`;
}

function Summary({ result }: { result: FilePreviewOut }) {
  const items: [string, string | null][] = [
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
    ["Rows", result.total_rows.toLocaleString()],
    ["Columns", String(result.columns.length)],
    ["Size", formatBytes(result.size_bytes)],
  ];
  return (
    <dl className="grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-4 lg:grid-cols-7">
      {items
        .filter((item): item is [string, string] => item[1] !== null)
        .map(([label, value]) => (
          <div key={label}>
            <dt className="text-[12px] text-muted-foreground">{label}</dt>
            <dd className="font-medium">{value}</dd>
          </div>
        ))}
    </dl>
  );
}

/**
 * Imports (UI-02 and the preview half of UI-03). The preview is real: the file goes to the
 * backend's file adapter, which detects format and encoding and returns the first 20 rows.
 * Importing into a workspace needs the database and workspaces, so it is not offered yet.
 */
export function ImportsPage() {
  const inputId = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const preview = useFilePreview();
  const health = useHealth();
  const [localError, setLocalError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const dbReady = health.data?.checks["database"]?.status === "ok";

  const handleFile = (file: File | undefined) => {
    if (!file) return;
    const ext = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
    if (!ACCEPTED_EXTENSIONS.includes(ext)) {
      setLocalError(`${file.name} isn't a CSV, JSON or text file.`);
      return;
    }
    if (file.size > MAX_UPLOAD_BYTES) {
      setLocalError(`${file.name} is ${formatBytes(file.size)}. Files can be up to 20 MB.`);
      return;
    }
    setLocalError(null);
    preview.mutate(file);
  };

  const onDrop = (event: DragEvent<HTMLLabelElement>) => {
    event.preventDefault();
    setDragging(false);
    handleFile(event.dataTransfer.files[0]);
  };

  const apiError = preview.error instanceof ApiError ? preview.error : null;
  const result = preview.data;

  return (
    <>
      <PageHeader
        title="Imports"
        description="Bring in customer feedback from files. Check a file first: we detect its format, encoding and columns and show the first rows."
      />

      {!dbReady && health.data && (
        <Alert className="mb-6">
          <Info aria-hidden />
          <AlertTitle>Importing starts once the database is connected</AlertTitle>
          <AlertDescription>
            Until then you can check files here. They're read in memory and not stored.
          </AlertDescription>
        </Alert>
      )}

      <div className="grid items-start gap-8 lg:grid-cols-[minmax(0,1fr)_18rem]">
        <div className="min-w-0 space-y-6">
          <label
            htmlFor={inputId}
            onDragOver={(e) => {
              e.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => {
              setDragging(false);
            }}
            onDrop={onDrop}
            className={cn(
              "flex cursor-pointer flex-col items-center justify-center gap-3 rounded-xl border border-dashed bg-card px-6 py-12 text-center transition-colors",
              dragging ? "border-primary bg-accent" : "hover:border-primary/60",
              preview.isPending && "pointer-events-none opacity-70",
            )}
          >
            <span className="flex size-11 items-center justify-center rounded-full bg-accent text-accent-foreground">
              <FileUp className="size-5" aria-hidden />
            </span>
            <span className="text-[15px] font-medium">
              {preview.isPending ? "Reading your file…" : "Drop a file here or choose one"}
            </span>
            <span className="text-[13px] text-muted-foreground">
              CSV with a header row, a JSON array of records, or a text transcript. Up to 20 MB.
            </span>
            <span className="sr-only">Choose a file</span>
          </label>
          <input
            ref={inputRef}
            id={inputId}
            type="file"
            accept={ACCEPTED_FILES}
            className="sr-only"
            disabled={preview.isPending}
            onChange={(event) => {
              handleFile(event.target.files?.[0]);
              event.target.value = "";
            }}
          />

          {(localError ?? apiError) && (
            <Alert variant="destructive">
              <AlertTriangle aria-hidden />
              <AlertTitle>This file can't be used</AlertTitle>
              <AlertDescription>
                <p>{localError ?? apiError?.message}</p>
                {apiError?.requestId && (
                  <p className="text-[12px]">Reference: {apiError.requestId}</p>
                )}
              </AlertDescription>
            </Alert>
          )}

          {result && (
            <section aria-labelledby="preview-heading" className="rounded-xl border bg-card">
              <div className="flex flex-wrap items-start justify-between gap-4 border-b px-6 py-4">
                <div className="min-w-0">
                  <h2 id="preview-heading" className="truncate text-[15px] font-semibold">
                    {result.original_filename}
                  </h2>
                  <p className="text-[13px] text-muted-foreground">
                    Showing {result.preview_rows.length} of {result.total_rows.toLocaleString()}{" "}
                    rows
                  </p>
                </div>
                <Button variant="outline" size="sm" onClick={() => inputRef.current?.click()}>
                  Check another file
                </Button>
              </div>
              <div className="space-y-5 px-6 py-5">
                <Summary result={result} />
                {result.warnings.length > 0 && (
                  <Alert>
                    <AlertTriangle className="text-warning" aria-hidden />
                    <AlertTitle>
                      {result.warnings.length === 1
                        ? "1 thing to check"
                        : `${result.warnings.length} things to check`}
                    </AlertTitle>
                    <AlertDescription>
                      <ul className="list-disc pl-4">
                        {result.warnings.map((w) => (
                          <li key={w}>{w}</li>
                        ))}
                      </ul>
                    </AlertDescription>
                  </Alert>
                )}
              </div>
              <div className="max-h-[28rem] overflow-auto border-t">
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
                            {cell === "" ? (
                              <span className="text-muted-foreground/60">empty</span>
                            ) : (
                              cell
                            )}
                          </TableCell>
                        ))}
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </section>
          )}
        </div>
        <SourceList />
      </div>
    </>
  );
}
