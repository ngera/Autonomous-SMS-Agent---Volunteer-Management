import { useMemo, useState } from "react";
import { CalendarDays, X } from "lucide-react";
import { format, parseISO, startOfWeek, addDays, isSameDay } from "date-fns";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import { usePlanning } from "../hooks/use-dashboard";
import type { PlanningEvent } from "../api";
import { CapacityRow, Legend, buildEventRow } from "./capacity-pulse";

/**
 * Planning heatmap — week × day grid of T+15 → T+60. Each cell shows
 * the worst-health event on that day; clicking a cell expands an
 * inline panel below with the full rich-row chart for the events on
 * that date. Replaces the long bar-list when the planning horizon
 * could contain 20+ events.
 *
 * Worst-event-wins color rule:
 *   1. Any event with booked < min_required        → at-risk
 *   2. Any event with fill_pct < 100% (and no #1)  → filling
 *   3. All events fully booked                     → filled
 *   4. No events                                   → empty
 */

type CellState = "at_risk" | "filling" | "filled" | "empty";

const CELL_STYLES: Record<
  CellState,
  { bg: string; ring: string; text: string; legendLabel: string }
> = {
  at_risk: {
    bg: "bg-red-500 hover:bg-red-600",
    ring: "ring-red-300/60 dark:ring-red-900/40",
    text: "text-white",
    legendLabel: "At-risk",
  },
  filling: {
    bg: "bg-amber-400 hover:bg-amber-500",
    ring: "ring-amber-300/60 dark:ring-amber-900/40",
    text: "text-amber-950",
    legendLabel: "Filling",
  },
  filled: {
    bg: "bg-emerald-500 hover:bg-emerald-600",
    ring: "ring-emerald-300/60 dark:ring-emerald-900/40",
    text: "text-white",
    legendLabel: "Filled",
  },
  empty: {
    bg: "bg-muted/40 hover:bg-muted/70",
    ring: "ring-transparent",
    text: "text-muted-foreground/50",
    legendLabel: "Nothing scheduled",
  },
};

function classifyDay(events: PlanningEvent[]): CellState {
  if (events.length === 0) return "empty";
  let bestSeen: CellState = "filled";
  for (const e of events) {
    if (e.booked < e.min_required_total || e.health === "needs_campaign") {
      return "at_risk";
    }
    if (e.fill_pct < 1) bestSeen = "filling";
  }
  return bestSeen;
}

export function PlanningHeatmap() {
  const { data, isLoading } = usePlanning();
  const [selectedDate, setSelectedDate] = useState<string | null>(null);

  const { weeks, eventsByDate } = useMemo(() => {
    const byDate = new Map<string, PlanningEvent[]>();
    for (const e of data ?? []) {
      const list = byDate.get(e.date) ?? [];
      list.push(e);
      byDate.set(e.date, list);
    }

    // Anchor the grid to the Monday of the earliest event week (or
    // today's week if no events). Generate enough weeks to cover the
    // last event date — caps the grid to the data, not a fixed 60 days
    // so the layout breathes correctly for sparse horizons.
    const today = new Date();
    const dates = (data ?? [])
      .map((e) => parseISO(e.date))
      .sort((a, b) => a.getTime() - b.getTime());
    const first = dates[0] ?? today;
    const last = dates[dates.length - 1] ?? today;
    const start = startOfWeek(first, { weekStartsOn: 1 });
    const weeks: Date[][] = [];
    let cursor = start;
    while (cursor <= last) {
      const row: Date[] = [];
      for (let i = 0; i < 7; i++) row.push(addDays(cursor, i));
      weeks.push(row);
      cursor = addDays(cursor, 7);
    }
    return { weeks, eventsByDate: byDate };
  }, [data]);

  if (isLoading) {
    return <Skeleton className="h-[280px] w-full rounded-2xl" />;
  }
  if (!data || data.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed py-10 text-center">
        <CalendarDays className="mb-2 h-7 w-7 text-muted-foreground" />
        <p className="text-sm font-medium">
          No events 15–60 days out
        </p>
        <p className="mt-0.5 text-xs text-muted-foreground">
          Schedule events in Calendar to see them here.
        </p>
      </div>
    );
  }

  const selectedEvents = selectedDate
    ? eventsByDate.get(selectedDate) ?? []
    : [];

  return (
    <div className="space-y-2 rounded-2xl border bg-card px-4 py-3">
      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1">
        <div className="flex items-baseline gap-2">
          <h3 className="text-sm font-semibold">
            {data.length} event{data.length === 1 ? "" : "s"} · {weeks.length}{" "}
            week{weeks.length === 1 ? "" : "s"}
          </h3>
          <p className="text-[11px] text-muted-foreground">
            click a day to see details
          </p>
        </div>
        <HeatmapLegend />
      </div>

      <Grid
        weeks={weeks}
        eventsByDate={eventsByDate}
        selectedDate={selectedDate}
        onSelect={(iso) =>
          setSelectedDate((prev) => (prev === iso ? null : iso))
        }
      />

      {selectedDate && (
        <DayPanel
          isoDate={selectedDate}
          events={selectedEvents}
          onClose={() => setSelectedDate(null)}
        />
      )}
    </div>
  );
}

