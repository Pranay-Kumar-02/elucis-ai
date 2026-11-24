import { isRouteErrorResponse, Link, useRouteError } from "react-router";

import { Button } from "@/components/ui/button";

export function RouteError() {
  const error = useRouteError();
  const detail = isRouteErrorResponse(error) ? `${error.status} ${error.statusText}` : null;
  return (
    <div role="alert" className="mx-auto max-w-md px-4 py-20 text-center">
      <h1 className="text-[22px] font-semibold">This page couldn't be displayed</h1>
      <p className="mt-2 text-muted-foreground">
        Reload the page. If it happens again, note the time and what you clicked.
      </p>
      {detail && <p className="mt-2 text-[13px] text-muted-foreground">{detail}</p>}
      <Button asChild variant="outline" className="mt-6">
        <Link to="/">Go to dashboard</Link>
      </Button>
    </div>
  );
}
