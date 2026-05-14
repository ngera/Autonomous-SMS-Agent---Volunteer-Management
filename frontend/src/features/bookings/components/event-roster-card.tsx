import { useMemo } from "react";
import { Link } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { LoadingState } from "@/components/shared/loading-state";
import { MapsLink } from "@/components/shared/maps-link";
import { formatDate, formatPhone } from "@/lib/utils";
import { BookingStatus } from "@/types/enums";
import type { EventRosterResponse, EventRosterService } from "@/types/api";

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
      </CardContent>
    </Card>
  );
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

  return (
    <div className="rounded-md border p-3">
      <div className="mb-2 flex flex-wrap items-baseline justify-between gap-2">
        <p className="text-sm font-medium">{svc.name}</p>
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