function HeatmapLegend() {
  const order: CellState[] = ["at_risk", "filling", "filled"];
  return (
    <div className="flex flex-wrap gap-x-3 gap-y-1 text-[10px] text-muted-foreground">
      {order.map((state) => (
        <span key={state} className="inline-flex items-center gap-1">
          <span
            className={cn(
              "h-2.5 w-2.5 rounded-sm",
              CELL_STYLES[state].bg.split(" ")[0],
            )}
          />
          {CELL_STYLES[state].legendLabel}
        </span>
      ))}
    </div>
  );
}

// Single-letter day-of-week labels for the compact left rail.
const DOW_LETTERS = ["M", "T", "W", "T", "F", "S", "S"];

function Grid({
  weeks,
  eventsByDate,
  selectedDate,
  onSelect,
}: {
  weeks: Date[][];
  eventsByDate: Map<string, PlanningEvent[]>;
  selectedDate: string | null;
  onSelect: (iso: string) => void;
}) {
  // GitHub-contributions layout: 7 day-of-week rows, weeks as columns.
  // Fits 9 weeks of a 60-day horizon in ~140px of vertical space, vs
  // the ~450px the rotated weeks-down layout took.
  const monthLabels: Array<{ idx: number; label: string }> = [];
  let lastMonth = -1;
  weeks.forEach((week, idx) => {
    const m = week[0].getMonth();
    if (m !== lastMonth) {
      monthLabels.push({ idx, label: format(week[0], "MMM") });
      lastMonth = m;
    }
  });

  return (
    <TooltipProvider delayDuration={120}>
      <div className="w-full">
        {/* Month label row */}
        <div
          className="grid gap-0.5 pl-8 text-xs font-medium text-muted-foreground"
          style={{
            gridTemplateColumns: `repeat(${weeks.length}, minmax(0, 1fr))`,
          }}
        >
          {weeks.map((week, i) => {
            const lbl = monthLabels.find((m) => m.idx === i);
            return (
              <div key={week[0].toISOString()} className="h-4">
                {lbl ? lbl.label : ""}
              </div>
            );
          })}
        </div>
        {/* DOW labels (left) + cells (right) */}
        <div className="mt-1 flex w-full gap-1.5">
          <div className="flex w-7 flex-col gap-0.5">
            {DOW_LETTERS.map((d, i) => (
              <div
                key={i}
                className="flex h-8 items-center justify-end pr-1 text-xs font-medium text-muted-foreground"
              >
                {i % 2 === 0 ? d : ""}
              </div>
            ))}
          </div>
          <div
            className="grid w-full gap-0.5"
            style={{
              gridTemplateColumns: `repeat(${weeks.length}, minmax(0, 1fr))`,
              gridTemplateRows: "repeat(7, 2rem)",
              gridAutoFlow: "column",
            }}
          >
            {weeks.flatMap((week) =>
              week.map((day) => {
                const iso = format(day, "yyyy-MM-dd");
                const events = eventsByDate.get(iso) ?? [];
                const state = classifyDay(events);
                const isSelected = selectedDate === iso;
                const isToday = isSameDay(day, new Date());
                return (
                  <HeatmapCell
                    key={iso}
                    day={day}
                    iso={iso}
                    events={events}
                    state={state}
                    isSelected={isSelected}
                    isToday={isToday}
                    onSelect={onSelect}
                  />
                );
              }),
            )}
          </div>
        </div>
      </div>
    </TooltipProvider>
  );
}

