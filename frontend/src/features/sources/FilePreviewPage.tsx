import { AlertTriangle, FileUp } from "lucide-react";
import { useId, useState, type ChangeEvent } from "react";

import { PageHeader } from "@/components/layout/PageHeader";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ACCEPTED_FILES, MAX_UPLOAD_BYTES, formatBytes } from "@/features/sources/format";
import { useFilePreview } from "@/features/sources/queries";
import { SourceCatalogue } from "@/features/sources/SourceCatalogue";
import { ApiError } from "@/lib/api/client";

export function FilePreviewPage() {
  const inputId = useId();
  const preview = useFilePreview();
  const [localError, setLocalError] = useState<string | null>(null);

  const onChange = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    if (file.size > MAX_UPLOAD_BYTES) {
      setLocalError(`${file.name} is ${formatBytes(file.size)}; the limit is 20 MB.`);
      return;
    }
    setLocalError(null);
    preview.mutate(file);
  };

  const apiError = preview.error instanceof ApiError ? preview.error : null;
  const result = preview.data;

  return (
    <>
      <PageHeader
        title="File preview"
        description="Developer tool: detects format and encoding and shows the first 20 rows of a CSV, JSON or TXT file. Nothing is stored."
      />
      <div className="grid gap-6 xl:grid-cols-[1fr_22rem]">
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Choose a file</CardTitle>
              <CardDescription>
                CSV (UTF-8), JSON array of records, or a TXT transcript · up to 20 MB
              </CardDescription>
            </CardHeader>
            <CardContent>
              <label
                htmlFor={inputId}
                className="flex cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border border-dashed px-6 py-10 text-center transition-colors hover:bg-accent/50"
              >
                <FileUp className="size-6 text-muted-foreground" aria-hidden />
                <span className="text-sm font-medium">
                  {preview.isPending ? "Reading file…" : "Click to choose a file"}
                </span>
                <span className="text-xs text-muted-foreground">.csv · .json · .txt</span>
              </label>
              <input
                id={inputId}
                type="file"
                accept={ACCEPTED_FILES}
                className="sr-only"
                onChange={onChange}
                disabled={preview.isPending}
              />
            </CardContent>
          </Card>

          {(localError ?? apiError) && (
            <Alert variant="destructive">
              <AlertTriangle aria-hidden />
              <AlertTitle>File not accepted</AlertTitle>
              <AlertDescription>
                <p>{localError ?? apiError?.message}</p>
                {apiError?.requestId && (
                  <p className="font-mono text-xs">Request ID: {apiError.requestId}</p>
                )}
              </AlertDescription>
            </Alert>
          )}

          {result && (
            <Card>
              <CardHeader>
                <CardTitle>{result.original_filename}</CardTitle>
                <CardDescription className="flex flex-wrap gap-2 pt-1">
                  <Badge variant="secondary">{result.detected_format.toUpperCase()}</Badge>
                  <Badge variant="secondary">{result.detected_encoding}</Badge>
                  {result.csv_delimiter && (
                    <Badge variant="secondary">
                      delimiter{" "}
                      {result.csv_delimiter === "\t" ? "tab" : `"${result.csv_delimiter}"`}
                    </Badge>
                  )}
                  {result.transcript_mode && (
                    <Badge variant="secondary">{result.transcript_mode}</Badge>
                  )}
                  <Badge variant="outline">{formatBytes(result.size_bytes)}</Badge>
                  <Badge variant="outline">{result.total_rows} rows</Badge>
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {result.warnings.length > 0 && (
                  <Alert>
                    <AlertTriangle aria-hidden />
                    <AlertTitle>Warnings</AlertTitle>
                    <AlertDescription>
                      <ul className="list-disc pl-4">
                        {result.warnings.map((w) => (
                          <li key={w}>{w}</li>
                        ))}
                      </ul>
                    </AlertDescription>
                  </Alert>
                )}
                <Table>
                  <TableCaption>
                    First {result.preview_rows.length} of {result.total_rows} rows
                  </TableCaption>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-12 text-muted-foreground">#</TableHead>
                      {result.columns.map((c) => (
                        <TableHead key={c}>{c}</TableHead>
                      ))}
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {result.preview_rows.map((row, i) => (
                      <TableRow key={i}>
                        <TableCell className="text-muted-foreground">{i + 1}</TableCell>
                        {row.map((cell, j) => (
                          <TableCell key={j} className="max-w-80 break-words whitespace-pre-wrap">
                            {cell}
                          </TableCell>
                        ))}
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
                <p className="font-mono text-xs break-all text-muted-foreground">
                  SHA-256 {result.sha256}
                </p>
              </CardContent>
            </Card>
          )}
        </div>
        <SourceCatalogue />
      </div>
    </>
  );
}
