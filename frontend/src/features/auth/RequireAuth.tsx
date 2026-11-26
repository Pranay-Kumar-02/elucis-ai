import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router";

import { ErrorAlert } from "@/components/layout/ErrorAlert";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useMe } from "@/features/auth/queries";
import { ApiError } from "@/lib/api/client";

/** Everything except sign-in and registration needs a session (FR-AUTH-02). */
export function RequireAuth({ children }: { children: ReactNode }) {
  const me = useMe();
  const location = useLocation();

  if (me.isPending) {
    return (
      <div className="mx-auto max-w-md space-y-3 px-6 py-24" aria-busy="true">
        <Skeleton className="h-6 w-40" />
        <Skeleton className="h-4 w-64" />
      </div>
    );
  }
  if (me.error instanceof ApiError && me.error.status === 401) {
    const next = encodeURIComponent(location.pathname + location.search);
    return <Navigate to={`/sign-in?next=${next}`} replace />;
  }
  if (me.isError) {
    return (
      <div className="mx-auto max-w-md space-y-4 px-6 py-24">
        <ErrorAlert
          error={me.error}
          title="Could not load your account"
          hint="Check that the server is running, then try again."
        />
        <Button variant="outline" onClick={() => void me.refetch()}>
          Try again
        </Button>
      </div>
    );
  }
  return children;
}
