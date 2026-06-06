import { useMemo } from "react";
import {
  Bar,
  BarChart,
  Cell,
  LabelList,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Sparkles, X } from "lucide-react";
import { cn } from "@/lib/utils";
import type { AlertItem } from "../api";
import {
  ALERT_CATEGORY_META,
  type AlertCategory,
  categoriesInGroup,
  categoryFor,
} from "../lib/alert-categories";

/**
 * Heads-up category chart — horizontal bars, one per category in the
 * heads-up group. Real alert counts (currently only walk-ups have a
 * production backend) are blended with a small dummy baseline so the
 * chart looks rich even before the issue-report / token-usage /
 * hallucination feeds are wired. Admins get a preview of the shape
 * of the surface; categories with no real or dummy data still render
 * an empty bar so the legend stays stable.
 *
 * Bars are clickable — picking one drills into a per-category sample
 * list rendered below the chart by the parent dashboard.
 */

const DUMMY_BASELINE: Partial<Record<AlertCategory, number>> = {
  candidate: 2,
  complaint: 3,
  hallucination: 1,
  feedback: 5,
  token_usage: 1,
  issue: 2,
};

/** Sample items per category — shown when the admin clicks a bar so
 *  they can see what the per-category feed will look like once each
 *  source backend is wired. Shape mirrors AlertItem.body / title /
 *  age_seconds — but rendered through a lightweight inline list (no
 *  snooze / dismiss) since these are previews, not real items. */
export interface DummyHeadsUpItem {
  title: string;
  body: string;
  age_seconds: number;
}

export const DUMMY_HEADS_UP_ITEMS: Record<AlertCategory, DummyHeadsUpItem[]> = {
  candidate: [
    {
      title: "Unknown number texted in — '(347) 555-0182'",
      body: "Said: 'hi i'd like to volunteer for the food drive on sat'. Promote to volunteer or dismiss.",
      age_seconds: 12 * 60,
    },
    {
      title: "Unknown number texted in — '(917) 555-2034'",
      body: "Said: 'is sunday gathering still happening?'. Promote or dismiss.",
      age_seconds: 2 * 3600,
    },
  ],
  complaint: [
    {
      title: "Volunteer complaint — Mark R.",
      body: "“The reminder SMS arrived twice this morning.” Reply or dismiss.",
      age_seconds: 8 * 60,
    },
    {
      title: "Volunteer complaint — Anita S.",
      body: "“Asked to switch services but it never got approved.” Open the run sheet.",
      age_seconds: 45 * 60,
    },
    {
      title: "Volunteer complaint — Diego M.",
      body: "“My check-in didn't register and I had to call.” Audit the check-in log.",
      age_seconds: 4 * 3600,
    },
  ],
  hallucination: [
    {
      title: "Thumbs-down on AI reply — booking flow",
      body: "Volunteer flagged the assistant for inventing a time slot that didn't exist. Open conversation to patch the prompt.",
      age_seconds: 35 * 60,
    },
  ],
  feedback: [
    {
      title: "Feedback — Jamie L.",
      body: "“Loved the new check-in flow!” No action required; archive when done.",
      age_seconds: 3 * 3600,
    },
    {
      title: "Feedback — Priya K.",
      body: "“Recurring events showing on the calendar is super helpful.” Archive when ready.",
      age_seconds: 5 * 3600,
    },
    {
      title: "Feedback — Tomás G.",
      body: "“Would love a way to set my availability for full months at once.” Capture for backlog.",
      age_seconds: 9 * 3600,
    },
    {
      title: "Feedback — Lin W.",
      body: "“Daily SMS digest is great, but 6am is too early.” Suggest tuning the schedule.",
      age_seconds: 18 * 3600,
    },
    {
      title: "Feedback — Anonymous",
      body: "“Add Spanish-language reminders please.” Capture for backlog.",
      age_seconds: 26 * 3600,
    },
  ],
  token_usage: [
    {
      title: "Daily token usage spiked +180%",
      body: "Yesterday's Claude bill burned $9.40 vs the trailing 7-day median of $3.30. Most spend came from the recruiter agent on a single tenant. Investigate.",
      age_seconds: 90 * 60,
    },
  ],
  issue: [
    {
      title: "Twilio webhook latency above 3s for 12 min",
      body: "Window started 02:18 UTC; SMS replies queued but didn't drop. Capacity returned to baseline. Confirm no volunteer fell off.",
      age_seconds: 2 * 3600,
    },
    {
      title: "Calendar sync failed for 3 bookings",
      body: "Google Calendar returned 'invalid credentials' for tenant 'mustr-demo' last evening. Reauth required.",
      age_seconds: 8 * 3600,
    },
  ],
  // Decisions-group categories — never displayed by HeadsUpChart, but
  // typed in here so the Record stays exhaustive.
  service_change: [],
  review: [],
  suspension: [],
  at_risk_event: [],
  rule_changed: [],
  urgent_message: [],
};

