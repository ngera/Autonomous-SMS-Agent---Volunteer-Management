import { useMemo, useState } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { HandCoins, Megaphone, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/**
 * Registered donors by type — stacked area preview, mirroring the
 * shape of VolunteerHealthChart so the two read as a coherent pair on
 * the Org Health tab. Tracks the running active count of donors in
 * each segment (Individual, Recurring, Corporate, Major) over time.
 *
 * Dummy data via a seeded PRNG until the donor-management backend
 * ships. Replace `generateDummySeries()` with the real hook then.
 */

interface DonorPoint {
  week: string;
  date: Date;
  individual: number;
  recurring: number;
  corporate: number;
  major: number;
  total: number;
}

type Range = "ytd" | "1y" | "2y" | "3y";

const RANGE_OPTIONS: { value: Range; label: string }[] = [
  { value: "ytd", label: "YTD" },
  { value: "1y", label: "1Y" },
  { value: "2y", label: "2Y" },
  { value: "3y", label: "3Y" },
];

const SEGMENT_META = {
  individual: { label: "Individual", color: "#F43F5E" }, // rose-500
  recurring: { label: "Recurring", color: "#8B5CF6" }, // violet-500
  corporate: { label: "Corporate", color: "#0EA5E9" }, // sky-500
  major: { label: "Major", color: "#10B981" }, // emerald-500
} as const;
const SEGMENT_KEYS = ["individual", "recurring", "corporate", "major"] as const;

function generateDummySeries(): DonorPoint[] {
  const out: DonorPoint[] = [];
  const today = new Date();
  const start = new Date(today);
  start.setDate(today.getDate() - 7 * 156);
  let seed = 0xd0d0d5; // arbitrary donor-themed seed
  const rand = () => {
    seed |= 0;
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
  // Running totals — accumulating headcount. Each segment grows at
  // its own pace; recurring catches up over time as the org runs
  // appeals; major is rare but ratchets up with each big-gift week.
  let individual = 45;
  let recurring = 8;
  let corporate = 3;
  let major = 1;
  for (let i = 0; i < 156; i++) {
    const d = new Date(start);
    d.setDate(start.getDate() + 7 * i);
    // Individual donors trickle in faster around the Nov/Dec window.
    const seasonalNudge = Math.max(
      0,
      Math.sin(((d.getMonth() - 9) / 12) * Math.PI * 2),
    );
    individual += Math.round(1.2 + seasonalNudge * 2.5 + (rand() - 0.5) * 1.5);
    // Recurring conversion accelerates as awareness builds.
    recurring += Math.round(0.4 + Math.pow(i, 0.4) * 0.05 + (rand() - 0.2) * 0.5);
    // Corporate sponsorships add ~1 every couple months.
    if (i % 8 === 0) corporate += Math.round(1 + rand() * 1);
    // Major donors land in lumpy batches.
    if (i > 0 && i % 22 === 0) major += Math.round(1 + rand() * 1);
    const total = individual + recurring + corporate + major;
    out.push({
      week: `${d.toLocaleString(undefined, { month: "short" })} ${d.getDate()}`,
      date: d,
      individual,
      recurring,
      corporate,
      major,
      total,
    });
  }
  return out;
}

function filterSeries(series: DonorPoint[], range: Range): DonorPoint[] {
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

export function DonorsChart() {
  const [range, setRange] = useState<Range>("1y");
  const allSeries = useMemo(generateDummySeries, []);
  const series = useMemo(
    () => filterSeries(allSeries, range),
    [allSeries, range],
  );

  // Latest snapshot in the visible range — what the stat tiles show.
  const latest = series[series.length - 1];
  const first = series[0];
  const totalNow = latest?.total ?? 0;
  const totalThen = first?.total ?? 0;
  const netGrowth = totalNow - totalThen;

  return (
    <div className="rounded-2xl border bg-card p-4">
      <div className="mb-2 flex items-baseline justify-between gap-3">
        <div className="flex items-center gap-2">
          <div className="flex h-6 w-6 items-center justify-center rounded-md bg-emerald-100 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-300">
            <HandCoins className="h-3.5 w-3.5" />
          </div>
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
              Registered donors
            </p>
            <h3 className="text-sm font-semibold">
              Donor base by type
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

      <div className="mb-2 grid grid-cols-4 gap-2 text-xs">
        {SEGMENT_KEYS.map((key) => (
          <Stat
            key={key}
            label={SEGMENT_META[key].label}
            value={latest?.[key] ?? 0}
            color={SEGMENT_META[key].color}
          />
        ))}
      </div>
      <p
        className={cn(
          "mb-2 text-xs font-medium tabular-nums",
          netGrowth >= 0
            ? "text-emerald-600 dark:text-emerald-400"
            : "text-rose-600 dark:text-rose-400",
        )}
      >
        {totalNow} active donors · {netGrowth >= 0 ? "+" : ""}
        {netGrowth} since {first?.week ?? "—"}
      </p>

      <div className="h-[200px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart
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
                  (SEGMENT_META as Record<string, { label: string }>)[name];
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
                  (SEGMENT_META as Record<string, { label: string }>)[value];
                return meta?.label ?? value;
              }}
            />
            {SEGMENT_KEYS.map((key) => (
              <Area
                key={key}
                type="monotone"
                dataKey={key}
                stackId="donors"
                stroke={SEGMENT_META[key].color}
                fill={SEGMENT_META[key].color}
                fillOpacity={0.55}
              />
            ))}
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {/* Dummy CTA — wires up once the Fundraising Campaign backend
          lands. Drives donor outreach (awareness + appeals); distinct
          from Musters and Recruiting Campaigns. */}
      <div className="mt-3 flex items-center justify-between gap-2">
        <Button size="sm" variant="default" className="gap-1" disabled>
          <Megaphone className="h-3.5 w-3.5" />
          Start Marketing Campaign
        </Button>
        <span className="text-[10px] uppercase tracking-wider text-muted-foreground">
          Preview · not yet wired
        </span>
      </div>

      <p className="mt-2 text-[11px] text-muted-foreground">
        {series.length} week{series.length === 1 ? "" : "s"} shown · real
        numbers will flow in once the donor-management backend lands.
      </p>
    </div>
  );
}

function Stat({
  label,
  value,
  color,
}: {
  label: string;
  value: number;
  color: string;
}) {
  return (
    <div className="rounded-md border bg-card/50 px-2 py-1.5">
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
