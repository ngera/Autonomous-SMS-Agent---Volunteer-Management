import { useMemo } from "react";
import { Link } from "react-router-dom";
import {
  CheckCircle2,
  CircleDashed,
  CircleDot,
  Clock,
  History as HistoryIcon,
  Pencil,
  PlusCircle,
  RefreshCw,
  UserX,
  XCircle,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { LoadingState } from "@/components/shared/loading-state";
import { MapsLink } from "@/components/shared/maps-link";
import { cn, formatDate, formatPhone } from "@/lib/utils";
import { BookingStatus } from "@/types/enums";
import type {
  EventRosterHistoryEntry,
  EventRosterResponse,
  EventRosterService,
} from "@/types/api";

interface EventRosterCardProps {
  roster: EventRosterResponse | undefined;
  isLoading: boolean;
  highlightBookingId?: string;
}

const ACTIVE_STATUSES = new Set([
  BookingStatus.SCHEDULED,
  BookingStatus.RESCHEDULED,
  BookingStatus.COMPLETED,
]);

function trimTime(t: string): string {
  return t.length >= 5 ? t.slice(0, 5) : t;
}

export function EventRosterCard({
  roster,
  isLoading,
  highlightBookingId,
}: EventRosterCardProps) {
  const grouped = useMemo(() => groupByCategory(roster?.services ?? []), [roster]);

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Event Roster</CardTitle>
        </CardHeader>
        <CardContent>
          <LoadingState />
        </CardContent>
      </Card>
    );
  }

  if (!roster) return null;

  const event = roster.event;
  const sourceLabel =
    event?.source === "specific_date"
      ? "One-off Event"
      : event?.source === "weekly_rule"
        ? "Weekly Schedule"
        : "Manual Booking";

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex flex-wrap items-center justify-between gap-2">
          <span>Event Roster</span>
          <Badge variant="secondary" className="text-xs font-normal">
            {sourceLabel}
          </Badge>
        </CardTitle>
        {event && (
          <div className="text-sm text-muted-foreground space-y-0.5">
            <p>
              <span className="font-medium text-foreground">
                {event.label || (event.source === "weekly_rule" ? "Weekly window" : "Event")}
              </span>
              {" · "}
              {formatDate(event.date)}
              {" · "}
              {trimTime(event.start_time)} – {trimTime(event.end_time)}
            </p>
            {event.location && (
              <p className="inline-flex items-center gap-1.5">
                <span>{event.location}</span>
                <MapsLink address={event.location} />
              </p>
            )}
          </div>
        )}
      </CardHeader>
      <CardContent className="space-y-4">
        {grouped.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No services configured for this slot.
          </p>
        ) : (
          grouped.map(({ category, services }) => (
            <div key={category} className="space-y-2">
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                {category}
              </p>
              <div className="space-y-2">
                {services.map((svc) => (
                  <ServiceBlock
                    key={svc.appointment_type_id}
                    svc={svc}
                    highlightBookingId={highlightBookingId}
                  />
                ))}
              </div>
            </div>
          ))
        )}
        <HistorySection history={roster.history ?? []} />
      </CardContent>
    </Card>
  );
}

function serviceFillKind(
  active: number,
  max: number,
): "empty" | "partial" | "full" {
  if (active === 0) return "empty";
  if (max > 0 && active >= max) return "full";
  return "partial";
}

interface ServiceBlockProps {
  svc: EventRosterService;
  highlightBookingId?: string;
}

