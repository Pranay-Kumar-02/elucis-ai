import { Link } from "react-router";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

/** Empty state for pages that belong to a workspace when the user has none yet. */
export function NoWorkspace() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>No workspace yet</CardTitle>
        <CardDescription>
          Workspace settings and members appear here once you create or join a workspace.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Button asChild>
          <Link to="/workspaces">Create a workspace</Link>
        </Button>
      </CardContent>
    </Card>
  );
}
