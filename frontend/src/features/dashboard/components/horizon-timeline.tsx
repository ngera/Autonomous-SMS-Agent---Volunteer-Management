import { useMemo } from "react";
import { CalendarDays } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import type { PlanningEvent } from "../api";
import { usePlanning } from "../hooks/use-dashboard";
import { EventCard } from "./event-card";

// Planning starts at T+15, so only the two beyond-operational buckets
// are relevant here. The `this_week` and `week_2` buckets exist in the
// API for the Capacity Pulse on Needs-You-Now.
const BUCKET_LABELS: Record<
  "weeks_3_4" | "month_2",
  { label: string; sub: string }
> = {
  weeks_3_4: { label: "Weeks 3–4", sub: "15–28 days out" },
  month_2: { label: "Month 2", sub: "29–60 days out" },
};
const PLANNING_BUCKETS = ["weeks_3_4", "month_2"] as const;

export function HorizonTimeline() {
  const { data, isLoading } = usePlanning();

  const buckets = useMemo(() => {
    const groups: Record<"weeks_3_4" | "month_2", PlanningEvent[]> = {
      weeks_3_4: [],
      month_2: [],
    };
    for (const e of data ?? []) {
      if (e.bucket === "weeks_3_4" || e.bucket === "month_2") {
        groups[e.bucket].push(e);
      }
    }
    return groups;
  }, [data]);

  if (isLoading) {
    return (
      <div className="grid gap-4 lg:grid-cols-2">
        <Skeleton className="h-64 rounded-2xl" />
        <Skeleton className="h-64 rounded-2xl" />
      </div>
    );
  }

  if (!data || data.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed py-10 text-center">
        <CalendarDays className="mb-2 h-8 w-8 text-muted-foreground" />
        <p className="text-sm font-medium">No events in the next 60 days</p>
        <p className="mt-1 max-w-sm text-xs text-muted-foreground">
          Schedule an event on the Calendar to see it here, and the
          recommendations engine will surface campaign suggestions
          automatically.
        </p>
      </div>
    );
  }

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      {PLANNING_BUCKETS.map((bucket) => (
        <BucketColumn
          key={bucket}
          bucket={bucket}
          events={buckets[bucket]}
        />
      ))}
    </div>
  );
}

interface BucketColumnProps {
  bucket: "weeks_3_4" | "month_2";
  events: PlanningEvent[];
}

function BucketColumn({ bucket, events }: BucketColumnProps) {
  const meta = BUCKET_LABELS[bucket];
  return (
    <section className="rounded-2xl border bg-card/50 p-3">
      <header className="mb-3 px-1">
        <div className="flex items-baseline gap-2">
          <h3 className="text-sm font-semibold">{meta.label}</h3>
          <span className="text-[11px] text-muted-foreground">
            {events.length}
          </span>
        </div>
        <p className="text-[11px] text-muted-foreground">{meta.sub}</p>
      </header>
      {events.length === 0 ? (
        <p className="rounded-xl border border-dashed bg-muted/30 px-3 py-6 text-center text-xs text-muted-foreground">
          Nothing scheduled in this window
        </p>
      ) : (
        <div className="space-y-2">
          {events.map((e) => (
            <EventCard key={e.slot_id} variant="planning" event={e} />
          ))}
        </div>
      )}
    </section>
  );
}