function ServiceBlock({ svc, highlightBookingId }: ServiceBlockProps) {
  const activeSignups = svc.signups.filter((s) =>
    ACTIVE_STATUSES.has(s.status as BookingStatus)
  );
  const inactiveSignups = svc.signups.filter(
    (s) => !ACTIVE_STATUSES.has(s.status as BookingStatus)
  );
  const filledLabel =
    svc.min_required > 0 && activeSignups.length < svc.min_required
      ? `${activeSignups.length} / ${svc.min_required} min · ${svc.max_allowed} max`
      : `${activeSignups.length} / ${svc.max_allowed} signed up`;
  const statusKind = serviceFillKind(activeSignups.length, svc.max_allowed);
  const StatusIcon =
    statusKind === "full"
      ? CheckCircle2
      : statusKind === "empty"
        ? CircleDashed
        : CircleDot;
  const statusColor =
    statusKind === "full"
      ? "text-emerald-600 dark:text-emerald-400"
      : statusKind === "empty"
        ? "text-red-600 dark:text-red-400"
        : "text-amber-600 dark:text-amber-400";
  const statusLabel =
    statusKind === "full"
      ? "100% booked"
      : statusKind === "empty"
        ? "Nothing booked"
        : "Partially booked";

  return (
    <div className="rounded-md border p-3">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <StatusIcon
            className={cn("h-4 w-4 shrink-0", statusColor)}
            aria-label={statusLabel}
          />
          <p className="text-sm font-medium">{svc.name}</p>
        </div>
        <p className="text-xs text-muted-foreground">{filledLabel}</p>
      </div>
      {activeSignups.length === 0 && inactiveSignups.length === 0 ? (
        <p className="text-xs text-muted-foreground italic">No volunteers signed up.</p>
      ) : (
        <ul className="space-y-1 text-sm">
          {activeSignups.map((s) => (
            <SignupRow
              key={s.booking_id}
              signup={s}
              highlight={s.booking_id === highlightBookingId}
            />
          ))}
          {inactiveSignups.map((s) => (
            <SignupRow
              key={s.booking_id}
              signup={s}
              highlight={s.booking_id === highlightBookingId}
              dim
            />
          ))}
        </ul>
      )}
    </div>
  );
}

interface SignupRowProps {
  signup: { booking_id: string; phone: string; name: string | null; status: string };
  highlight?: boolean;
  dim?: boolean;
}

function SignupRow({ signup, highlight, dim }: SignupRowProps) {
  const display = (signup.name ?? "").trim() || "—";
  return (
    <li
      className={`flex flex-wrap items-center justify-between gap-2 rounded px-2 py-1 ${
        highlight ? "bg-primary/10" : ""
      } ${dim ? "opacity-60" : ""}`}
    >
      <Link
        to={`/bookings/${signup.booking_id}`}
        className="flex flex-wrap items-baseline gap-x-3 gap-y-0.5 hover:underline"
      >
        <span className="font-medium">{display}</span>
        <span className="text-xs text-muted-foreground">
          {formatPhone(signup.phone)}
        </span>
      </Link>
      {signup.status !== BookingStatus.SCHEDULED && (
        <Badge variant="outline" className="text-[10px] uppercase">
          {signup.status.toLowerCase().replace("_", " ")}
        </Badge>
      )}
    </li>
  );
}

// ── History section ───────────────────────────────────────────────

export function HistorySection({ history }: { history: EventRosterHistoryEntry[] }) {
  return (
    <div className="space-y-2 border-t pt-4">
      <div className="flex items-center gap-2">
        <HistoryIcon className="h-3.5 w-3.5 text-muted-foreground" />
        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          History
        </p>
        <span className="text-[11px] text-muted-foreground">
          {history.length === 0
            ? "nothing yet"
            : `${history.length} event${history.length === 1 ? "" : "s"}`}
        </span>
      </div>
      {history.length === 0 ? (
        <p className="text-xs italic text-muted-foreground">
          No booking activity yet for this event.
        </p>
      ) : (
        <ul className="space-y-1.5">
          {history.map((h, i) => (
            <HistoryRow key={`${h.booking_id}:${h.timestamp}:${i}`} entry={h} />
          ))}
        </ul>
      )}
    </div>
  );
}

const EVENT_TYPE_META: Record<
  EventRosterHistoryEntry["event_type"],
  { Icon: React.ComponentType<{ className?: string }>; color: string; verb: string }
