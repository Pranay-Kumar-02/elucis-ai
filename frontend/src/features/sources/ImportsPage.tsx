import { AlertTriangle, Info } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router";

import { PageHeader } from "@/components/layout/PageHeader";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { ImportHistory } from "@/features/imports/ImportHistory";
import { useCheckFile, useStartImport, useUploadFile } from "@/features/imports/queries";
import { MappingForm } from "@/features/sources/MappingForm";
import { PreviewCard } from "@/features/sources/PreviewCard";
import { SourceInputPanel } from "@/features/sources/SourceInputPanel";
import { SourceList } from "@/features/sources/SourceList";
import { ValidationReport } from "@/features/sources/ValidationReport";
import { useActiveWorkspace } from "@/features/workspaces/active";
import { NoWorkspace } from "@/features/workspaces/NoWorkspace";
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
 * Imports (UI-02 and UI-03): upload or paste (the file is stored, API-14), match columns,
 * check every row, then start the import (API-15) and follow it on its report page (UI-04).
 * Viewers see the import history only.
 */
export function ImportsPage() {
  const { active } = useActiveWorkspace();
  if (!active) {
    return (
      <>
        <PageHeader title="Imports" />
        <NoWorkspace />
      </>
    );
  }
  const canImport = active.role === "editor" || active.role === "owner";
  return (
    <>
      <PageHeader
        title="Imports"
        description="Bring in customer feedback from files or pasted text. Check the data first: we read every row with your column matches and show what will be imported."
      />
      <div className="grid items-start gap-8 lg:grid-cols-[minmax(0,1fr)_18rem]">
        <div className="min-w-0 space-y-6">
          {canImport ? (
            <ImportFlow key={active.workspace_id} workspaceId={active.workspace_id} />
          ) : (
            <Alert>
              <Info aria-hidden />
              <AlertTitle>Viewing only</AlertTitle>
              <AlertDescription>
                Editors and Owners can import feedback. You can open past imports below.
              </AlertDescription>
            </Alert>
          )}
          <ImportHistory workspaceId={active.workspace_id} />
        </div>
        <SourceList />
      </div>
    </>
  );
}

function ImportFlow({ workspaceId }: { workspaceId: string }) {
  const navigate = useNavigate();
  const upload = useUploadFile(workspaceId);
  const validation = useCheckFile(workspaceId);
  const start = useStartImport(workspaceId);
  const [sourceType, setSourceType] = useState<SourceType>("review");
  const [input, setInput] = useState<SourceInput | null>(null);
  const [mapping, setMapping] = useState<ColumnMapping>({});
  const [localError, setLocalError] = useState<string | null>(null);
  // Files stored from this page, so changing the source type (which uploads again for fresh
  // suggestions) does not warn that the file is a copy of itself.
  const [ownUploads, setOwnUploads] = useState<string[]>([]);
  const [importKey, setImportKey] = useState(() => crypto.randomUUID());

  const runUpload = (next: SourceInput, type: SourceType) => {
    setInput(next);
    validation.reset();
    start.reset();
    upload.mutate(
      { input: next, sourceType: type },
      {
        onSuccess: (result) => {
          setMapping(result.suggested_mapping);
          setOwnUploads((ids) => [...ids, result.id]);
          setImportKey(crypto.randomUUID());
        },
      },
    );
  };

  const changeType = (type: SourceType) => {
    setSourceType(type);
    if (input) runUpload(input, type);
  };

  const changeMapping = (next: ColumnMapping) => {
    setMapping(next);
    validation.reset();
    start.reset();
    setImportKey(crypto.randomUUID()); // a different mapping is a different import
  };

  const result = upload.isSuccess ? upload.data : null;
  const check = () => {
    if (!result) return;
    validation.mutate({ fileId: result.id, sourceType, mapping });
  };
  const begin = () => {
    if (!result) return;
    start.mutate(
      { fileId: result.id, sourceType, mapping, key: importKey },
      { onSuccess: (ref) => void navigate(`/imports/${ref.resource_id}`) },
    );
  };

  const duplicate =
    result?.duplicate_of_file && !ownUploads.includes(result.duplicate_of_file.id)
      ? result.duplicate_of_file
      : null;
  const isMetrics = sourceType === "metrics";
  const ready = validation.data && validation.data.summary.valid > 0;

  return (
    <>
      <SourceInputPanel
        sourceType={sourceType}
        onSourceTypeChange={changeType}
        onInput={(next) => {
          runUpload(next, sourceType);
        }}
        onLocalError={setLocalError}
        busy={upload.isPending}
      />
      <ErrorAlert error={upload.error} local={localError} />
      {result && !localError && (
        <>
          {duplicate && (
            <Alert>
              <Info aria-hidden />
              <AlertTitle>This file was imported before</AlertTitle>
              <AlertDescription>
                It has the same content as {duplicate.original_filename}. You can continue; repeated
                feedback from the same customer is marked as a duplicate.
              </AlertDescription>
            </Alert>
          )}
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
            <ValidationReport
              report={validation.data}
              action={
                <>
                  <Button onClick={begin} disabled={!ready || isMetrics || start.isPending}>
                    {start.isPending ? "Starting…" : "Start import"}
                  </Button>
                  {isMetrics && (
                    <span className="text-[12px] text-muted-foreground">
                      Importing metrics isn't available yet
                    </span>
                  )}
                  {!isMetrics && !ready && (
                    <span className="text-[12px] text-muted-foreground">
                      No valid records to import
                    </span>
                  )}
                </>
              }
            />
          )}
          <ErrorAlert error={start.error} local={null} />
        </>
      )}
    </>
  );
}
