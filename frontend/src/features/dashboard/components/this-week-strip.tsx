import { useMemo } from "react";
import { CalendarDays } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { useWeeklySlotStatuses } from "../hooks/use-dashboard";
import { aggregateBySchedule, type AggregatedEvent } from "../lib/aggregate";
import { EventCard } from "./event-card";

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

export function ThisWeekStrip() {
  const { data, isLoading } = useWeeklySlotStatuses(0);

  const events = useMemo(
    () => aggregateBySchedule(data ?? []),
    [data],
  );

  const buckets = useMemo(() => {
    const today = new Date();
    const groups: Record<
      "Today" | "Tomorrow" | "Rest of week",
      AggregatedEvent[]
    > = {
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
    return <Skeleton className="h-32 w-full rounded-2xl" />;
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
    <div className="grid gap-3 lg:grid-cols-3">
      {(["Today", "Tomorrow", "Rest of week"] as const).map((bucket) => (
        <BucketColumn
          key={bucket}
          label={bucket}
          events={buckets[bucket]}
        />
      ))}
    </div>
  );
}

function BucketColumn({
  label,
  events,
}: {
  label: string;
  events: AggregatedEvent[];
}) {
  return (
    <section className="space-y-2">
      <div className="flex items-center gap-2">
        <h3 className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
          {label}
        </h3>
        <span className="text-[10px] text-muted-foreground">
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
          {events.slice(0, 5).map((e) => (
            <EventCard key={e.key} variant="weekly" event={e} />
          ))}
          {events.length > 5 && (
            <p className="px-2 text-center text-[11px] text-muted-foreground">
              +{events.length - 5} more
            </p>
          )}
        </div>
      )}
    </section>
  );
}