interface HeadsUpChartProps {
  /** Live alerts the dashboard already loaded; real counts get added
   *  on top of the dummy baseline. */
  alerts: AlertItem[];
  /** Currently picked category (drills the preview list below). */
  selectedCategory: AlertCategory | null;
  onSelectCategory: (cat: AlertCategory | null) => void;
}

export function HeadsUpChart({
  alerts,
  selectedCategory,
  onSelectCategory,
}: HeadsUpChartProps) {
  const data = useMemo(() => {
    const realCounts = new Map<AlertCategory, number>();
    for (const a of alerts) {
      const cat = categoryFor(a);
      realCounts.set(cat, (realCounts.get(cat) ?? 0) + 1);
    }
    return categoriesInGroup("heads_up").map((cat) => {
      const real = realCounts.get(cat) ?? 0;
      const dummy = DUMMY_BASELINE[cat] ?? 0;
      return {
        category: cat,
        label: ALERT_CATEGORY_META[cat].label,
        color: ALERT_CATEGORY_META[cat].color,
        real,
        dummy,
        total: real + dummy,
      };
    });
  }, [alerts]);

  const totalReal = data.reduce((s, d) => s + d.real, 0);
  const totalDummy = data.reduce((s, d) => s + d.dummy, 0);
  const usingDummy = totalDummy > 0;

  function handleClick(_data: unknown, index: number) {
    const cat = data[index]?.category;
    if (!cat) return;
    onSelectCategory(selectedCategory === cat ? null : cat);
  }

  return (
    <div className="rounded-xl border bg-card/50 p-4">
      <div className="mb-3 flex items-baseline justify-between gap-3">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
            Heads-up activity
          </p>
          <h3 className="text-sm font-semibold">
            {selectedCategory
              ? `Showing: ${ALERT_CATEGORY_META[selectedCategory].label}`
              : "What's lingering in your inbox"}
          </h3>
        </div>
        <div className="flex items-center gap-2">
          {selectedCategory && (
            <button
              type="button"
              onClick={() => onSelectCategory(null)}
              className="inline-flex items-center gap-1 rounded-full bg-muted px-2 py-0.5 text-[11px] text-muted-foreground hover:text-foreground"
            >
              <X className="h-3 w-3" />
              Clear
            </button>
          )}
          {usingDummy && (
            <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-medium text-amber-800 dark:bg-amber-950/50 dark:text-amber-300">
              <Sparkles className="h-3 w-3" />
              Preview · dummy data
            </span>
          )}
        </div>
      </div>

      <div className="h-[220px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={data}
            layout="vertical"
            margin={{ top: 4, right: 40, bottom: 4, left: 12 }}
          >
            <XAxis
              type="number"
              tick={{ fontSize: 11 }}
              allowDecimals={false}
              stroke="currentColor"
              className="text-muted-foreground"
            />
            <YAxis
              type="category"
              dataKey="label"
              tick={{ fontSize: 11 }}
              width={140}
              stroke="currentColor"
              className="text-muted-foreground"
            />
            <Tooltip
              cursor={{ fill: "rgba(148, 163, 184, 0.12)" }}
              contentStyle={{
                background: "var(--card)",
                border: "1px solid var(--border)",
                borderRadius: 8,
                fontSize: 12,
                color: "var(--foreground)",
              }}
              labelStyle={{ color: "var(--foreground)", fontWeight: 600 }}
              itemStyle={{ color: "var(--foreground)" }}
              formatter={(value: number, _name, props) => {
                const d = props.payload as {
                  real: number;
                  dummy: number;
                };
                const breakdown =
                  d.real > 0 && d.dummy > 0
                    ? ` (${d.real} live, ${d.dummy} dummy)`
                    : d.real === 0 && d.dummy > 0
                      ? " (dummy)"
                      : "";
                return [`${value}${breakdown}`, "Items"];
              }}
            />
            <Bar
              dataKey="total"
              radius={[0, 4, 4, 0]}
              onClick={handleClick}
              cursor="pointer"
            >
              {data.map((d) => (
                <Cell
                  key={d.category}
                  fill={d.color}
                  fillOpacity={
                    !selectedCategory || selectedCategory === d.category
                      ? 1
                      : 0.25
                  }
                />
              ))}
              <LabelList
                dataKey="total"
                position="right"
                style={{
                  fontSize: 11,
                  fontWeight: 600,
                  fill: "var(--foreground)",
                }}
              />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      <p className="mt-2 text-[11px] text-muted-foreground">
        {totalReal} live item{totalReal === 1 ? "" : "s"} in your inbox
        {usingDummy && (
          <>
            {" · "}
            <span className="italic">
              {totalDummy} preview item{totalDummy === 1 ? "" : "s"} shown
              so you can see what the surface looks like under load
            </span>
          </>
        )}
        . Click a bar to see sample messages.
      </p>
    </div>
  );
}

