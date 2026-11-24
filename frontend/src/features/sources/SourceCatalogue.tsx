import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useSourceAdapters } from "@/features/sources/queries";

/** Which data sources exist: only file import is implemented; connectors are designed only. */
export function SourceCatalogue() {
  const { data, isPending, isError } = useSourceAdapters();
  return (
    <Card>
      <CardHeader>
        <CardTitle>Data sources</CardTitle>
        <CardDescription>Source adapters (D01 §3)</CardDescription>
      </CardHeader>
      <CardContent>
        {isPending && <Skeleton className="h-40" />}
        {isError && <p className="text-sm text-muted-foreground">Catalogue not available.</p>}
        {data && (
          <ul className="space-y-3">
            {data.map((s) => (
              <li key={s.kind} className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-medium">{s.label}</p>
                  {s.auth && <p className="text-xs text-muted-foreground">{s.auth}</p>}
                </div>
                <Badge variant={s.status === "implemented" ? "success" : "secondary"}>
                  {s.status === "implemented" ? "Implemented" : "Designed"}
                </Badge>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
