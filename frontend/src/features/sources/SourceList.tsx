import { Skeleton } from "@/components/ui/skeleton";
import { useSourceAdapters } from "@/features/sources/queries";

/** Plain-language descriptions; the API returns technical connector details. */
const descriptions: Record<string, string> = {
  file: "CSV, JSON or text exports from any tool",
  google_play: "Reviews from your Play Console",
  app_store: "Reviews from App Store Connect",
  zendesk: "Support tickets and conversations",
  mixpanel: "Product usage events",
  amplitude: "Product usage events",
  ms_graph_transcripts: "Customer call transcripts",
};

/** Data sources: file import works today; connectors are planned and say so. */
export function SourceList() {
  const { data, isPending, isError } = useSourceAdapters();
  return (
    <section aria-labelledby="sources-heading">
      <h2 id="sources-heading" className="mb-3 text-[15px] font-semibold">
        Sources
      </h2>
      {isPending && <Skeleton className="h-64 rounded-xl" />}
      {isError && <p className="text-[13px] text-muted-foreground">Sources couldn't be loaded.</p>}
      {data && (
        <ul className="divide-y rounded-xl border bg-card">
          {data.map((s) => {
            const available = s.status === "implemented";
            return (
              <li key={s.kind} className="flex items-start justify-between gap-3 px-4 py-3">
                <div className="min-w-0">
                  <p className={available ? "font-medium" : "font-medium text-muted-foreground"}>
                    {s.kind === "file" ? "File upload" : s.label}
                  </p>
                  <p className="text-[13px] text-muted-foreground">
                    {descriptions[s.kind] ?? s.label}
                  </p>
                </div>
                <span
                  className={
                    available
                      ? "mt-0.5 shrink-0 rounded-md bg-success/12 px-2 py-0.5 text-[12px] font-medium text-success"
                      : "mt-0.5 shrink-0 rounded-md bg-muted px-2 py-0.5 text-[12px] text-muted-foreground"
                  }
                >
                  {available ? "Available" : "Planned"}
                </span>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
