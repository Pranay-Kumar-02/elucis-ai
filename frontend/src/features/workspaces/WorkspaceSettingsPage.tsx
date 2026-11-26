import { CheckCircle2, Plus, Trash2 } from "lucide-react";
import { useId, useState, type SubmitEvent } from "react";
import { useNavigate } from "react-router";

import { ErrorAlert } from "@/components/layout/ErrorAlert";
import { PageHeader } from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { useActiveWorkspace } from "@/features/workspaces/active";
import { NoWorkspace } from "@/features/workspaces/NoWorkspace";
import {
  useDeleteWorkspace,
  useUpdateWorkspace,
  useWorkspace,
} from "@/features/workspaces/queries";
import { roleLabels } from "@/features/workspaces/roles";
import { SettingsTabs } from "@/features/workspaces/SettingsTabs";
import type { DeletingState } from "@/features/workspaces/WorkspacesPage";
import type { WorkspaceOut } from "@/lib/api/types";

interface GlossaryRow {
  term: string;
  definition: string;
}

function toRows(glossary: Record<string, string>): GlossaryRow[] {
  return Object.entries(glossary).map(([term, definition]) => ({ term, definition }));
}

/** Name, description and the product profile used when generating documents (CR-07). */
function GeneralForm({ workspace }: { workspace: WorkspaceOut }) {
  const update = useUpdateWorkspace(workspace.id);
  const canEdit = workspace.role === "owner";
  const [form, setForm] = useState({
    name: workspace.name,
    description: workspace.description ?? "",
    product_name: workspace.product_name ?? "",
    product_description: workspace.product_description ?? "",
    target_users: workspace.target_users ?? "",
  });
  const [glossary, setGlossary] = useState<GlossaryRow[]>(() => toRows(workspace.glossary));
  const id = useId();

  const field = (key: keyof typeof form, label: string, max: number, multiline = false) => {
    const props = {
      id: `${id}-${key}`,
      value: form[key],
      maxLength: max,
      disabled: !canEdit,
      onChange: (e: { target: { value: string } }) => {
        setForm({ ...form, [key]: e.target.value });
      },
    };
    return (
      <div className="space-y-1.5">
        <Label htmlFor={props.id}>{label}</Label>
        {multiline ? <Textarea rows={3} {...props} /> : <Input {...props} />}
      </div>
    );
  };

  const onSubmit = (event: SubmitEvent<HTMLFormElement>) => {
    event.preventDefault();
    const blank = (v: string) => (v.trim() ? v.trim() : null);
    update.mutate({
      name: form.name.trim(),
      description: blank(form.description),
      product_name: blank(form.product_name),
      product_description: blank(form.product_description),
      target_users: blank(form.target_users),
      glossary: Object.fromEntries(
        glossary.filter((r) => r.term.trim()).map((r) => [r.term.trim(), r.definition.trim()]),
      ),
    });
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>General</CardTitle>
        <CardDescription>
          {canEdit
            ? "The product profile and glossary help the assistant and documents use your terms."
            : `Only Owners can change these settings. Your role: ${roleLabels[workspace.role]}.`}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form className="space-y-4" onSubmit={onSubmit}>
          {update.isError && <ErrorAlert error={update.error} title="Changes were not saved" />}
          {update.isSuccess && (
            <p className="flex items-center gap-2 text-sm text-success" role="status">
              <CheckCircle2 className="size-4" aria-hidden /> Saved.
            </p>
          )}
          {field("name", "Workspace name", 120)}
          {field("description", "Description", 500, true)}
          {field("product_name", "Product name", 200)}
          {field("product_description", "Product description", 2000, true)}
          {field("target_users", "Target users", 500, true)}
          <fieldset className="space-y-2" disabled={!canEdit}>
            <legend className="text-sm font-medium">Glossary</legend>
            {glossary.length === 0 && (
              <p className="text-sm text-muted-foreground">No terms yet.</p>
            )}
            {glossary.map((row, index) => (
              <div key={index} className="flex gap-2">
                <Input
                  aria-label={`Term ${index + 1}`}
                  className="max-w-[12rem]"
                  maxLength={80}
                  value={row.term}
                  onChange={(e) => {
                    setGlossary(
                      glossary.map((r, i) => (i === index ? { ...r, term: e.target.value } : r)),
                    );
                  }}
                />
                <Input
                  aria-label={`Definition ${index + 1}`}
                  maxLength={500}
                  value={row.definition}
                  onChange={(e) => {
                    setGlossary(
                      glossary.map((r, i) =>
                        i === index ? { ...r, definition: e.target.value } : r,
                      ),
                    );
                  }}
                />
                {canEdit && (
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    aria-label={`Remove term ${index + 1}`}
                    onClick={() => {
                      setGlossary(glossary.filter((_, i) => i !== index));
                    }}
                  >
                    <Trash2 />
                  </Button>
                )}
              </div>
            ))}
            {canEdit && glossary.length < 200 && (
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => {
                  setGlossary([...glossary, { term: "", definition: "" }]);
                }}
              >
                <Plus /> Add term
              </Button>
            )}
          </fieldset>
          {canEdit && (
            <Button type="submit" disabled={update.isPending || !form.name.trim()}>
              {update.isPending ? "Saving…" : "Save changes"}
            </Button>
          )}
        </form>
      </CardContent>
    </Card>
  );
}

