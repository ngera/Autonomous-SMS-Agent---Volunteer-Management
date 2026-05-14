import { format, parseISO } from "date-fns";
import { Bell, EyeOff, Megaphone } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { cn, formatTimeAgo } from "@/lib/utils";
import { MapsLink } from "@/components/shared/maps-link";
import {
  fillPercent,
  fillTone,
  type AggregatedEvent,
  type AggregatedService,
} from "../lib/aggregate";
import type { RosterEntry } from "@/types/api";

interface WeeklyScheduleListProps {
  events: AggregatedEvent[];
  isLoading: boolean;
  onSendAnnouncement?: (ev: AggregatedEvent) => void;
  onSendReminder?: (ev: AggregatedEvent) => void;
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

function rosterDisplayName(entry: RosterEntry): string {
  const display = (entry.name || "").trim() || entry.phone;
  if (entry.visibility === "first_name") {
    return display.split(" ")[0] || display;
  }
  return display;
}

function ServiceBreakdown({ svc }: { svc: AggregatedService }) {
  const visible: string[] = [];
  let hiddenCount = 0;
  for (const r of svc.roster) {
    if (r.visibility === "hidden") {
      hiddenCount++;
    } else {
      visible.push(rosterDisplayName(r));
    }
  }
  return (
    <div className="space-y-1">
      <div className="flex items-baseline justify-between gap-2 text-xs">
        <span className="font-medium">{svc.service_name}</span>
        <span className="tabular-nums text-muted-foreground">
          {svc.booked} / {svc.max_allowed} (min {svc.min_required})
        </span>
      </div>
      {svc.roster.length === 0 ? (
        <p className="pl-2 text-[11px] italic text-muted-foreground">
          no signups yet
        </p>
      ) : (
        <ul className="space-y-0.5 pl-2 text-[11px] text-muted-foreground">
          {visible.map((n, i) => (
            <li key={i}>{n}</li>
          ))}
          {hiddenCount > 0 && (
            <li className="flex items-center gap-1 italic">
              <EyeOff className="h-3 w-3" /> {hiddenCount} hidden
            </li>
          )}
        </ul>
      )}
    </div>
  );
}

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

function EventRow({
  ev,
  onSendAnnouncement,
  onSendReminder,
}: {
  ev: AggregatedEvent;
  onSendAnnouncement?: (ev: AggregatedEvent) => void;
  onSendReminder?: (ev: AggregatedEvent) => void;
}) {
  const navigate = useNavigate();
  const pct = fillPercent(ev.booked, ev.max_allowed);
  const tone = fillTone(pct);

  const subline = [
    ev.window_time,
    ev.location,
    ev.source === "recurring" ? "weekly" : null,
  ]
    .filter(Boolean)
    .join(" · ");

  const route = ev.source_id
    ? ev.source === "one_time"
      ? `/events/specific/${ev.source_id}`
      : `/events/rule/${ev.source_id}/${ev.date}`
    : null;

  function goToRoster(e: React.MouseEvent | React.KeyboardEvent) {
    if (!route) return;
    if ("key" in e && e.key !== "Enter" && e.key !== " ") return;
    e.preventDefault();
    navigate(route);
  }

  return (
    <div
      role={route ? "button" : undefined}
      tabIndex={route ? 0 : undefined}
      onClick={route ? goToRoster : undefined}
      onKeyDown={route ? goToRoster : undefined}
      className={cn(
        "group relative flex items-start gap-4 py-3",
        route && "cursor-pointer rounded-md hover:bg-muted/40 focus:outline-none focus:ring-2 focus:ring-primary/40 focus:ring-offset-2"
      )}
    >
      <div className="invisible absolute right-0 top-full z-20 mt-1 w-80 rounded-md border bg-popover p-3 text-popover-foreground shadow-lg group-hover:visible">
        <p className="mb-1 text-xs font-medium">
          {ev.display_name} · {ev.window_time}
        </p>
        {ev.location && (
          <p className="mb-2 inline-flex items-start gap-1 text-[11px] text-muted-foreground">
            <span>{ev.location}</span>
            <MapsLink address={ev.location} className="text-muted-foreground hover:text-foreground" />
          </p>
        )}
        <div className="space-y-2">
          {ev.services.map((svc) => (
            <ServiceBreakdown key={svc.appointment_type_id} svc={svc} />
          ))}
        </div>
        {(onSendAnnouncement || onSendReminder) && (
          <div className="mt-3 flex gap-2 border-t pt-2">
            {onSendAnnouncement && (
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  onSendAnnouncement(ev);
                }}
                className="inline-flex items-center gap-1 rounded-md border px-2 py-1 text-[11px] hover:bg-muted"
              >
                <Megaphone className="h-3 w-3" />
                Send announcement
              </button>
            )}
            {onSendReminder && (
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  onSendReminder(ev);
                }}
                className="inline-flex items-center gap-1 rounded-md border px-2 py-1 text-[11px] hover:bg-muted"
              >
                <Bell className="h-3 w-3" />
                Send reminder
              </button>
            )}
          </div>
        )}
      </div>
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
  onSendAnnouncement,
  onSendReminder,
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
              <EventRow
                key={ev.key}
                ev={ev}
                onSendAnnouncement={onSendAnnouncement}
                onSendReminder={onSendReminder}
              />
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
