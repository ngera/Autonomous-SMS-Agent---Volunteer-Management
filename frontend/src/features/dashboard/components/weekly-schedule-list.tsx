import { format, parseISO } from "date-fns";
import { Bell, Megaphone } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { cn, formatTimeAgo } from "@/lib/utils";
import { fillPercent, fillTone, type AggregatedEvent } from "../lib/aggregate";

interface WeeklyScheduleListProps {
  events: AggregatedEvent[];
  isLoading: boolean;
}

const TONE_BAR: Record<"green" | "amber" | "red", string> = {
  green: "bg-emerald-500",
  amber: "bg-amber-500",
  red: "bg-rose-500",
};

const TONE_TEXT: Record<"green" | "amber" | "red", string> = {
  green: "text-emerald-600",
  amber: "text-amber-600",
  red: "text-rose-600",
};

function DateBadge({
  date,
  isOneTime,
}: {
  date: string;
  isOneTime: boolean;
}) {
  const parsed = parseISO(date);
  const day = format(parsed, "EEE").toLowerCase();
  const md = format(parsed, "M/d");
  return (
    <div
      className={cn(
        "flex w-12 flex-col items-center justify-center rounded-md py-1.5 text-center",
        isOneTime
          ? "bg-amber-50 text-amber-900 dark:bg-amber-950/40 dark:text-amber-200"
          : "bg-muted text-muted-foreground"
      )}
    >
      <span className="text-[10px] font-medium uppercase">{day}</span>
      <span className="text-sm font-semibold leading-tight">{md}</span>
    </div>
  );
}

function EventRow({ ev }: { ev: AggregatedEvent }) {
  const pct = fillPercent(ev.booked, ev.max_allowed);
  const tone = fillTone(pct);

  const subline = [
    ev.window_time,
    ev.location,
    ev.source === "recurring" ? "weekly" : null,
  ]
    .filter(Boolean)
    .join(" · ");

  return (
    <div className="flex items-start gap-4 py-3">
      <DateBadge date={ev.date} isOneTime={ev.source === "one_time"} />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <p className="truncate font-medium">{ev.display_name}</p>
          {ev.source === "one_time" && (
            <Badge
              variant="secondary"
              className="bg-amber-100 text-amber-900 hover:bg-amber-100 dark:bg-amber-950/60 dark:text-amber-200"
            >
              one-time
            </Badge>
          )}
        </div>
        {subline && (
          <p className="truncate text-xs text-muted-foreground">{subline}</p>
        )}
        {(ev.last_reminder_sent || ev.last_announcement_sent) && (
          <div className="mt-1 flex flex-wrap items-center gap-1.5">
            {ev.last_reminder_sent && (
              <span className="inline-flex items-center gap-1 rounded-full bg-muted px-2 py-0.5 text-[10px] text-muted-foreground">
                <Bell className="h-3 w-3" />
                Reminder {formatTimeAgo(ev.last_reminder_sent)}
              </span>
            )}
            {ev.last_announcement_sent && (
              <span className="inline-flex items-center gap-1 rounded-full bg-muted px-2 py-0.5 text-[10px] text-muted-foreground">
                <Megaphone className="h-3 w-3" />
                Announcement {formatTimeAgo(ev.last_announcement_sent)}
              </span>
            )}
          </div>
        )}
      </div>
      <div className="flex w-40 flex-col items-end gap-1.5">
        <span className={cn("text-sm font-medium tabular-nums", TONE_TEXT[tone])}>
          {ev.booked} / {ev.max_allowed}
        </span>
        <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
          <div
            className={cn("h-full rounded-full", TONE_BAR[tone])}
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>
    </div>
  );
}

export function WeeklyScheduleList({
  events,
  isLoading,
}: WeeklyScheduleListProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>This week's schedule</CardTitle>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="space-y-3">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-12 w-full" />
            ))}
          </div>
        ) : events.length === 0 ? (
          <p className="py-8 text-center text-sm text-muted-foreground">
            No events scheduled this week.
          </p>
        ) : (
          <div className="divide-y">
            {events.map((ev) => (
              <EventRow key={ev.key} ev={ev} />
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
