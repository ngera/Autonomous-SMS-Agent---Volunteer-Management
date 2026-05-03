import { format, parseISO } from "date-fns";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { fillPercent, fillTone, type AggregatedEvent } from "../lib/aggregate";

interface UpcomingOneTimeEventsProps {
  events: AggregatedEvent[];
  isLoading: boolean;
}

const TONE_BAR: Record<"green" | "amber" | "red", string> = {
  green: "bg-emerald-500",
  amber: "bg-amber-500",
  red: "bg-rose-500",
};

const TONE_PILL: Record<"green" | "amber" | "red", { label: string; cls: string }> = {
  green: {
    label: "on track",
    cls: "bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300",
  },
  amber: {
    label: "filling",
    cls: "bg-amber-100 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300",
  },
  red: {
    label: "low",
    cls: "bg-rose-100 text-rose-800 dark:bg-rose-950/60 dark:text-rose-300",
  },
};

function daysAway(date: string): string {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const target = parseISO(date);
  const diff = Math.round((target.getTime() - today.getTime()) / 86_400_000);
  if (diff === 0) return "today";
  if (diff === 1) return "tomorrow";
  return `${diff} days away`;
}

export function UpcomingOneTimeEvents({
  events,
  isLoading,
}: UpcomingOneTimeEventsProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Upcoming one-time events</CardTitle>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="space-y-3">
            {Array.from({ length: 2 }).map((_, i) => (
              <Skeleton key={i} className="h-12 w-full" />
            ))}
          </div>
        ) : events.length === 0 ? (
          <p className="py-8 text-center text-sm text-muted-foreground">
            No one-time events scheduled in the next 7 days.
          </p>
        ) : (
          <div className="space-y-4">
            {events.map((ev) => {
              const pct = fillPercent(ev.booked, ev.max_allowed);
              const tone = fillTone(pct);
              const pill = TONE_PILL[tone];
              return (
                <div key={ev.key} className="space-y-1.5">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="truncate font-medium">{ev.display_name}</p>
                      <p className="truncate text-xs text-muted-foreground">
                        {format(parseISO(ev.date), "MMM d")} · {daysAway(ev.date)}
                      </p>
                    </div>
                    <span
                      className={cn(
                        "shrink-0 rounded-full px-2 py-0.5 text-xs font-medium",
                        pill.cls
                      )}
                    >
                      {pill.label}
                    </span>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
                      <div
                        className={cn("h-full rounded-full", TONE_BAR[tone])}
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                    <span className="w-16 text-right text-xs tabular-nums text-muted-foreground">
                      {ev.booked} / {ev.max_allowed}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
