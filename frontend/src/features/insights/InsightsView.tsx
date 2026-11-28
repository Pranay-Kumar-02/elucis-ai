import { Minus, Quote, TrendingDown, TrendingUp } from "lucide-react";
import { useId, useState } from "react";

import { ErrorAlert } from "@/components/layout/ErrorAlert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { NativeSelect } from "@/components/ui/native-select";
import { Skeleton } from "@/components/ui/skeleton";
import { categoryLabels } from "@/features/analysis/queries";
import { formatDay, formatWhen } from "@/features/imports/labels";
import { useInsights, useRequestDetail, useThemeDetail } from "@/features/insights/queries";
import { WeeklyChart } from "@/features/insights/WeeklyChart";
import { sourceTypes } from "@/features/sources/fields";
import type {
  EvidenceOut,
  GroupStatsOut,
  InsightsFilters,
  InsightsOut,
  RequestOut,
  ThemeOut,
  Trend,
} from "@/lib/api/types";
import { cn } from "@/lib/utils";

const trendMeta: Record<Trend, { icon: typeof Minus; label: string }> = {
  up: { icon: TrendingUp, label: "Rising" },
  down: { icon: TrendingDown, label: "Falling" },
  flat: { icon: Minus, label: "Steady" },
};

const percent = (x: number) => `${String(Math.round(x * 100))}%`;
const sourceLabel = (v: string) => sourceTypes.find((t) => t.value === v)?.label ?? v;

function TrendLabel({ trend }: { trend: Trend }) {
  const meta = trendMeta[trend];
  const Icon = meta.icon;
  return (
    <span className="inline-flex items-center gap-1 text-[12px] text-muted-foreground">
      <Icon className="size-3.5" aria-hidden />
      {meta.label}
    </span>
  );
}

/** Known customers with identity coverage (CR-18): unknown identities are never customers. */
function Customers({ stats }: { stats: GroupStatsOut }) {
  return (
    <span className="text-[13px] text-muted-foreground">
      <span className="tabular font-medium text-foreground">
        {stats.known_customers.toLocaleString()}
      </span>{" "}
      customer{stats.known_customers === 1 ? "" : "s"}
      {stats.unknown_identity_records > 0 && (
        <>
          {" "}
          · {stats.unknown_identity_records.toLocaleString()} unknown identity (
          {percent(stats.identity_coverage)} identified)
        </>
      )}
    </span>
  );
}

function EvidenceList({ items }: { items: EvidenceOut[] }) {
  if (items.length === 0) {
    return <p className="text-[13px] text-muted-foreground">No quotes in this period.</p>;
  }
  return (
    <ul className="space-y-2">
      {items.map((e) => (
        <li key={e.record_id} className="flex gap-2 text-[13px]">
          <Quote className="mt-0.5 size-3.5 shrink-0 text-warning" aria-hidden />
          <div className="min-w-0">
            <p className="break-words">“{e.text}”</p>
            <p className="text-[12px] text-muted-foreground">
              E-{e.record_id.slice(0, 6)}
              {e.occurred_at && <> · {formatDay(e.occurred_at)}</>}
              {e.rating !== null && <> · {"★".repeat(e.rating)}</>}
              {e.cited && <> · cited in the theme name</>}
            </p>
          </div>
        </li>
      ))}
    </ul>
  );
}

function ThemeCard({
  theme,
  ws,
  filters,
}: {
  theme: ThemeOut;
  ws: string;
  filters: InsightsFilters;
}) {
  const [open, setOpen] = useState(false);
  const detail = useThemeDetail(ws, theme.id, filters, open);
  const negative = theme.sentiment["negative"] ?? 0;
  const categories = Object.entries(theme.categories).sort(([, a], [, b]) => b - a);
  return (
    <li className="rounded-xl border bg-card px-5 py-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1 basis-80">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-[15px] font-semibold">{theme.name}</h3>
            {theme.pain_point && <Badge variant="warning">Pain point</Badge>}
            {theme.vocal_flag && <Badge variant="outline">Mostly one customer</Badge>}
          </div>
          {theme.description && (
            <p className="mt-1 text-[13px] text-muted-foreground">{theme.description}</p>
          )}
          <p className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1">
            <span className="text-[13px]">
              <span className="tabular font-medium">{theme.record_count.toLocaleString()}</span>{" "}
              records · {percent(theme.share)} of feedback
            </span>
            <Customers stats={theme} />
            <TrendLabel trend={theme.trend} />
          </p>
          <p className="mt-1 text-[12px] text-muted-foreground">
            {percent(negative / theme.record_count)} negative ·{" "}
            {categories
              .slice(0, 3)
              .map(([c, n]) => `${categoryLabels[c] ?? c} ${String(n)}`)
              .join(" · ")}
          </p>
        </div>
        <WeeklyChart weeks={theme.weekly} label={`Weekly records for ${theme.name}`} compact />
      </div>
      <div className="mt-3">
        <EvidenceList items={open && detail.data ? detail.data.evidence : theme.evidence} />
        {open && detail.isPending && <Skeleton className="mt-2 h-10 w-full" />}
        {open && detail.isError && (
          <ErrorAlert error={detail.error} title="More evidence could not load" />
        )}
        {open && detail.data && (
          <div className="mt-3">
            <p className="mb-1 text-[12px] text-muted-foreground">Records per week</p>
            <WeeklyChart weeks={detail.data.weekly} label={`Weekly records for ${theme.name}`} />
            {detail.data.undated > 0 && (
              <p className="text-[12px] text-muted-foreground">
                {detail.data.undated.toLocaleString()} records have no date.
              </p>
            )}
          </div>
        )}
        <Button
          variant="ghost"
          size="sm"
          className="mt-2 px-0"
          aria-expanded={open}
          onClick={() => {
            setOpen((v) => !v);
          }}
        >
          {open ? "Show less" : "Show more evidence"}
        </Button>
      </div>
    </li>
  );
}

