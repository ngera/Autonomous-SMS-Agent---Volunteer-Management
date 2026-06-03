import { useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { CalendarDays, ChevronRight, MapPin } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { useWeeklySlotStatuses } from "../hooks/use-dashboard";
import { aggregateBySchedule, fillPercent, type AggregatedEvent } from "../lib/aggregate";

const DAY_LABELS: Record<string, string> = {
  Monday: "Mon",
  Tuesday: "Tue",
  Wednesday: "Wed",
  Thursday: "Thu",
  Friday: "Fri",
  Saturday: "Sat",
  Sunday: "Sun",
};

function bucketFor(event: AggregatedEvent, today: Date) {
  const eventDate = new Date(`${event.date}T00:00:00`);
  const diff = Math.round(
    (eventDate.getTime() - new Date(today.toDateString()).getTime()) /
      (1000 * 60 * 60 * 24),
  );
  if (diff <= 0) return "Today";
  if (diff === 1) return "Tomorrow";
  return "Rest of week";
}

function statusTint(pct: number): {
  ring: string;
  bar: string;
  label: string;
  tone: string;
} {
  if (pct >= 1) {
    return {
      ring: "ring-emerald-200/70 dark:ring-emerald-900/40",
      bar: "bg-emerald-500",
      label: "Filled",
      tone: "text-emerald-700 dark:text-emerald-300",
    };
  }
  if (pct >= 0.6) {
    return {
      ring: "ring-sky-200/70 dark:ring-sky-900/40",
      bar: "bg-sky-500",
      label: "Filling",
      tone: "text-sky-700 dark:text-sky-300",
    };
  }
  return {
    ring: "ring-amber-200/70 dark:ring-amber-900/40",
    bar: "bg-amber-500",
    label: "Under-filled",
    tone: "text-amber-700 dark:text-amber-300",
  };
}

export function ThisWeekStrip() {
  const navigate = useNavigate();
  const { data, isLoading } = useWeeklySlotStatuses(0);

  const events = useMemo(
    () => aggregateBySchedule(data ?? []),
    [data],
  );

  const buckets = useMemo(() => {
    const today = new Date();
    const groups: Record<"Today" | "Tomorrow" | "Rest of week", AggregatedEvent[]> = {
      Today: [],
      Tomorrow: [],
      "Rest of week": [],
    };
    for (const e of events) {
      const b = bucketFor(e, today);
      (groups as Record<string, AggregatedEvent[]>)[b].push(e);
    }
    return groups;
  }, [events]);

  if (isLoading) {
    return (
      <div className="space-y-2">
        <Skeleton className="h-32 w-full rounded-2xl" />
      </div>
    );
  }

  if (events.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed py-8 text-center">
        <CalendarDays className="mb-2 h-7 w-7 text-muted-foreground" />
        <p className="text-sm font-medium">No events this week</p>
        <p className="mt-0.5 text-xs text-muted-foreground">
          Schedule something in Calendar to see it here.
        </p>
      </div>
    );
  }

  return (
    <div className="grid gap-4 lg:grid-cols-3">
      {(["Today", "Tomorrow", "Rest of week"] as const).map((bucket) => (
        <BucketColumn
          key={bucket}
          label={bucket}
          events={buckets[bucket]}
          onOpen={(e) =>
            navigate(
              e.source === "one_time" && e.source_id
                ? `/events/specific/${e.source_id}`
                : `/bookings?date=${e.date}`,
            )
          }
        />
      ))}
    </div>
  );
}

interface BucketColumnProps {
  label: string;
  events: AggregatedEvent[];
  onOpen: (e: AggregatedEvent) => void;
}

function BucketColumn({ label, events, onOpen }: BucketColumnProps) {
  return (
    <section>
      <div className="mb-2 flex items-center gap-2">
        <h3 className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
          {label}
        </h3>
        <span className="text-[11px] text-muted-foreground">
          {events.length}
        </span>
        <div className="h-px flex-1 bg-border" />
      </div>
      {events.length === 0 ? (
        <p className="rounded-xl border border-dashed bg-muted/30 px-3 py-4 text-center text-xs text-muted-foreground">
          Nothing scheduled
        </p>
      ) : (
        <div className="space-y-2">
          {events.slice(0, 6).map((e) => {
            const pct = fillPercent(e.booked, e.max_allowed);
            const tint = statusTint(pct);
            return (
              <button
                key={e.key}
                type="button"
                onClick={() => onOpen(e)}
                className={cn(
                  "group block w-full rounded-xl bg-card px-3 py-2.5 text-left ring-1 transition-all",
                  "hover:shadow-md hover:-translate-y-px",
                  tint.ring,
                )}
              >
                <div className="flex items-baseline gap-2">
                  <p className="truncate text-sm font-semibold">
                    {e.display_name}
                  </p>
                  <span className="ml-auto shrink-0 text-[11px] text-muted-foreground">
                    {DAY_LABELS[e.day_name] ?? e.day_name} · {e.window_time}
                  </span>
                </div>
                <div className="mt-1 flex items-center gap-1.5 text-[11px] text-muted-foreground">
                  {e.location && (
                    <span className="inline-flex items-center gap-0.5">
                      <MapPin className="h-3 w-3" />
                      {e.location}
                    </span>
                  )}
                  <span className={cn("ml-auto font-medium", tint.tone)}>
                    {tint.label}
                  </span>
                </div>
                {/* Fill bar */}
                <div className="mt-2 flex items-center gap-2">
                  <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
                    <div
                      className={cn(
                        "h-full rounded-full transition-all",
                        tint.bar,
                      )}
                      style={{ width: `${Math.min(100, pct * 100)}%` }}
                    />
                  </div>
                  <span className="shrink-0 text-[11px] font-medium tabular-nums">
                    {e.booked}/{e.max_allowed}
                  </span>
                  <ChevronRight className="h-3.5 w-3.5 shrink-0 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100" />
                </div>
              </button>
            );
          })}
          {events.length > 6 && (
            <p className="px-2 text-center text-[11px] text-muted-foreground">
              +{events.length - 6} more
            </p>
          )}
        </div>
      )}
    </section>
  );
}
