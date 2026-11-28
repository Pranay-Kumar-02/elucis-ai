import type { WeekOut } from "@/lib/api/types";

/**
 * Weekly volume as columns: one series, one hue (the action colour), recessive baseline,
 * hover tooltip per column through SVG <title>, and a text summary for screen readers.
 * Counts come straight from the API (SQL); nothing is estimated here.
 */
export function WeeklyChart({
  weeks,
  label,
  height = 36,
  compact = false,
}: {
  weeks: WeekOut[];
  label: string;
  height?: number;
  compact?: boolean;
}) {
  if (weeks.length === 0) {
    return <span className="text-[12px] text-muted-foreground">No dated feedback</span>;
  }
  const shown = compact ? weeks.slice(-12) : weeks;
  const max = Math.max(...shown.map((w) => w.n), 1);
  const bar = compact ? 6 : 14;
  const gap = 2; // surface gap between columns
  const width = shown.length * (bar + gap);
  const summary = `${label}: ${shown.map((w) => `${w.week} ${String(w.n)}`).join(", ")}`;
  return (
    <svg
      role="img"
      aria-label={summary}
      width={width}
      height={height + (compact ? 0 : 14)}
      className="overflow-visible text-primary"
    >
      {shown.map((w, i) => {
        const h = w.n === 0 ? 0 : Math.max(2, (w.n / max) * height);
        const x = i * (bar + gap);
        return (
          <g key={w.week}>
            <title>{`Week of ${w.start}: ${String(w.n)} record${w.n === 1 ? "" : "s"}`}</title>
            {/* Invisible hit target taller than the mark, so short columns are easy to hover. */}
            <rect x={x} y={0} width={bar} height={height} fill="transparent" />
            <rect
              x={x}
              y={height - h}
              width={bar}
              height={h}
              rx={Math.min(2, bar / 2)}
              fill="currentColor"
            />
          </g>
        );
      })}
      <line
        x1={0}
        x2={width - gap}
        y1={height + 0.5}
        y2={height + 0.5}
        className="stroke-border"
        strokeWidth={1}
      />
      {!compact && (
        <>
          <text x={0} y={height + 12} className="fill-muted-foreground text-[10px]">
            {shown[0]?.week}
          </text>
          {shown.length > 1 && (
            <text
              x={width - gap}
              y={height + 12}
              textAnchor="end"
              className="fill-muted-foreground text-[10px]"
            >
              {shown.at(-1)?.week}
            </text>
          )}
        </>
      )}
    </svg>
  );
}