function RequestRow({
  request,
  ws,
  filters,
}: {
  request: RequestOut;
  ws: string;
  filters: InsightsFilters;
}) {
  const [open, setOpen] = useState(false);
  const detail = useRequestDetail(ws, request.id, filters, open);
  const others = request.asks.filter((a) => a.ask !== request.title).slice(0, 3);
  return (
    <li className="px-5 py-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1 basis-80">
          <h3 className="text-[15px] font-semibold">{request.title}</h3>
          <p className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1">
            <span className="text-[13px]">
              <span className="tabular font-medium">{request.record_count.toLocaleString()}</span>{" "}
              request{request.record_count === 1 ? "" : "s"}
            </span>
            <Customers stats={request} />
            <TrendLabel trend={request.trend} />
          </p>
          {others.length > 0 && (
            <p className="mt-1 text-[12px] text-muted-foreground">
              Also asked as: {others.map((a) => `“${a.ask}” (${String(a.n)})`).join(", ")}
            </p>
          )}
          {request.low_confidence > 0 && (
            <p className="mt-1 text-[12px] text-muted-foreground">
              {request.low_confidence} ask{request.low_confidence === 1 ? "" : "s"} taken from the
              customer’s own words (the model gave no valid summary).
            </p>
          )}
        </div>
        <WeeklyChart
          weeks={request.weekly}
          label={`Weekly requests for ${request.title}`}
          compact
        />
      </div>
      {open && (
        <div className="mt-3">
          {detail.isPending && <Skeleton className="h-10 w-full" />}
          {detail.isError && <ErrorAlert error={detail.error} title="Requests could not load" />}
          {detail.data && <EvidenceList items={detail.data.evidence} />}
        </div>
      )}
      <Button
        variant="ghost"
        size="sm"
        className="mt-2 px-0"
        aria-expanded={open}
        onClick={() => {
          setOpen((v) => !v);
        }}
      >
        {open ? "Hide requests" : "Show requests"}
      </Button>
    </li>
  );
}

function FilterBar({
  filters,
  data,
  onChange,
}: {
  filters: InsightsFilters;
  data: InsightsOut | undefined;
  onChange: (next: InsightsFilters) => void;
}) {
  const id = useId();
  const active = Boolean(
    filters.from ?? filters.to ?? filters.source_type ?? filters.pain_points_only,
  );
  const set = (patch: InsightsFilters) => {
    const merged = { ...filters, ...patch };
    // Empty values mean "no filter": keep only the ones that are set.
    onChange(Object.fromEntries(Object.entries(merged).filter(([, v]) => v !== "" && v !== false)));
  };
  return (
    <div
      role="group"
      aria-label="Filters"
      className="flex flex-wrap items-end gap-4 rounded-xl border bg-card px-5 py-3"
    >
      <div className="space-y-1">
        <Label htmlFor={`${id}-from`}>From</Label>
        <Input
          id={`${id}-from`}
          type="date"
          className="w-40"
          value={filters.from ?? ""}
          min={data?.date_range.from ?? undefined}
          max={filters.to ?? data?.date_range.to ?? undefined}
          onChange={(e) => {
            set({ from: e.target.value });
          }}
        />
      </div>
      <div className="space-y-1">
        <Label htmlFor={`${id}-to`}>To</Label>
        <Input
          id={`${id}-to`}
          type="date"
          className="w-40"
          value={filters.to ?? ""}
          min={filters.from ?? data?.date_range.from ?? undefined}
          max={data?.date_range.to ?? undefined}
          onChange={(e) => {
            set({ to: e.target.value });
          }}
        />
      </div>
      <div className="space-y-1">
        <Label htmlFor={`${id}-source`}>Source</Label>
        <NativeSelect
          id={`${id}-source`}
          value={filters.source_type ?? ""}
          onChange={(e) => {
            set({ source_type: e.target.value });
          }}
        >
          <option value="">All sources</option>
          {(data?.source_types ?? []).map((s) => (
            <option key={s} value={s}>
              {sourceLabel(s)}
            </option>
          ))}
        </NativeSelect>
      </div>
      <label className="flex items-center gap-2 pb-2 text-sm">
        <input
          type="checkbox"
          className="size-4 accent-[var(--color-primary)]"
          checked={Boolean(filters.pain_points_only)}
          onChange={(e) => {
            set({ pain_points_only: e.target.checked });
          }}
        />
        Pain points only
      </label>
      {active && (
        <Button
          variant="ghost"
          size="sm"
          className="mb-1"
          onClick={() => {
            onChange({});
          }}
        >
          Clear filters
        </Button>
      )}
    </div>
  );
}

