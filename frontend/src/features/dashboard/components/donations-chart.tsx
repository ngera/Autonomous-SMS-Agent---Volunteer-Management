import { useMemo, useState } from "react";
import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { ArrowDownRight, ArrowUpRight, Heart, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * Donations tracker — preview chart shown while the donation-campaign
 * backend (mustr_pitch_deck plan: Donation Campaigns) is still in
 * scoping. Renders a trend of dummy weekly totals with a
 * "Preview · dummy data" pill so the admin can see the surface
 * before real numbers exist.
 *
 * Replace `generateDummySeries()` with `useDonationsTrend(range)` (or
 * equivalent) when the backend is wired.
 */

interface DonationPoint {
  week: string;        // "May 5" / "May 12" — short label for x-axis
  date: Date;          // anchor for filtering
  // Stacked bar segments — different donor sources roll up to total.
  individual: number;  // one-off individual gifts
  recurring: number;   // monthly subscribers
  corporate: number;   // corporate sponsorships
  events: number;      // donations collected at events
  total: number;       // sum of the four above; convenience for tooltip
  cumulative: number;  // running total across the filtered range
}

const SEGMENT_META = {
  individual: { label: "Individual", color: "#F43F5E" }, // rose-500
  recurring: { label: "Recurring", color: "#8B5CF6" }, // violet-500
  corporate: { label: "Corporate", color: "#0EA5E9" }, // sky-500
  events: { label: "At events", color: "#10B981" }, // emerald-500
} as const;
const SEGMENT_KEYS = ["individual", "recurring", "corporate", "events"] as const;

type Range = "ytd" | "1y" | "2y" | "3y";

const RANGE_OPTIONS: { value: Range; label: string }[] = [
  { value: "ytd", label: "YTD" },
  { value: "1y", label: "1Y" },
  { value: "2y", label: "2Y" },
  { value: "3y", label: "3Y" },
];

/** Build ~3 years of dummy weekly donations with a gentle upward
 *  trend, a seasonal year-end bump, and per-week noise. Deterministic
 *  via a simple PRNG so the preview is stable across reloads. */
function generateDummySeries(): DonationPoint[] {
  const out: DonationPoint[] = [];
  const today = new Date();
  // Anchor on Mondays so each week label is consistent.
  const start = new Date(today);
  start.setDate(today.getDate() - 7 * 156); // ~3y back
  // Seeded PRNG (mulberry32).
  let seed = 0xc0ffee;
  const rand = () => {
    seed |= 0;
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
  for (let i = 0; i < 156; i++) {
    const d = new Date(start);
    d.setDate(start.getDate() + 7 * i);
    // Accelerating baseline (i^1.5) — a young nonprofit growing its
    // donor base. Cumulative on this shape curves upward instead of
    // tracing a near-straight ramp like steady weekly inflows would.
    const baseline = 500 + Math.pow(i, 1.5) * 1.2;
    // Big seasonal bump around the Nov/Dec giving window — gives the
    // cumulative line a visible "step" each year.
    const seasonal = Math.max(
      0,
      Math.sin(((d.getMonth() - 9) / 12) * Math.PI * 2) * 1800,
    );
    const noise = (rand() - 0.5) * 600;
    // Occasional major-gift weeks (~every 25 weeks) — sharp jumps the
    // cumulative line picks up immediately. Skipped on i=0 so the
    // chart's left edge stays low.
    const majorGift =
      i > 0 && i % 25 === 0 ? 4000 + Math.floor(rand() * 4000) : 0;
    const total = Math.max(
      120,
      Math.round(baseline + seasonal + noise + majorGift),
    );
    // Mix split: individuals are the largest segment, recurring grows
    // over time, corporate is lumpy, events spike in seasonal weeks.
    const recurringShare = Math.min(0.4, 0.15 + (i / 156) * 0.25);
    const recurring = Math.round(total * recurringShare);
    const corporate = Math.round(total * (0.1 + (rand() - 0.5) * 0.1));
    const events = Math.round(total * (seasonal > 200 ? 0.18 : 0.06));
    const individual = Math.max(0, total - recurring - corporate - events);
    out.push({
      week: `${d.toLocaleString(undefined, { month: "short" })} ${d.getDate()}`,
      date: d,
      individual,
      recurring,
      corporate,
      events,
      total,
      cumulative: 0, // backfilled after filter (varies per range)
    });
  }
  return out;
}

function formatCurrency(n: number): string {
  if (n >= 1000) return `$${(n / 1000).toFixed(1)}k`;
  return `$${n}`;
}

function filterSeries(series: DonationPoint[], range: Range): DonationPoint[] {
  const now = new Date();
  let cutoff: Date;
  if (range === "ytd") {
    cutoff = new Date(now.getFullYear(), 0, 1);
  } else {
    const years = range === "1y" ? 1 : range === "2y" ? 2 : 3;
    cutoff = new Date(now);
    cutoff.setFullYear(now.getFullYear() - years);
  }
  // Backfill the running total against the filtered range so the
  // cumulative line starts at 0 on the left edge of the visible chart.
  let running = 0;
  return series
    .filter((p) => p.date >= cutoff)
    .map((p) => {
      running += p.total;
      return { ...p, cumulative: running };
    });
}

export function DonationsChart() {
  const [range, setRange] = useState<Range>("1y");
  const allSeries = useMemo(generateDummySeries, []);
  const series = useMemo(() => filterSeries(allSeries, range), [allSeries, range]);

  const total = useMemo(
    () => series.reduce((s, p) => s + p.total, 0),
    [series],
  );
  const last = series[series.length - 1]?.total ?? 0;
  const prev = series[series.length - 2]?.total ?? 0;
  const delta = prev > 0 ? ((last - prev) / prev) * 100 : 0;
  const up = delta >= 0;

  return (
    <div className="rounded-2xl border bg-card p-4">
      <div className="mb-2 flex items-baseline justify-between gap-3">
        <div className="flex items-center gap-2">
          <div className="flex h-6 w-6 items-center justify-center rounded-md bg-rose-100 text-rose-700 dark:bg-rose-950/50 dark:text-rose-300">
            <Heart className="h-3.5 w-3.5" />
          </div>
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
              Donations
            </p>
            <h3 className="text-sm font-semibold">Donation tracker</h3>
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

      <div className="mb-2 flex items-baseline gap-3">
        <p className="text-2xl font-bold tabular-nums">{formatCurrency(total)}</p>
        <span
          className={cn(
            "inline-flex items-center gap-0.5 text-xs font-medium tabular-nums",
            up
              ? "text-emerald-600 dark:text-emerald-400"
              : "text-rose-600 dark:text-rose-400",
          )}
        >
          {up ? (
            <ArrowUpRight className="h-3 w-3" />
          ) : (
            <ArrowDownRight className="h-3 w-3" />
          )}
          {delta >= 0 ? "+" : ""}
          {delta.toFixed(0)}% wk/wk
        </span>
      </div>

      <div className="h-[180px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          {/* ComposedChart layers stacked weekly bars (per donor source)
              under a cumulative line on a secondary y-axis. The bars
              answer "how much came in this week and from whom?" while
              the line answers "where do we stand against goal?". */}
          <ComposedChart
            data={series}
            margin={{ top: 4, right: 4, bottom: 0, left: -16 }}
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
              yAxisId="weekly"
              tick={{ fontSize: 10 }}
              tickLine={false}
              axisLine={false}
              width={36}
              stroke="currentColor"
              className="text-muted-foreground"
              tickFormatter={(v: number) => formatCurrency(v)}
            />
            <YAxis
              yAxisId="cumulative"
              orientation="right"
              tick={{ fontSize: 10 }}
              tickLine={false}
              axisLine={false}
              width={42}
              stroke="currentColor"
              className="text-muted-foreground"
              tickFormatter={(v: number) => formatCurrency(v)}
            />
            <Tooltip
              cursor={{ fill: "rgba(148, 163, 184, 0.08)" }}
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
                const meta = (SEGMENT_META as Record<string, { label: string }>)[
                  name
                ];
                const label =
                  meta?.label ??
                  (name === "cumulative" ? "Cumulative" : name);
                return [formatCurrency(v), label];
              }}
            />
            <Legend
              verticalAlign="top"
              height={20}
              iconType="circle"
              iconSize={8}
              wrapperStyle={{ fontSize: 10, paddingBottom: 4 }}
              formatter={(value) => {
                const meta = (SEGMENT_META as Record<string, { label: string }>)[
                  value
                ];
                return meta?.label ?? (value === "cumulative" ? "Cumulative" : value);
              }}
            />
            {SEGMENT_KEYS.map((key) => (
              <Bar
                key={key}
                yAxisId="weekly"
                dataKey={key}
                stackId="weekly"
                fill={SEGMENT_META[key].color}
                radius={[0, 0, 0, 0]}
              />
            ))}
            <Line
              yAxisId="cumulative"
              type="monotone"
              dataKey="cumulative"
              stroke="#0F172A"
              strokeWidth={2.25}
              dot={false}
              className="dark:[&_path]:stroke-white"
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      <p className="mt-1 text-[11px] text-muted-foreground">
        {series.length} week{series.length === 1 ? "" : "s"} shown ·
        real numbers will flow in once the donation-campaign backend
        ships ({" "}
        <span className="italic">mustr_pitch_deck plan: Donation Campaigns</span>
        ).
      </p>
    </div>
  );
}
