import { AlertTriangle, Info } from "lucide-react";
import { useState } from "react";

import { PageHeader } from "@/components/layout/PageHeader";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { MappingForm } from "@/features/sources/MappingForm";
import { PreviewCard } from "@/features/sources/PreviewCard";
import { useSourcePreview, useSourceValidation } from "@/features/sources/queries";
import { SourceInputPanel } from "@/features/sources/SourceInputPanel";
import { SourceList } from "@/features/sources/SourceList";
import { ValidationReport } from "@/features/sources/ValidationReport";
import { useHealth } from "@/features/system/queries";
import { ApiError } from "@/lib/api/client";
import type { SourceInput } from "@/lib/api/endpoints";
import type { ColumnMapping, SourceType } from "@/lib/api/types";

function ErrorAlert({ error, local }: { error: unknown; local: string | null }) {
  const apiError = error instanceof ApiError ? error : null;
  if (!local && !apiError) return null;
  const details = apiError?.details.filter((d) => d.field.startsWith("column_mapping.")) ?? [];
  return (
    <Alert variant="destructive">
      <AlertTriangle aria-hidden />
      <AlertTitle>{local ? "This file can't be used" : "That didn't work"}</AlertTitle>
      <AlertDescription>
        <p>{local ?? apiError?.message}</p>
        {details.length > 0 && (
          <ul className="list-disc pl-4">
            {details.map((d) => (
              <li key={d.field + d.issue}>
                {d.field.replace("column_mapping.", "")}: {d.issue.replaceAll("_", " ")}
              </li>
            ))}
          </ul>
        )}
        {apiError?.requestId && <p className="text-[12px]">Reference: {apiError.requestId}</p>}
      </AlertDescription>
    </Alert>
  );
}

/**
 * Imports (UI-02 and UI-03 up to "Start import"). Each step calls the real source-fetching
 * layer: preview (format, encoding, columns), then validation of every row with the chosen
 * column matches. Starting an import needs the database and stays disabled until then.
 */
export function ImportsPage() {
  const health = useHealth();
  const preview = useSourcePreview();
  const validation = useSourceValidation();
  const [sourceType, setSourceType] = useState<SourceType>("review");
  const [input, setInput] = useState<SourceInput | null>(null);
  const [mapping, setMapping] = useState<ColumnMapping>({});
  const [localError, setLocalError] = useState<string | null>(null);
  const dbReady = health.data?.checks["database"]?.status === "ok";

  const runPreview = (next: SourceInput, type: SourceType) => {
    setInput(next);
    validation.reset();
    preview.mutate(
      { input: next, sourceType: type },
      {
        onSuccess: (result) => {
          setMapping(result.suggested_mapping);
        },
      },
    );
  };

  const changeType = (type: SourceType) => {
    setSourceType(type);
    if (input) runPreview(input, type);
  };

  const changeMapping = (next: ColumnMapping) => {
    setMapping(next);
    validation.reset();
  };

  const check = () => {
    if (!input) return;
    validation.mutate({ input, sourceType, mapping });
  };

  const result = preview.isSuccess ? preview.data : null;

  return (
    <>
      <PageHeader
        title="Imports"
        description="Bring in customer feedback from files or pasted text. Check the data first: we read every row with your column matches and show what would be imported."
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
          <SourceInputPanel
            sourceType={sourceType}
            onSourceTypeChange={changeType}
            onInput={(next) => {
              runPreview(next, sourceType);
            }}
            onLocalError={setLocalError}
            busy={preview.isPending}
          />
          <ErrorAlert error={preview.error} local={localError} />
          {result && !localError && (
            <>
              <PreviewCard result={result} />
              <MappingForm
                preview={result}
                mapping={mapping}
                onChange={changeMapping}
                onCheck={check}
                checking={validation.isPending}
              />
              <ErrorAlert error={validation.error} local={null} />
              {validation.data && (
                <ValidationReport report={validation.data} databaseReady={dbReady} />
              )}
            </>
          )}
        </div>
        <SourceList />
      </div>
    </>
  );
}