function Tile({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-xl border bg-card px-5 py-4">
      <p className="text-[12px] text-muted-foreground">{label}</p>
      <p className="tabular text-[26px] font-semibold">{value.toLocaleString()}</p>
    </div>
  );
}

/**
 * Insights (D12 UI-11 with the theme list of UI-06): pain points and themes with counts,
 * customers, trends and evidence quotes, and feature-request groups, for the current
 * analysis run. Every figure comes from the API; quotes are masked customer text.
 */
export function InsightsView({ ws, rerunning }: { ws: string; rerunning: boolean }) {
  const [filters, setFilters] = useState<InsightsFilters>({});
  const insights = useInsights(ws, filters);
  const data = insights.data;

  return (
    <div className="space-y-6" aria-busy={insights.isFetching}>
      <FilterBar filters={filters} data={data} onChange={setFilters} />
      {insights.isError && <ErrorAlert error={insights.error} title="Insights could not load" />}
      {insights.isPending && (
        <div className="grid gap-4 sm:grid-cols-4" aria-label="Loading insights">
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-20" />
          ))}
          <Skeleton className="h-40 sm:col-span-4" />
        </div>
      )}
      {data && (
        <div className={cn("space-y-8", insights.isFetching && "opacity-70")}>
          {rerunning && (
            <p className="text-[13px] text-muted-foreground" role="status">
              A new analysis is running; these are the previous results.
            </p>
          )}
          <div className="grid gap-4 sm:grid-cols-4">
            <Tile label="Feedback analysed" value={data.records_analysed} />
            <Tile label="Themes" value={data.themes.length} />
            <Tile label="Pain points" value={data.pain_points} />
            <Tile label="Request groups" value={data.requests.length} />
          </div>
          {data.run_finished_at && (
            <p className="-mt-4 text-[12px] text-muted-foreground">
              From the analysis of {formatWhen(data.run_finished_at)}
              {data.date_range.from && data.date_range.to && (
                <>
                  {" "}
                  · feedback dated {formatDay(data.date_range.from)} to{" "}
                  {formatDay(data.date_range.to)}
                </>
              )}
            </p>
          )}

          <section aria-labelledby="themes-heading" className="space-y-3">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <h2 id="themes-heading" className="text-[18px] font-semibold">
                {filters.pain_points_only ? "Pain points" : "Pain points and themes"}
              </h2>
              {data.unassigned > 0 && (
                <p className="text-[13px] text-muted-foreground">
                  Unassigned: {data.unassigned.toLocaleString()} records fit no theme
                </p>
              )}
            </div>
            {data.records_analysed === 0 ? (
              <p className="rounded-xl border bg-card px-5 py-6 text-sm text-muted-foreground">
                No feedback matches these filters.
              </p>
            ) : data.themes.length === 0 ? (
              <p className="rounded-xl border bg-card px-5 py-6 text-sm text-muted-foreground">
                {filters.pain_points_only
                  ? "No theme here is mostly problems or negative feedback."
                  : "No themes yet: themes need at least 10 analysed records with something in common."}
              </p>
            ) : (
              <ul className="space-y-3">
                {data.themes.map((t) => (
                  <ThemeCard key={t.id} theme={t} ws={ws} filters={filters} />
                ))}
              </ul>
            )}
          </section>

          <section aria-labelledby="requests-heading" className="space-y-3">
            <h2 id="requests-heading" className="text-[18px] font-semibold">
              Feature requests
            </h2>
            {data.requests.length === 0 ? (
              <p className="rounded-xl border bg-card px-5 py-6 text-sm text-muted-foreground">
                No feature requests in{" "}
                {data.records_analysed === 0 ? "these filters" : "this analysis"}.
              </p>
            ) : (
              <ul className="divide-y rounded-xl border bg-card">
                {data.requests.map((r) => (
                  <RequestRow key={r.id} request={r} ws={ws} filters={filters} />
                ))}
              </ul>
            )}
          </section>
        </div>
      )}
    </div>
  );
}
