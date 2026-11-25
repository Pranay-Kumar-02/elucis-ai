import { FileUp } from "lucide-react";
import { useId, useState, type DragEvent } from "react";

import { Button } from "@/components/ui/button";
import { NativeSelect } from "@/components/ui/native-select";
import { Textarea } from "@/components/ui/textarea";
import { sourceTypes } from "@/features/sources/fields";
import {
  ACCEPTED_EXTENSIONS,
  ACCEPTED_FILES,
  MAX_UPLOAD_BYTES,
  formatBytes,
} from "@/features/sources/format";
import type { SourceInput } from "@/lib/api/endpoints";
import type { SourceType } from "@/lib/api/types";
import { cn } from "@/lib/utils";

const MAX_PASTED_CHARS = 1_000_000;

interface Props {
  sourceType: SourceType;
  onSourceTypeChange: (value: SourceType) => void;
  onInput: (input: SourceInput) => void;
  onLocalError: (message: string | null) => void;
  busy: boolean;
}

/** Step 1 (UI-02): what kind of feedback, and where it comes from. */
export function SourceInputPanel({
  sourceType,
  onSourceTypeChange,
  onInput,
  onLocalError,
  busy,
}: Props) {
  const fileId = useId();
  const typeId = useId();
  const textId = useId();
  const [mode, setMode] = useState<"file" | "text">("file");
  const [text, setText] = useState("");
  const [dragging, setDragging] = useState(false);

  const takeFile = (file: File | undefined) => {
    if (!file) return;
    const ext = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
    if (!ACCEPTED_EXTENSIONS.includes(ext)) {
      onLocalError(`${file.name} isn't a CSV, JSON or text file.`);
      return;
    }
    if (file.size > MAX_UPLOAD_BYTES) {
      onLocalError(`${file.name} is ${formatBytes(file.size)}. Files can be up to 20 MB.`);
      return;
    }
    onLocalError(null);
    onInput({ kind: "file", file });
  };

  const onDrop = (event: DragEvent<HTMLLabelElement>) => {
    event.preventDefault();
    setDragging(false);
    takeFile(event.dataTransfer.files[0]);
  };

  return (
    <section aria-labelledby="source-heading" className="rounded-xl border bg-card">
      <div className="flex flex-wrap items-end gap-4 border-b px-6 py-4">
        <h2 id="source-heading" className="mr-auto text-[15px] font-semibold">
          Feedback source
        </h2>
        <div className="w-full sm:w-64">
          <label htmlFor={typeId} className="mb-1 block text-[13px] text-muted-foreground">
            Type of feedback
          </label>
          <NativeSelect
            id={typeId}
            value={sourceType}
            disabled={busy}
            onChange={(e) => {
              onSourceTypeChange(e.target.value as SourceType);
            }}
          >
            {sourceTypes.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </NativeSelect>
          <p className="mt-1 text-[12px] text-muted-foreground">
            {sourceTypes.find((t) => t.value === sourceType)?.hint}
          </p>
        </div>
      </div>
      <div className="space-y-4 px-6 py-5">
        <div
          role="radiogroup"
          aria-label="How to add feedback"
          className="inline-flex rounded-lg bg-muted p-1"
        >
          {(["file", "text"] as const).map((value) => (
            <button
              key={value}
              type="button"
              role="radio"
              aria-checked={mode === value}
              onClick={() => {
                setMode(value);
              }}
              className={cn(
                "rounded-md px-3 py-1.5 text-[13px] font-medium transition-colors",
                mode === value
                  ? "bg-card shadow-xs"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              {value === "file" ? "Upload a file" : "Paste text"}
            </button>
          ))}
        </div>

        {mode === "file" ? (
          <>
            <label
              htmlFor={fileId}
              onDragOver={(e) => {
                e.preventDefault();
                setDragging(true);
              }}
              onDragLeave={() => {
                setDragging(false);
              }}
              onDrop={onDrop}
              className={cn(
                "flex cursor-pointer flex-col items-center justify-center gap-3 rounded-lg border border-dashed px-6 py-10 text-center transition-colors",
                dragging ? "border-primary bg-accent" : "hover:border-primary/60",
                busy && "pointer-events-none opacity-70",
              )}
            >
              <span className="flex size-11 items-center justify-center rounded-full bg-accent text-accent-foreground">
                <FileUp className="size-5" aria-hidden />
              </span>
              <span className="text-[15px] font-medium">
                {busy ? "Reading…" : "Drop a file here or choose one"}
              </span>
              <span className="text-[13px] text-muted-foreground">
                CSV with a header row, a JSON array of records, or a text transcript. Up to 20 MB.
              </span>
              <span className="sr-only">Choose a file</span>
            </label>
            <input
              id={fileId}
              type="file"
              accept={ACCEPTED_FILES}
              className="sr-only"
              disabled={busy}
              onChange={(event) => {
                takeFile(event.target.files?.[0]);
                event.target.value = "";
              }}
            />
          </>
        ) : (
          <div className="space-y-3">
            <label htmlFor={textId} className="sr-only">
              Pasted feedback
            </label>
            <Textarea
              id={textId}
              value={text}
              maxLength={MAX_PASTED_CHARS}
              placeholder={
                "Paste feedback or a call transcript.\nSeparate items with a blank line, or use “Name: …” for speakers."
              }
              onChange={(e) => {
                setText(e.target.value);
              }}
              disabled={busy}
            />
            <div className="flex items-center justify-between gap-3">
              <span className="tabular text-[12px] text-muted-foreground">
                {text.length.toLocaleString()} / {MAX_PASTED_CHARS.toLocaleString()} characters
              </span>
              <Button
                size="sm"
                disabled={busy || text.trim() === ""}
                onClick={() => {
                  onLocalError(null);
                  onInput({ kind: "text", text });
                }}
              >
                Preview text
              </Button>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
