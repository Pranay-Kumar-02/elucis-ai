import { AlertTriangle } from "lucide-react";
import { useId } from "react";

import { ErrorAlert } from "@/components/layout/ErrorAlert";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useUpdateWorkspace } from "@/features/workspaces/queries";
import type { WorkspaceOut } from "@/lib/api/types";

/**
 * Optional cloud backup for analysis (IMP-38). Off by default; only an Owner can turn it on,
 * and only when the server has a Gemini key. The warning states Google's free-tier terms
 * (F-10) plainly, because the decision is the Owner's to make with the facts in view.
 */
export function AiBackupCard({ workspace }: { workspace: WorkspaceOut }) {
  const update = useUpdateWorkspace(workspace.id);
  const id = useId();
  const isOwner = workspace.role === "owner";
  const enabled = workspace.gemini_fallback;
  const available = workspace.gemini_available;

  return (
    <Card>
      <CardHeader>
        <CardTitle>AI backup</CardTitle>
        <CardDescription>
          Analysis runs on the local models on this computer. A cloud backup can answer the calls
          the local model fails; it never replaces it.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {update.isError && <ErrorAlert error={update.error} title="The setting was not saved" />}
        <label htmlFor={id} className="flex items-start gap-3">
          <input
            id={id}
            type="checkbox"
            role="switch"
            aria-checked={enabled}
            className="mt-1 size-4 accent-[var(--color-primary)]"
            checked={enabled}
            disabled={!isOwner || !available || update.isPending}
            onChange={(e) => {
              update.mutate({ gemini_fallback: e.target.checked });
            }}
          />
          <span>
            <span className="text-sm font-medium">
              Use Google Gemini as a backup when the local model fails
            </span>
            <span className="block text-[13px] text-muted-foreground">
              {enabled ? "On" : "Off"}
              {!available && " · Not available: GEMINI_API_KEY is not set on the server"}
              {available && !isOwner && " · Only Owners can change this"}
            </span>
          </span>
        </label>
        <Alert>
          <AlertTriangle aria-hidden />
          <AlertTitle>What is sent, and Google's terms</AlertTitle>
          <AlertDescription>
            <p>
              Only masked feedback text (personal data replaced by [EMAIL], [NAME] and similar) of
              the calls the local model could not answer. Embeddings and everything else stay on
              this computer.
            </p>
            <p>
              On Google's free tier, Google may use what you send to improve its products, and human
              reviewers may read it. Don't enable this for confidential feedback unless the key
              belongs to a billed Google Cloud project.
            </p>
          </AlertDescription>
        </Alert>
      </CardContent>
    </Card>
  );
}
