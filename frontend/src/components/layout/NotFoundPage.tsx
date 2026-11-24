import { Link } from "react-router";

import { Button } from "@/components/ui/button";

export function NotFoundPage() {
  return (
    <div className="mx-auto max-w-md py-20 text-center">
      <h1 className="text-[26px] font-semibold tracking-[-0.015em]">Page not found</h1>
      <p className="mt-2 text-muted-foreground">
        The address may be mistyped, or the page has moved.
      </p>
      <Button asChild className="mt-6">
        <Link to="/">Go to dashboard</Link>
      </Button>
    </div>
  );
}