/** Per-category dummy preview list — shown when the admin clicks a
 *  bar on HeadsUpChart. Plain rendering (no snooze / dismiss) since
 *  the underlying source backends aren't shipped; this is a preview
 *  of the surface, not a real triage queue. */
export function HeadsUpPreviewList({
  category,
}: {
  category: AlertCategory;
}) {
  const meta = ALERT_CATEGORY_META[category];
  const items = DUMMY_HEADS_UP_ITEMS[category] ?? [];
  if (items.length === 0) {
    return (
      <div className="rounded-xl border bg-card/50 p-4 text-center text-sm text-muted-foreground">
        No preview items for {meta.label}.
      </div>
    );
  }
  return (
    <ul className="space-y-2">
      {items.map((it, i) => (
        <li
          key={i}
          className="rounded-xl border bg-card p-3"
          style={{ borderLeft: `4px solid ${meta.color}` }}
        >
          <div className="flex items-baseline justify-between gap-2">
            <p className="text-sm font-semibold leading-tight">{it.title}</p>
            <p className="shrink-0 text-[10px] uppercase tracking-wider text-muted-foreground">
              {humanizeAge(it.age_seconds)}
            </p>
          </div>
          <p className="mt-1 text-xs text-muted-foreground">{it.body}</p>
          <p
            className={cn(
              "mt-1.5 text-[10px] font-medium uppercase tracking-wider",
            )}
            style={{ color: meta.color }}
          >
            {meta.label}
          </p>
        </li>
      ))}
    </ul>
  );
}

function humanizeAge(seconds: number): string {
  if (seconds < 60) return "just now";
  if (seconds < 3600) return `${Math.round(seconds / 60)}m ago`;
  if (seconds < 86_400) return `${Math.round(seconds / 3600)}h ago`;
  return `${Math.round(seconds / 86_400)}d ago`;
}