> = {
  created: {
    Icon: PlusCircle,
    color: "text-emerald-600 dark:text-emerald-400",
    verb: "booked",
  },
  rescheduled: {
    Icon: RefreshCw,
    color: "text-amber-600 dark:text-amber-400",
    verb: "rescheduled",
  },
  cancelled: {
    Icon: XCircle,
    color: "text-rose-600 dark:text-rose-400",
    verb: "cancelled",
  },
  completed: {
    Icon: CheckCircle2,
    color: "text-emerald-600 dark:text-emerald-400",
    verb: "completed",
  },
  no_show: {
    Icon: UserX,
    color: "text-rose-600 dark:text-rose-400",
    verb: "no-show",
  },
  status_changed: {
    Icon: Pencil,
    color: "text-sky-600 dark:text-sky-400",
    verb: "status changed",
  },
};

function HistoryRow({ entry }: { entry: EventRosterHistoryEntry }) {
  const meta = EVENT_TYPE_META[entry.event_type] ?? EVENT_TYPE_META.status_changed;
  const Icon = meta.Icon;
  const volunteer = (entry.volunteer_name ?? "").trim() || formatPhone(entry.volunteer_phone);
  const actor =
    entry.changed_by === "admin"
      ? entry.admin_email
        ? `admin · ${entry.admin_email}`
        : "admin"
      : entry.changed_by === "scheduler"
        ? "auto-scheduler"
        : "via SMS";

  const detail = buildHistoryDetail(entry);

  return (
    <li className="flex gap-2 rounded px-2 py-1.5 hover:bg-muted/40">
      <Icon className={cn("mt-0.5 h-4 w-4 shrink-0", meta.color)} />
      <div className="min-w-0 flex-1 space-y-0.5">
        <p className="text-xs">
          <Link
            to={`/bookings/${entry.booking_id}`}
            className="font-medium hover:underline"
          >
            {volunteer}
          </Link>
          {" "}
          <span className="text-muted-foreground">{meta.verb}</span>
          {entry.service_name && (
            <>
              {" "}
              <span className="font-medium">{entry.service_name}</span>
            </>
          )}
          {detail && (
            <>
              {" — "}
              <span className="text-muted-foreground">{detail}</span>
            </>
          )}
        </p>
        <p className="flex items-center gap-2 text-[11px] text-muted-foreground">
          <Clock className="h-3 w-3" />
          {formatRelative(entry.timestamp)}
          <span>·</span>
          <span>{actor}</span>
          {entry.notes && (
            <>
              <span>·</span>
              <span className="italic">{entry.notes}</span>
            </>
          )}
        </p>
      </div>
    </li>
  );
}

function buildHistoryDetail(entry: EventRosterHistoryEntry): string {
  if (
    entry.event_type === "rescheduled" &&
    entry.previous_scheduled_at &&
    entry.new_scheduled_at
  ) {
    return `${formatTime(entry.previous_scheduled_at)} → ${formatTime(entry.new_scheduled_at)}`;
  }
  if (entry.event_type === "status_changed" && entry.previous_status && entry.new_status) {
    return `${entry.previous_status.toLowerCase().replace("_", " ")} → ${entry.new_status.toLowerCase().replace("_", " ")}`;
  }
  return "";
}

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

function formatRelative(iso: string): string {
  try {
    const then = new Date(iso).getTime();
    const now = Date.now();
    const diffSec = Math.round((now - then) / 1000);
    if (diffSec < 60) return "just now";
    if (diffSec < 3600) return `${Math.round(diffSec / 60)}m ago`;
    if (diffSec < 86_400) return `${Math.round(diffSec / 3600)}h ago`;
    if (diffSec < 7 * 86_400) return `${Math.round(diffSec / 86_400)}d ago`;
    return new Date(iso).toLocaleDateString(undefined, {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  } catch {
    return iso;
  }
}

function groupByCategory(services: EventRosterService[]) {
  const map = new Map<string, EventRosterService[]>();
  for (const s of services) {
    const list = map.get(s.category) ?? [];
    list.push(s);
    map.set(s.category, list);
  }
  return Array.from(map.entries())
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([category, list]) => ({
      category,
      services: list.sort((a, b) => a.name.localeCompare(b.name)),
    }));
}
