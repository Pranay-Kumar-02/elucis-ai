import { useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Loader2 } from "lucide-react";
import { useEffect, useId, useState, type SubmitEvent } from "react";
import { useLocation, useNavigate } from "react-router";

import { ErrorAlert } from "@/components/layout/ErrorAlert";
import { PageHeader } from "@/components/layout/PageHeader";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { meKey } from "@/features/auth/queries";
import { useActiveWorkspace } from "@/features/workspaces/active";
import {
  useCreateWorkspace,
  useWorkspace,
  useWorkspaces,
  workspaceKeys,
} from "@/features/workspaces/queries";
import { roleLabels } from "@/features/workspaces/roles";
import { ApiError } from "@/lib/api/client";

export interface DeletingState {
  deleting?: { id: string; name: string };
}

/** Shows a deletion in progress until the workspace answers 404 (API-09 runs as a job). */
function DeletionStatus({ id, name }: { id: string; name: string }) {
  const probe = useWorkspace(id, { pollUntilGone: true });
  const client = useQueryClient();
  const gone = probe.error instanceof ApiError && probe.error.status === 404;
  useEffect(() => {
    if (!gone) return;
    // The membership is gone too: refresh the switcher and this list.
    void client.invalidateQueries({ queryKey: meKey });
    void client.invalidateQueries({ queryKey: workspaceKeys.all, exact: true });
  }, [gone, client]);
  if (gone) {
    return (
      <Alert>
        <CheckCircle2 aria-hidden className="text-success" />
        <AlertTitle>Workspace deleted</AlertTitle>
        <AlertDescription>“{name}” and all of its data have been removed.</AlertDescription>
      </Alert>
    );
  }
  if (probe.isError)
    return <ErrorAlert error={probe.error} title="Could not confirm the deletion" />;
  return (
    <Alert>
      <Loader2 aria-hidden className="animate-spin" />
      <AlertTitle>Deleting “{name}”</AlertTitle>
      <AlertDescription>
        Removing its feedback, analysis and documents. This page updates when it is done.
      </AlertDescription>
    </Alert>
  );
}

function CreateWorkspaceForm({ first }: { first: boolean }) {
  const create = useCreateWorkspace();
  const { select } = useActiveWorkspace();
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const id = useId();

  const onSubmit = (event: SubmitEvent<HTMLFormElement>) => {
    event.preventDefault();
    create.mutate(
      { name: name.trim(), ...(description.trim() && { description: description.trim() }) },
      {
        onSuccess: (ws) => {
          select(ws.id);
          void navigate("/");
        },
      },
    );
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>{first ? "Create your first workspace" : "Create a workspace"}</CardTitle>
        <CardDescription>
          A workspace holds one product’s feedback, analysis, decisions and documents. You will be
          its Owner and can invite your team.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form className="space-y-4" onSubmit={onSubmit}>
          {create.isError && (
            <ErrorAlert error={create.error} title="Could not create the workspace" />
          )}
          <div className="space-y-1.5">
            <Label htmlFor={`${id}-name`}>Name</Label>
            <Input
              id={`${id}-name`}
              required
              maxLength={120}
              placeholder="For example: Checkout app"
              value={name}
              onChange={(e) => {
                setName(e.target.value);
              }}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor={`${id}-description`}>
              Description <span className="font-normal text-muted-foreground">(optional)</span>
            </Label>
            <Textarea
              id={`${id}-description`}
              maxLength={500}
              rows={2}
              value={description}
              onChange={(e) => {
                setDescription(e.target.value);
              }}
            />
          </div>
          <Button type="submit" disabled={create.isPending || !name.trim()}>
            {create.isPending ? "Creating…" : "Create workspace"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}

export function WorkspacesPage() {
  const workspaces = useWorkspaces();
  const { active, select } = useActiveWorkspace();
  const navigate = useNavigate();
  const deleting = (useLocation().state as DeletingState | null)?.deleting;
  const items = workspaces.data?.items ?? [];

  return (
    <>
      <PageHeader
        title="Workspaces"
        description="Switch between products, or create a workspace for a new one."
      />
      <div className="space-y-6">
        {deleting && <DeletionStatus id={deleting.id} name={deleting.name} />}
        {workspaces.isPending && (
          <div className="space-y-2" aria-busy="true">
            <Skeleton className="h-16 w-full" />
            <Skeleton className="h-16 w-full" />
          </div>
        )}
        {workspaces.isError && (
          <ErrorAlert error={workspaces.error} title="Could not load workspaces" />
        )}
        {items.length > 0 && (
          <ul className="divide-y rounded-xl border bg-card">
            {items.map((ws) => (
              <li key={ws.id} className="flex flex-wrap items-center gap-3 px-5 py-4">
                <div className="min-w-0 flex-1">
                  <p className="font-medium">{ws.name}</p>
                  {ws.description && (
                    <p className="truncate text-sm text-muted-foreground">{ws.description}</p>
                  )}
                </div>
                <Badge variant="secondary">{roleLabels[ws.role]}</Badge>
                {active?.workspace_id === ws.id ? (
                  <span className="text-sm text-muted-foreground">Current</span>
                ) : (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      select(ws.id);
                      void navigate("/");
                    }}
                  >
                    Open
                  </Button>
                )}
              </li>
            ))}
          </ul>
        )}
        {workspaces.isSuccess && <CreateWorkspaceForm first={items.length === 0} />}
      </div>
    </>
  );
}