function HeatmapCell({
  day,
  iso,
  events,
  state,
  isSelected,
  isToday,
  onSelect,
}: {
  day: Date;
  iso: string;
  events: PlanningEvent[];
  state: CellState;
  isSelected: boolean;
  isToday: boolean;
  onSelect: (iso: string) => void;
}) {
  const styles = CELL_STYLES[state];
  const disabled = state === "empty";
  const button = (
    <button
      type="button"
      disabled={disabled}
      onClick={() => onSelect(iso)}
      aria-label={`${format(day, "EEE MMM d")} — ${events.length} event${events.length === 1 ? "" : "s"}`}
      className={cn(
        "relative flex h-full w-full flex-col items-center justify-center rounded-[4px] ring-1 transition-all",
        styles.bg,
        styles.ring,
        styles.text,
        disabled ? "cursor-default" : "cursor-pointer",
        isSelected &&
          "outline outline-2 outline-offset-1 outline-foreground/70",
        isToday && !isSelected && "outline outline-1 outline-foreground/30",
      )}
    >
      <span className="text-[11px] font-medium leading-none opacity-80">
        {format(day, "d")}
      </span>
      {events.length > 0 && (
        <span className="mt-0.5 text-[11px] font-bold leading-none tabular-nums">
          {events.reduce((sum, e) => sum + e.booked, 0)}/
          {events.reduce((sum, e) => sum + e.capacity, 0)}
        </span>
      )}
    </button>
  );

  if (events.length === 0) return button;

  return (
    <Tooltip>
      <TooltipTrigger asChild>{button}</TooltipTrigger>
      <TooltipContent className="max-w-[240px] space-y-1 p-2">
        <p className="text-[11px] font-semibold">
          {format(day, "EEE, MMM d")}
        </p>
        {events.slice(0, 4).map((e) => (
          <div
            key={e.slot_id}
            className="flex items-center justify-between gap-2 text-[11px]"
          >
            <span className="truncate">{e.label}</span>
            <span
              className={cn(
                "tabular-nums",
                e.booked < e.min_required_total && "text-red-300",
              )}
            >
              {e.booked}/{e.capacity}
            </span>
          </div>
        ))}
        {events.length > 4 && (
          <p className="text-[10px] text-muted-foreground">
            + {events.length - 4} more — click to expand
          </p>
        )}
      </TooltipContent>
    </Tooltip>
  );
}

function DayPanel({
  isoDate,
  events,
  onClose,
}: {
  isoDate: string;
  events: PlanningEvent[];
  onClose: () => void;
}) {
  const dateLabel = (() => {
    try {
      return format(parseISO(isoDate), "EEEE, MMMM d");
    } catch {
      return isoDate;
    }
  })();
  const rows = useMemo(() => events.map(buildEventRow), [events]);
  const globalMax = useMemo(
    () => Math.max(1, ...rows.map((r) => r.max)),
    [rows],
  );

  return (
    <div className="rounded-xl border bg-muted/30 p-3">
      <div className="mb-2 flex items-baseline justify-between">
        <p className="text-sm font-semibold">{dateLabel}</p>
        <button
          type="button"
          onClick={onClose}
          className="inline-flex items-center gap-1 text-[11px] text-muted-foreground hover:text-foreground"
        >
          <X className="h-3 w-3" />
          Close
        </button>
      </div>
      <Legend />
      <div className="mt-2 space-y-2">
        {rows.map((r) => (
          <CapacityRow
            key={r.event.slot_id}
            row={r}
            globalMax={globalMax}
          />
        ))}
      </div>
    </div>
  );
}