/** FR-AUTH-11: deletion needs the exact name typed, and runs as a background job. */
function DangerZone({ workspace }: { workspace: WorkspaceOut }) {
  const remove = useDeleteWorkspace(workspace.id);
  const navigate = useNavigate();
  const [typed, setTyped] = useState("");
  const id = useId();
  const confirmed = typed === workspace.name;

  return (
    <Card className="border-destructive/40">
      <CardHeader>
        <CardTitle>Delete workspace</CardTitle>
        <CardDescription>
          Permanently removes all feedback, analysis, documents, roadmaps and members of this
          workspace. This cannot be undone.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {remove.isError && (
          <ErrorAlert error={remove.error} title="The workspace was not deleted" />
        )}
        <div className="space-y-1.5">
          <Label htmlFor={id}>
            Type <span className="font-semibold">{workspace.name}</span> to confirm
          </Label>
          <Input
            id={id}
            autoComplete="off"
            value={typed}
            onChange={(e) => {
              setTyped(e.target.value);
            }}
          />
        </div>
        <Button
          variant="destructive"
          disabled={!confirmed || remove.isPending}
          onClick={() => {
            remove.mutate(typed, {
              onSuccess: () => {
                const state: DeletingState = {
                  deleting: { id: workspace.id, name: workspace.name },
                };
                void navigate("/workspaces", { state });
              },
            });
          }}
        >
          {remove.isPending ? "Deleting…" : "Delete workspace"}
        </Button>
      </CardContent>
    </Card>
  );
}

export function WorkspaceSettingsPage() {
  const { active } = useActiveWorkspace();
  const workspace = useWorkspace(active?.workspace_id);

  return (
    <>
      <PageHeader title="Settings" description="Workspace profile, members and system status." />
      <SettingsTabs />
      {!active && <NoWorkspace />}
      {active && workspace.isPending && <Skeleton className="h-96 w-full" />}
      {workspace.isError && (
        <ErrorAlert error={workspace.error} title="Could not load the workspace" />
      )}
      {workspace.data && (
        <div className="space-y-6">
          {/* Keyed by workspace so switching workspaces resets the form. */}
          <GeneralForm key={workspace.data.id} workspace={workspace.data} />
          {workspace.data.role === "owner" && (
            <DangerZone key={`danger-${workspace.data.id}`} workspace={workspace.data} />
          )}
        </div>
      )}
    </>
  );
}
