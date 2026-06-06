import { useMemo } from "react";
import {
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { useAlerts } from "../hooks/use-dashboard";
import { useAlertState } from "../lib/alert-state";
import {
  ALERT_CATEGORY_META,
  type AlertCategory,
  type AlertCategoryCount,
  categoriesInGroup,
  categoryFor,
  countByCategory,
  groupForCategory,
} from "../lib/alert-categories";

interface AlertsDonutProps {
  /** Currently selected category — for filtering the alerts feed below.
   *  null means "all". */
  selected: AlertCategory | null;
  onSelect: (category: AlertCategory | null) => void;
}

export function AlertsDonut({ selected, onSelect }: AlertsDonutProps) {
  const { data: alerts, isLoading } = useAlerts();
  const state = useAlertState();

  // Filter out locally-suppressed alerts so the chart matches the feed.
  // Heads-up categories are intentionally excluded — those live in their
  // own dashboard section now; this donut is the Decisions slice only.
  const visible = useMemo(() => {
    if (!alerts) return [];
    const now = Date.now();
    return alerts.filter((a) => {
      const sn = state.snoozedUntil(a.id);
      if (sn && sn > now) return false;
      if (state.dismissedRecord(a.id)) return false;
      if (groupForCategory(categoryFor(a)) !== "decisions") return false;
      return true;
    });
  }, [alerts, state]);

  // Restrict the legend to Decisions categories only so the empty
  // heads-up rows don't pad the panel.
  const decisionCategories = useMemo(
    () => new Set<AlertCategory>(categoriesInGroup("decisions")),
    [],
  );
  const data = useMemo(
    () =>
      countByCategory(visible).filter((d) =>
        decisionCategories.has(d.category),
      ),
    [visible, decisionCategories],
  );
  const total = useMemo(
    () => data.reduce((sum, d) => sum + d.count, 0),
    [data],
  );
  // Only feed non-zero categories to recharts so the donut isn't littered
  // with empty slices.
  const nonZero = data.filter((d) => d.count > 0);

  if (isLoading) {
    return (
      <Skeleton className="h-[260px] w-full rounded-2xl" />
    );
  }

  return (
    <div className="rounded-2xl border bg-card p-4">
      <div className="mb-3 flex items-baseline justify-between">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
            Decisions by category
          </p>
          <h3 className="text-sm font-semibold">Alerts breakdown</h3>
        </div>
        {selected && (
          <button
            type="button"
            onClick={() => onSelect(null)}
            className="text-[11px] text-muted-foreground hover:text-foreground hover:underline"
          >
            Clear filter
          </button>
        )}
      </div>

      <div className="grid grid-cols-5 items-center gap-3">
        {/* Donut + center total — span 2 cols */}
        <div className="relative col-span-2 h-[180px]">
          {nonZero.length === 0 ? (
            <div className="flex h-full items-center justify-center rounded-full bg-emerald-50/60 ring-1 ring-emerald-200 dark:bg-emerald-950/20 dark:ring-emerald-900/40">
              <div className="text-center">
                <p className="text-2xl font-bold tabular-nums text-emerald-700 dark:text-emerald-300">
                  0
                </p>
                <p className="text-[10px] uppercase tracking-wider text-emerald-700/80 dark:text-emerald-300/80">
                  all clear
                </p>
              </div>
            </div>
          ) : (
            <>
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={nonZero}
                    dataKey="count"
                    nameKey="label"
                    cx="50%"
                    cy="50%"
                    innerRadius={48}
                    outerRadius={75}
                    paddingAngle={1.5}
                    strokeWidth={2}
                    stroke="var(--card)"
                    onClick={(payload) => {
                      const d = payload as unknown as AlertCategoryCount;
                      if (selected === d.category) onSelect(null);
                      else onSelect(d.category);
                    }}
                  >
                    {nonZero.map((entry) => (
                      <Cell
                        key={entry.category}
                        fill={entry.color}
                        fillOpacity={
                          !selected || selected === entry.category ? 1 : 0.25
                        }
                        cursor="pointer"
                      />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "var(--popover)",
                      border: "1px solid var(--border)",
                      borderRadius: 6,
                      color: "var(--popover-foreground)",
                      fontSize: 12,
                    }}
                    labelStyle={{ color: "var(--popover-foreground)" }}
                    itemStyle={{ color: "var(--popover-foreground)" }}
                  />
                </PieChart>
              </ResponsiveContainer>
              {/* Center label — total */}
              <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
                <p className="text-2xl font-bold tabular-nums text-foreground">
                  {total}
                </p>
                <p className="text-[10px] uppercase tracking-wider text-muted-foreground">
                  alerts
                </p>
              </div>
            </>
          )}
        </div>

        {/* Legend — span 3 cols */}
        <div className="col-span-3 space-y-1">
          {data.map((d) => {
            const active = selected === d.category;
            const dimmed = selected !== null && !active;
            return (
              <button
                key={d.category}
                type="button"
                onClick={() => onSelect(active ? null : d.category)}
                disabled={d.count === 0}
                className={cn(
                  "flex w-full items-center gap-2 rounded-md px-2 py-1 text-left transition-colors",
                  "disabled:cursor-default disabled:opacity-50",
                  active && "bg-muted",
                  !active &&
                    d.count > 0 &&
                    "hover:bg-muted/60",
                  dimmed && "opacity-50",
                )}
              >
                <span
                  className="h-2.5 w-2.5 shrink-0 rounded-full"
                  style={{ backgroundColor: d.color }}
                />
                <span className="flex-1 truncate text-xs">{d.label}</span>
                <span
                  className={cn(
                    "tabular-nums text-xs font-semibold",
                    d.count === 0
                      ? "text-muted-foreground"
                      : "text-foreground",
                  )}
                >
                  {d.count}
                </span>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}

/** Helper for parent: filter an alerts list by the donut's selected category. */
export function filterAlertsByCategory(
  alerts: { source: string }[],
  selected: AlertCategory | null,
): typeof alerts {
  if (!selected) return alerts;
  return alerts.filter((a) => categoryFor(a as never) === selected);
}

export { ALERT_CATEGORY_META };
