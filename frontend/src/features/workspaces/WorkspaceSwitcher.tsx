import { useId } from "react";
import { Link } from "react-router";

import { NativeSelect } from "@/components/ui/native-select";
import { useActiveWorkspace } from "@/features/workspaces/active";

/** Header control for FR-AUTH-10: choose the active workspace among the user's memberships. */
export function WorkspaceSwitcher() {
  const { active, memberships, select } = useActiveWorkspace();
  const id = useId();

  if (!active) {
    return (
      <Link to="/workspaces" className="text-sm font-medium text-primary hover:underline">
        Create a workspace
      </Link>
    );
  }
  return (
    <div className="flex items-center gap-2">
      <label htmlFor={id} className="sr-only">
        Active workspace
      </label>
      <NativeSelect
        id={id}
        className="h-8 max-w-[14rem] text-[13px]"
        value={active.workspace_id}
        onChange={(e) => {
          select(e.target.value);
        }}
      >
        {memberships.map((m) => (
          <option key={m.workspace_id} value={m.workspace_id}>
            {m.workspace_name}
          </option>
        ))}
      </NativeSelect>
    </div>
  );
}
