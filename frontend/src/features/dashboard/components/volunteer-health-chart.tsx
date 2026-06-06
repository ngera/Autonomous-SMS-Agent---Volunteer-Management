import { useMemo, useState } from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Sparkles, UserPlus, Users } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/**
 * Volunteer health tracker — three-line preview chart shown until the
 * recruiting / churn / no-show backend lands. Plots weekly counts of
 * new recruits, departures, and no-shows so the admin can see at a
 * glance whether the pool is growing, churning, or flaking on shifts.
 *
 * Like DonationsChart, the data is deterministic dummy so the preview
 * is stable. Replace `generateDummySeries()` with the real hook when
 * the backend exists.
 */

interface VolunteerPoint {
  week: string;
  date: Date;
  recruited: number;
  left: number;
  no_show: number;
  /** Running active-volunteer count, built up from a fixed starting
   *  pool + (recruited − left) each week. */
  active: number;
}

type Range = "ytd" | "1y" | "2y" | "3y";

const RANGE_OPTIONS: { value: Range; label: string }[] = [
  { value: "ytd", label: "YTD" },
  { value: "1y", label: "1Y" },
  { value: "2y", label: "2Y" },
  { value: "3y", label: "3Y" },
];

const SERIES_META = {
  recruited: { label: "Recruited", color: "#10B981" }, // emerald-500
  left: { label: "Left", color: "#F43F5E" }, // rose-500
  no_show: { label: "No-shows", color: "#F59E0B" }, // amber-500
} as const;

