import { useId, useState, type SubmitEvent } from "react";

import { ErrorAlert } from "@/components/layout/ErrorAlert";
import { PageHeader } from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { NativeSelect } from "@/components/ui/native-select";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useMe } from "@/features/auth/queries";
import { useActiveWorkspace } from "@/features/workspaces/active";
import { NoWorkspace } from "@/features/workspaces/NoWorkspace";
import {
  useAddMember,
  useChangeRole,
  useMembers,
  useRemoveMember,
} from "@/features/workspaces/queries";
import { ROLES, roleDescriptions, roleLabels } from "@/features/workspaces/roles";
import { SettingsTabs } from "@/features/workspaces/SettingsTabs";
import type { MemberOut, Role } from "@/lib/api/types";

function AddMemberForm({ workspaceId }: { workspaceId: string }) {
  const add = useAddMember(workspaceId);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<Role>("viewer"); // SEC-21: new members are Viewers
  const id = useId();

  const onSubmit = (event: SubmitEvent<HTMLFormElement>) => {
    event.preventDefault();
    add.mutate(
      { email: email.trim(), role },
      {
        onSuccess: () => {
          setEmail("");
          setRole("viewer");
        },
      },
    );
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Add a member</CardTitle>
        <CardDescription>
          The person must already have an account. {roleDescriptions[role]}.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form className="flex flex-wrap items-end gap-3" onSubmit={onSubmit}>
          <div className="min-w-[16rem] flex-1 space-y-1.5">
            <Label htmlFor={`${id}-email`}>Email</Label>
            <Input
              id={`${id}-email`}
              type="email"
              required
              value={email}
              onChange={(e) => {
                setEmail(e.target.value);
              }}
            />
          </div>
          <div className="w-40 space-y-1.5">
            <Label htmlFor={`${id}-role`}>Role</Label>
            <NativeSelect
              id={`${id}-role`}
              value={role}
              onChange={(e) => {
                setRole(e.target.value as Role);
              }}
            >
              {ROLES.map((r) => (
                <option key={r} value={r}>
                  {roleLabels[r]}
                </option>
              ))}
            </NativeSelect>
          </div>
          <Button type="submit" disabled={add.isPending || !email.trim()}>
            {add.isPending ? "Adding…" : "Add member"}
          </Button>
        </form>
        {add.isError && (
          <div className="mt-4">
            <ErrorAlert error={add.error} title="The member was not added" />
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function MemberRow({
  member,
  workspaceId,
  manage,
  isSelf,
}: {
  member: MemberOut;
  workspaceId: string;
  manage: boolean;
  isSelf: boolean;
}) {
  const change = useChangeRole(workspaceId);
  const remove = useRemoveMember(workspaceId);
  const [confirming, setConfirming] = useState(false);
  const error = change.error ?? remove.error;

  return (
    <TableRow>
      <TableCell>
        <p className="font-medium">
          {member.display_name ?? member.email}
          {isSelf && <span className="ml-2 text-[12px] text-muted-foreground">(you)</span>}
        </p>
        {member.display_name && <p className="text-[13px] text-muted-foreground">{member.email}</p>}
        {error && (
          <div className="mt-2">
            <ErrorAlert error={error} title="Change not saved" />
          </div>
        )}
      </TableCell>
      <TableCell className="w-44">
        {manage ? (
          <NativeSelect
            aria-label={`Role of ${member.email}`}
            value={member.role}
            disabled={change.isPending}
            onChange={(e) => {
              change.mutate({ userId: member.user_id, role: e.target.value as Role });
            }}
          >
            {ROLES.map((r) => (
              <option key={r} value={r}>
                {roleLabels[r]}
              </option>
            ))}
          </NativeSelect>
        ) : (
          roleLabels[member.role]
        )}
      </TableCell>
      {manage && (
        <TableCell className="w-40 text-right">
          <Button
            variant={confirming ? "destructive" : "ghost"}
            size="sm"
            disabled={remove.isPending}
            onClick={() => {
              if (!confirming) {
                setConfirming(true);
                return;
              }
              remove.mutate(member.user_id, {
                onSettled: () => {
                  setConfirming(false);
                },
              });
            }}
          >
            {confirming ? "Confirm removal" : "Remove"}
          </Button>
        </TableCell>
      )}
    </TableRow>
  );
}

export function MembersPage() {
  const { active } = useActiveWorkspace();
  const me = useMe();
  const members = useMembers(active?.workspace_id);
  const isOwner = active?.role === "owner";

  return (
    <>
      <PageHeader title="Settings" description="Workspace profile, members and system status." />
      <SettingsTabs />
      {!active && <NoWorkspace />}
      {active && (
        <div className="space-y-6">
          {isOwner && <AddMemberForm workspaceId={active.workspace_id} />}
          <Card>
            <CardHeader>
              <CardTitle>Members of {active.workspace_name}</CardTitle>
              {!isOwner && (
                <CardDescription>
                  Only Owners can add members or change roles. Your role: {roleLabels[active.role]}.
                </CardDescription>
              )}
            </CardHeader>
            <CardContent>
              {members.isPending && <Skeleton className="h-24 w-full" />}
              {members.isError && (
                <ErrorAlert error={members.error} title="Could not load members" />
              )}
              {members.data && (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Member</TableHead>
                      <TableHead>Role</TableHead>
                      {isOwner && <TableHead className="sr-only">Actions</TableHead>}
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {members.data.items.map((m) => (
                      <MemberRow
                        key={m.user_id}
                        member={m}
                        workspaceId={active.workspace_id}
                        manage={isOwner}
                        isSelf={m.user_id === me.data?.user.id}
                      />
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </div>
      )}
    </>
  );
}
