import { LogOut } from "lucide-react";
import { useNavigate } from "react-router";

import { Button } from "@/components/ui/button";
import { useMe, useSignOut } from "@/features/auth/queries";

/** The signed-in user and sign-out (FR-AUTH-03: the session ends immediately). */
export function UserMenu() {
  const me = useMe();
  const signOut = useSignOut();
  const navigate = useNavigate();
  const user = me.data?.user;
  if (!user) return null;
  return (
    <div className="flex items-center gap-1">
      <span className="hidden max-w-[12rem] truncate text-[13px] text-muted-foreground lg:inline">
        {user.display_name ?? user.email}
      </span>
      <Button
        variant="ghost"
        size="icon"
        aria-label="Sign out"
        title="Sign out"
        disabled={signOut.isPending}
        onClick={() => {
          signOut.mutate(undefined, {
            onSettled: () => void navigate("/sign-in", { replace: true }),
          });
        }}
      >
        <LogOut />
      </Button>
    </div>
  );
}