function generateDummySeries(): VolunteerPoint[] {
  const out: VolunteerPoint[] = [];
  const today = new Date();
  const start = new Date(today);
  start.setDate(today.getDate() - 7 * 156);
  let seed = 0x5eed1ee;
  const rand = () => {
    seed |= 0;
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
  // Starting active pool — what the org had 3y back. Each week's
  // active count compounds from here as new recruits join and
  // departures leave.
  let active = 25;
  for (let i = 0; i < 156; i++) {
    const d = new Date(start);
    d.setDate(start.getDate() + 7 * i);
    // Recruiting grows over time (word-of-mouth + campaign maturity)
    // with a small Sept/Oct bump (back-to-school volunteering).
    // Values scaled to a ~1/10 magnitude for the preview — small
    // weekly counts read more like a real nonprofit's churn book.
    const recruitedBaseline = 0.3 + Math.pow(i, 0.85) * 0.018;
    const recruitedSeasonal = Math.max(
      0,
      Math.sin(((d.getMonth() - 7) / 12) * Math.PI * 2) * 0.4,
    );
    const recruited = Math.max(
      0,
      Math.round(recruitedBaseline + recruitedSeasonal + (rand() - 0.5) * 0.4),
    );
    // Churn drifts up slowly as the pool grows (always some leakage).
    const leftBaseline = 0.15 + i * 0.0025;
    const left = Math.max(
      0,
      Math.round(leftBaseline + (rand() - 0.5) * 0.3),
    );
    // No-shows track event density — heavier in summer giving season.
    const noShowSeasonal = Math.max(
      0,
      Math.sin(((d.getMonth() - 5) / 12) * Math.PI * 2) * 0.3,
    );
    const no_show = Math.max(
      0,
      Math.round(0.2 + noShowSeasonal + (rand() - 0.5) * 0.25),
    );
    active = Math.max(0, active + recruited - left);
    out.push({
      week: `${d.toLocaleString(undefined, { month: "short" })} ${d.getDate()}`,
      date: d,
      recruited,
      left,
      no_show,
      active,
    });
  }
  return out;
}

function filterSeries(series: VolunteerPoint[], range: Range): VolunteerPoint[] {
  const now = new Date();
  let cutoff: Date;
  if (range === "ytd") {
    cutoff = new Date(now.getFullYear(), 0, 1);
  } else {
    const years = range === "1y" ? 1 : range === "2y" ? 2 : 3;
    cutoff = new Date(now);
    cutoff.setFullYear(now.getFullYear() - years);
  }
  return series.filter((p) => p.date >= cutoff);
}

export function VolunteerHealthChart() {
  const [range, setRange] = useState<Range>("1y");
  const allSeries = useMemo(generateDummySeries, []);
  const series = useMemo(
    () => filterSeries(allSeries, range),
    [allSeries, range],
  );

  const totals = useMemo(
    () =>
      series.reduce(
        (acc, p) => ({
          recruited: acc.recruited + p.recruited,
          left: acc.left + p.left,
          no_show: acc.no_show + p.no_show,
        }),
        { recruited: 0, left: 0, no_show: 0 },
      ),
    [series],
  );
  const net = totals.recruited - totals.left;

  return (
    <div className="rounded-2xl border bg-card p-4">
      <div className="mb-2 flex items-baseline justify-between gap-3">
        <div className="flex items-center gap-2">
          <div className="flex h-6 w-6 items-center justify-center rounded-md bg-sky-100 text-sky-700 dark:bg-sky-950/50 dark:text-sky-300">
            <Users className="h-3.5 w-3.5" />
          </div>
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
              Volunteer health
            </p>
            <h3 className="text-sm font-semibold">
              Recruiting · Leaving · No-shows
            </h3>
          </div>
        </div>
        <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-medium text-amber-800 dark:bg-amber-950/50 dark:text-amber-300">
          <Sparkles className="h-3 w-3" />
          Preview · dummy data
        </span>
      </div>

      <div className="mb-2 inline-flex items-center gap-0.5 rounded-md border bg-muted/50 p-0.5">
        {RANGE_OPTIONS.map((opt) => {
          const active = range === opt.value;
          return (
            <button
              key={opt.value}
              type="button"
              onClick={() => setRange(opt.value)}
              className={cn(
                "rounded px-2 py-0.5 text-[11px] font-medium transition-colors",
                active
                  ? "bg-card text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground",
              )}
              aria-pressed={active}
            >
              {opt.label}
            </button>
          );
        })}
      </div>

      <div className="mb-2 grid grid-cols-2 gap-2 text-xs sm:grid-cols-4">
        <Stat
          label="Active"
          value={series[series.length - 1]?.active ?? 0}
          color="#0EA5E9"
          highlight
        />
        <Stat label="Recruited" value={totals.recruited} color={SERIES_META.recruited.color} />
        <Stat label="Left" value={totals.left} color={SERIES_META.left.color} />
        <Stat label="No-shows" value={totals.no_show} color={SERIES_META.no_show.color} />
      </div>
      <p
        className={cn(
          "mb-2 text-xs font-medium tabular-nums",
          net >= 0
            ? "text-emerald-600 dark:text-emerald-400"
            : "text-rose-600 dark:text-rose-400",
        )}
      >
        Net pool change: {net >= 0 ? "+" : ""}
        {net} volunteers
      </p>

      <div className="h-[200px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart
            data={series}
            margin={{ top: 4, right: 8, bottom: 0, left: -16 }}
          >
            <CartesianGrid stroke="rgba(148, 163, 184, 0.15)" vertical={false} />
            <XAxis
              dataKey="week"
              tick={{ fontSize: 10 }}
              tickLine={false}
              axisLine={false}
              stroke="currentColor"
              className="text-muted-foreground"
              interval={Math.max(0, Math.floor(series.length / 8) - 1)}
            />
            <YAxis
              tick={{ fontSize: 10 }}
              tickLine={false}
              axisLine={false}
              width={32}
              stroke="currentColor"
              className="text-muted-foreground"
              allowDecimals={false}
            />
            <Tooltip
              cursor={{
                stroke: "rgba(148, 163, 184, 0.35)",
                strokeWidth: 1,
              }}
              contentStyle={{
                background: "var(--popover)",
                border: "1px solid var(--border)",
                borderRadius: 6,
                fontSize: 12,
                color: "var(--popover-foreground)",
              }}
              labelStyle={{ color: "var(--popover-foreground)", fontWeight: 600 }}
              itemStyle={{ color: "var(--popover-foreground)" }}
              formatter={(v: number, name: string) => {
                const meta =
                  (SERIES_META as Record<string, { label: string }>)[name];
                return [v, meta?.label ?? name];
              }}
            />
            <Legend
              verticalAlign="top"
              height={20}
              iconType="circle"
              iconSize={8}
              wrapperStyle={{ fontSize: 10, paddingBottom: 4 }}
              formatter={(value) => {
                const meta =
                  (SERIES_META as Record<string, { label: string }>)[value];
                return meta?.label ?? value;
              }}
            />
            {(["recruited", "left", "no_show"] as const).map((key) => (
              <Line
                key={key}
                type="monotone"
                dataKey={key}
                stroke={SERIES_META[key].color}
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 4 }}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Dummy CTA — wires up once the Recruiting Campaign backend
          lands. Distinct from Musters (which fill events from the
          existing pool); this one brings NEW volunteers into the pool. */}
      <div className="mt-3 flex items-center justify-between gap-2">
        <Button size="sm" variant="default" className="gap-1" disabled>
          <UserPlus className="h-3.5 w-3.5" />
          Start Recruitment Campaign
        </Button>
        <span className="text-[10px] uppercase tracking-wider text-muted-foreground">
          Preview · not yet wired
        </span>
      </div>

      <p className="mt-2 text-[11px] text-muted-foreground">
        {series.length} week{series.length === 1 ? "" : "s"} shown · real
        numbers will flow in once the recruiting / engagement backends
        track these events end-to-end.
      </p>
    </div>
  );
}

function Stat({
  label,
  value,
  color,
  highlight,
}: {
  label: string;
  value: number;
  color: string;
  highlight?: boolean;
}) {
  return (
    <div
      className={cn(
        "rounded-md border px-2 py-1.5",
        highlight ? "border-sky-200 bg-sky-50 dark:border-sky-900/60 dark:bg-sky-950/30" : "bg-card/50",
      )}
    >
      <p className="flex items-center gap-1 text-[10px] uppercase tracking-wider text-muted-foreground">
        <span
          className="inline-block h-2 w-2 rounded-full"
          style={{ backgroundColor: color }}
        />
        {label}
      </p>
      <p className="text-base font-semibold tabular-nums">{value}</p>
    </div>
  );
}
