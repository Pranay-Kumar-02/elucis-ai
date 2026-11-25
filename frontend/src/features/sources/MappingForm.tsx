import { Info } from "lucide-react";
import { useId } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { NativeSelect } from "@/components/ui/native-select";
import { fieldLabels, fieldsFor } from "@/features/sources/fields";
import type { ColumnMapping, FilePreviewOut, MappingField } from "@/lib/api/types";

interface Props {
  preview: FilePreviewOut;
  mapping: ColumnMapping;
  onChange: (mapping: ColumnMapping) => void;
  onCheck: () => void;
  checking: boolean;
}

function firstValue(preview: FilePreviewOut, column: string | undefined): string | null {
  if (!column) return null;
  const index = preview.columns.indexOf(column);
  const value = preview.preview_rows.map((row) => row[index] ?? "").find((v) => v.trim() !== "");
  return value ?? null;
}

/** Step 3 (UI-03): match file columns to standard fields. Suggestions are only proposals. */
export function MappingForm({ preview, mapping, onChange, onCheck, checking }: Props) {
  const baseId = useId();
  const fields = fieldsFor(preview.source_type);
  const required = new Set<MappingField>(preview.required_fields);
  const missing = preview.required_fields.filter((f) => !mapping[f]);
  const isFeedback = preview.source_type !== "metrics";
  const fixedLayout = preview.detected_format === "txt";

  const setField = (field: MappingField, column: string) => {
    const next: ColumnMapping = Object.fromEntries(
      Object.entries(mapping).filter(([key]) => key !== field),
    );
    if (column) next[field] = column;
    onChange(next);
  };

  return (
    <section aria-labelledby="mapping-heading" className="rounded-xl border bg-card">
      <div className="border-b px-6 py-4">
        <h2 id="mapping-heading" className="text-[15px] font-semibold">
          Match columns
        </h2>
        <p className="text-[13px] text-muted-foreground">
          {fixedLayout
            ? "Text is split automatically; nothing to match."
            : "We suggested matches from the column names. Check each one before continuing."}
        </p>
      </div>
      <div className="space-y-5 px-6 py-5">
        {!fixedLayout && (
          <div className="grid gap-x-6 gap-y-4 sm:grid-cols-2">
            {fields.map((field) => {
              const id = `${baseId}-${field}`;
              const sample = firstValue(preview, mapping[field]);
              return (
                <div key={field}>
                  <label htmlFor={id} className="mb-1 block text-[13px] font-medium">
                    {fieldLabels[field]}
                    {required.has(field) ? (
                      <span className="text-destructive" aria-hidden>
                        {" "}
                        *
                      </span>
                    ) : (
                      <span className="font-normal text-muted-foreground"> (optional)</span>
                    )}
                  </label>
                  <NativeSelect
                    id={id}
                    value={mapping[field] ?? ""}
                    aria-required={required.has(field)}
                    aria-invalid={required.has(field) && !mapping[field]}
                    onChange={(e) => {
                      setField(field, e.target.value);
                    }}
                  >
                    <option value="">Not in this file</option>
                    {preview.columns.map((c) => (
                      <option key={c} value={c}>
                        {c}
                      </option>
                    ))}
                  </NativeSelect>
                  <p
                    className="mt-1 truncate text-[12px] text-muted-foreground"
                    title={sample ?? undefined}
                  >
                    {sample ? `e.g. ${sample}` : " "}
                  </p>
                </div>
              );
            })}
          </div>
        )}
        {isFeedback && !mapping.customer_id && (
          <Alert>
            <Info aria-hidden />
            <AlertDescription>
              Without a customer ID column, customer identity will be unknown. Reach and claims
              about how many customers want something will be limited.
            </AlertDescription>
          </Alert>
        )}
        <div className="flex flex-wrap items-center gap-3">
          <Button onClick={onCheck} disabled={checking || missing.length > 0}>
            {checking ? "Checking records…" : "Check records"}
          </Button>
          {missing.length > 0 && (
            <span className="text-[13px] text-muted-foreground">
              Choose a column for {missing.map((f) => fieldLabels[f]).join(", ")} to continue.
            </span>
          )}
        </div>
      </div>
    </section>
  );
}
