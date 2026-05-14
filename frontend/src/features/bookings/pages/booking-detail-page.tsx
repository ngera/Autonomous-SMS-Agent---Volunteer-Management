import { useMemo, useState } from "react";
import { useParams, useNavigate, useLocation, Link } from "react-router-dom";
import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle,
  ChevronDown,
  ChevronRight,
  Megaphone,
  Pencil,
  RefreshCw,
  XCircle,
} from "lucide-react";
import { differenceInCalendarDays } from "date-fns";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { PageHeader } from "@/components/shared/page-header";
import { LoadingState } from "@/components/shared/loading-state";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { MapsLink } from "@/components/shared/maps-link";
import { formatDate, formatDateTime, formatPhone } from "@/lib/utils";
import { useAuth } from "@/hooks/use-auth";
import { AdminRole, BookingStatus } from "@/types/enums";
import {
  useBooking,
  useBookingEventRoster,
  useBookingHistory,
  useSpecificSlotEventRoster,
  useWeeklyRuleEventRoster,
  useRescheduleBooking,
  useUpdateBookingStatus,
  useCancelBooking,
} from "../hooks/use-bookings";
import { BookingHistoryTimeline } from "../components/booking-history-timeline";
import { RescheduleDialog } from "../components/reschedule-dialog";
import { StatusUpdateDialog } from "../components/status-update-dialog";
import { AnnouncementForm } from "@/features/announcements/components/announcement-form";
import { useCreateAnnouncement } from "@/features/announcements/hooks/use-announcements";
import type {
  EventContext,
  EventRosterService,
  EventRosterSignup,
} from "@/types/api";

const ACTIVE_STATUSES = new Set<string>([
  BookingStatus.SCHEDULED,
  BookingStatus.RESCHEDULED,
  BookingStatus.COMPLETED,
]);

const ALERT_DAYS_AHEAD = 2;

function trimTime(t: string): string {
  return t.length >= 5 ? t.slice(0, 5) : t;
}

function fmtTimeRange(start: string, end: string): string {
  return `${trimTime(start)} – ${trimTime(end)}`;
}

function parseEventDate(dateStr: string): Date {
  const [y, m, d] = dateStr.split("-").map(Number);
  return new Date(y, m - 1, d);
}

interface CategoryGroup {
  category: string;
  services: EventRosterService[];
}

function groupByCategory(services: EventRosterService[]): CategoryGroup[] {
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

export function BookingDetailPage() {
  // Page handles three entry routes:
  //   /bookings/:id                 → booking-based (focal booking + roster)
  //   /events/specific/:slotId      → specific-date event (no focal booking)
  //   /events/rule/:ruleId/:date    → weekly-rule occurrence (no focal booking)
  // tanstack-query's `enabled` flag in each hook handles which queries actually fire.
  const params = useParams<{
    id?: string;
    slotId?: string;
    ruleId?: string;
    date?: string;
  }>();
  const navigate = useNavigate();
  const location = useLocation();
  const { hasRole } = useAuth();

  // React Router gives the very first history entry a key of "default"; on
  // every subsequent push it generates a fresh key. So if we still have
  // "default", the user landed here directly (deep link / refresh) — there's
  // nothing to go back to, fall through to the calendar.
  function handleBack() {
    if (location.key && location.key !== "default") {
      navigate(-1);
    } else {
      navigate("/bookings");
    }
  }

  const mode: "booking" | "specific" | "rule" = params.id
    ? "booking"
    : params.slotId
      ? "specific"
      : "rule";

  const booking = useBooking(params.id ?? "");
  const history = useBookingHistory(params.id ?? "");
  const bookingRoster = useBookingEventRoster(params.id ?? "");
  const specificRoster = useSpecificSlotEventRoster(params.slotId);
  const weeklyRoster = useWeeklyRuleEventRoster(params.ruleId, params.date);
  const roster =
    mode === "booking"
      ? bookingRoster
      : mode === "specific"
        ? specificRoster
        : weeklyRoster;
  const reschedule = useRescheduleBooking();
  const statusUpdate = useUpdateBookingStatus();
  const cancel = useCancelBooking();

  const [showReschedule, setShowReschedule] = useState(false);
  const [showStatusUpdate, setShowStatusUpdate] = useState(false);
  const [showCancel, setShowCancel] = useState(false);
  const [showAnnouncement, setShowAnnouncement] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const createAnnouncement = useCreateAnnouncement();

  const services = roster.data?.services ?? [];

  const totals = useMemo(() => {
    let totalMin = 0;
    let totalMax = 0;
    let totalActive = 0;
    let hasConfig = false;
    for (const s of services) {
      totalMin += s.min_required;
      totalMax += s.max_allowed;
      if (s.min_required > 0 || s.max_allowed > 0) hasConfig = true;
      for (const sg of s.signups) {
        if (ACTIVE_STATUSES.has(sg.status)) totalActive += 1;
      }
    }
    return {
      totalMin,
      totalMax,
      totalActive,
      moreNeeded: Math.max(0, totalMin - totalActive),
      hasConfig,
    };
  }, [services]);

  const cancelledSignups = useMemo<Array<EventRosterSignup & { service_name: string }>>(
    () =>
      services.flatMap((s) =>
        s.signups
          .filter((sg) => !ACTIVE_STATUSES.has(sg.status))
          .map((sg) => ({ ...sg, service_name: s.name }))
      ).sort(
        (a, b) =>
          new Date(b.scheduled_at).getTime() - new Date(a.scheduled_at).getTime()
      ),
    [services]
  );

  const event = roster.data?.event ?? null;
  const today = useMemo(() => new Date(), []);
  const daysAway = event ? differenceInCalendarDays(parseEventDate(event.date), today) : null;
  const showAlert =
    totals.hasConfig &&
    totals.moreNeeded > 0 &&
    daysAway !== null &&
    daysAway >= 0 &&
    daysAway <= ALERT_DAYS_AHEAD;
  const daysAwayLabel =
    daysAway === null
      ? ""
      : daysAway < 0
        ? `${Math.abs(daysAway)} day${Math.abs(daysAway) === 1 ? "" : "s"} ago`
        : daysAway === 0
          ? "today"
          : daysAway === 1
            ? "tomorrow"
            : `in ${daysAway} days`;

  const grouped = useMemo(() => groupByCategory(services), [services]);

  if (mode === "booking" && booking.isLoading) return <LoadingState />;
  if (mode === "booking" && !booking.data) return <p>Booking not found.</p>;
  if (roster.isLoading && !roster.data) return <LoadingState />;
  if (!roster.data) return <p>Event not found.</p>;

  const b = booking.data;
  const isActiveBooking =
    !!b &&
    (b.status === BookingStatus.SCHEDULED || b.status === BookingStatus.RESCHEDULED);
  const canModify = hasRole(AdminRole.MANAGER);
  const highlightBookingId = b?.id ?? "";

  const announcementCtx: EventContext | null =
    event && services.length > 0
      ? {
          event_label:
            event.label ||
            (event.source === "weekly_rule" ? "Weekly window" : "Event"),
          event_date: event.date,
          event_start_time: trimTime(event.start_time),
          event_end_time: trimTime(event.end_time),
          event_location: event.location,
          service_name: services[0].name,
          appointment_type_id: services[0].appointment_type_id,
        }
      : null;

  const sourceLabel =
    event?.source === "specific_date"
      ? "One-off Event"
      : event?.source === "weekly_rule"
        ? "Weekly Schedule"
        : "Manual Booking";

  return (
    <div className="space-y-6">
      <PageHeader
        title={event?.label || "Event Detail"}
        actions={
          <Button variant="ghost" onClick={handleBack}>
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back
          </Button>
        }
      />

      {/* Event header */}
      <Card
        className={
          showAlert ? "border-red-300 dark:border-red-900" : undefined
        }
      >
        <CardHeader className="space-y-2">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div className="space-y-1">
              <CardTitle className="text-xl">
                {event?.label || (event?.source === "weekly_rule" ? "Weekly window" : "Event")}
              </CardTitle>
              {event && (
                <p className="text-sm text-muted-foreground">
                  {formatDate(event.date)} · {fmtTimeRange(event.start_time, event.end_time)}
                  {daysAwayLabel ? ` · ${daysAwayLabel}` : ""}
                </p>
              )}
              {event?.location && (
                <p className="text-sm text-muted-foreground inline-flex items-center gap-1.5">
                  <span>{event.location}</span>
                  <MapsLink address={event.location} />
                </p>
              )}
            </div>
            <div className="flex items-center gap-2">
              {canModify && event?.source_id && event.source === "specific_date" && (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() =>
                    navigate(
                      `/availability?tab=specific&edit_slot=${event.source_id}`
                    )
                  }
                >
                  <Pencil className="mr-2 h-3.5 w-3.5" />
                  Edit event
                </Button>
              )}
              {canModify && event?.source === "weekly_rule" && (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => navigate("/availability?tab=schedule")}
                >
                  <Pencil className="mr-2 h-3.5 w-3.5" />
                  Edit weekly schedule
                </Button>
              )}
              {canModify && announcementCtx && (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => setShowAnnouncement(true)}
                >
                  <Megaphone className="mr-2 h-3.5 w-3.5" />
                  Send announcement
                </Button>
              )}
              <Badge variant="secondary" className="text-xs font-normal">
                {sourceLabel}
              </Badge>
            </div>
          </div>

          {showAlert && (
            <div className="flex items-start gap-2 rounded-md border border-red-300 bg-red-50 p-3 text-sm text-red-900 dark:border-red-900 dark:bg-red-950 dark:text-red-200">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
              <p>
                Event is <strong>{daysAwayLabel}</strong> and still needs{" "}
                <strong>{totals.moreNeeded}</strong> more volunteer
                {totals.moreNeeded === 1 ? "" : "s"} to meet the minimum of {totals.totalMin}.
              </p>
            </div>
          )}
        </CardHeader>

        <CardContent>
          <div className="grid gap-3 sm:grid-cols-4">
            <Stat label="Booked" value={totals.totalActive} />
            <Stat
              label="Minimum needed"
              value={totals.hasConfig ? totals.totalMin : "—"}
            />
            <Stat
              label="Maximum"
              value={totals.hasConfig ? totals.totalMax : "—"}
            />
            <Stat
              label="More needed"
              value={totals.hasConfig ? totals.moreNeeded : 0}
              accent={
                totals.hasConfig && totals.moreNeeded > 0
                  ? showAlert
                    ? "danger"
                    : "warning"
                  : "ok"
              }
            />
          </div>
        </CardContent>
      </Card>

      {/* Focal booking actions — only when entering via a booking */}
      {canModify && isActiveBooking && b && (
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs text-muted-foreground">
            Actions on this booking ({b.contact_name || formatPhone(b.contact_phone)})
          </span>
          <Button variant="outline" size="sm" onClick={() => setShowReschedule(true)}>
            <RefreshCw className="mr-2 h-4 w-4" />
            Reschedule
          </Button>
          <Button variant="outline" size="sm" onClick={() => setShowStatusUpdate(true)}>
            <CheckCircle className="mr-2 h-4 w-4" />
            Update Status
          </Button>
          <Button variant="destructive" size="sm" onClick={() => setShowCancel(true)}>
            <XCircle className="mr-2 h-4 w-4" />
            Cancel
          </Button>
        </div>
      )}

      {/* Active roster, grouped by category then service */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Roster</CardTitle>
        </CardHeader>
        <CardContent className="space-y-5">
          {roster.isLoading ? (
            <LoadingState />
          ) : grouped.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No services configured for this slot.
            </p>
          ) : (
            grouped.map(({ category, services: list }) => (
              <div key={category} className="space-y-2">
                <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  {category}
                </p>
                <div className="space-y-2">
                  {list.map((svc) => (
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

      {/* History — collapsed by default to keep the active roster front and centre */}
      <Card>
        <button
          type="button"
          onClick={() => setHistoryOpen((v) => !v)}
          aria-expanded={historyOpen}
          aria-controls="event-history-content"
          className="flex w-full items-center justify-between gap-2 px-4 py-3 text-left hover:bg-muted/40"
        >
          <div className="flex items-center gap-2">
            {historyOpen ? (
              <ChevronDown className="h-4 w-4 text-muted-foreground" />
            ) : (
              <ChevronRight className="h-4 w-4 text-muted-foreground" />
            )}
            <CardTitle className="text-base">History</CardTitle>
            {cancelledSignups.length > 0 && (
              <Badge variant="secondary" className="text-[10px]">
                {cancelledSignups.length} cancelled
              </Badge>
            )}
          </div>
          <span className="text-xs text-muted-foreground">
            {historyOpen ? "Hide" : "Show"}
          </span>
        </button>
        {historyOpen && (
          <CardContent id="event-history-content" className="space-y-4 pt-0">
            {cancelledSignups.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No cancelled or no-show bookings for this event.
              </p>
            ) : (
              <div className="space-y-1.5">
                {cancelledSignups.map((sg) => (
                  <CancelledRow key={sg.booking_id} sg={sg} />
                ))}
              </div>
            )}

            {b && (
              <div className="border-t pt-3">
                <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Status changes for this booking
                </p>
                <BookingHistoryTimeline
                  history={history.data ?? []}
                  isLoading={history.isLoading}
                />
              </div>
            )}
          </CardContent>
        )}
      </Card>

      {b && (
        <>
          <RescheduleDialog
            open={showReschedule}
            onOpenChange={setShowReschedule}
            appointmentTypeId={b.appointment_type_id}
            isLoading={reschedule.isPending}
            onConfirm={(newScheduledAt) => {
              reschedule.mutate(
                { id: b.id, body: { new_scheduled_at: newScheduledAt } },
                {
                  onSuccess: () => {
                    setShowReschedule(false);
                    void booking.refetch();
                    void history.refetch();
                    void roster.refetch();
                  },
                }
              );
            }}
          />

          <StatusUpdateDialog
            open={showStatusUpdate}
            onOpenChange={setShowStatusUpdate}
            currentStatus={b.status}
            isLoading={statusUpdate.isPending}
            onConfirm={(status, notes) => {
              statusUpdate.mutate(
                { id: b.id, body: { status, notes } },
                {
                  onSuccess: () => {
                    setShowStatusUpdate(false);
                    void booking.refetch();
                    void history.refetch();
                    void roster.refetch();
                  },
                }
              );
            }}
          />

          <ConfirmDialog
            open={showCancel}
            onOpenChange={setShowCancel}
            title="Cancel Booking"
            description="Are you sure you want to cancel this booking? The customer will be notified via SMS."
            confirmLabel="Cancel Booking"
            variant="destructive"
            isLoading={cancel.isPending}
            onConfirm={() => {
              cancel.mutate(b.id, {
                onSuccess: () => {
                  setShowCancel(false);
                  navigate("/bookings");
                },
              });
            }}
          />
        </>
      )}

      <AnnouncementForm
        open={showAnnouncement}
        onOpenChange={setShowAnnouncement}
        initialEventContext={announcementCtx}
        isLoading={createAnnouncement.isPending}
        onSubmit={(data) =>
          createAnnouncement.mutate(data, {
            onSuccess: () => setShowAnnouncement(false),
            onError: (err: unknown) => {
              const detail =
                (err as { response?: { data?: { detail?: string } } })?.response
                  ?.data?.detail ||
                (err as Error)?.message ||
                "Failed to send announcement";
              alert(`Could not send announcement: ${detail}`);
            },
          })
        }
      />
    </div>
  );
}

interface StatProps {
  label: string;
  value: number | string;
  accent?: "ok" | "warning" | "danger";
}

function Stat({ label, value, accent = "ok" }: StatProps) {
  const accentClass =
    accent === "danger"
      ? "text-red-700 dark:text-red-300"
      : accent === "warning"
        ? "text-amber-700 dark:text-amber-300"
        : "text-foreground";
  return (
    <div className="rounded-md border bg-muted/30 p-3">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className={`text-2xl font-semibold leading-none ${accentClass}`}>
        {value}
      </p>
    </div>
  );
}

interface ServiceBlockProps {
  svc: EventRosterService;
  highlightBookingId: string;
}

function ServiceBlock({ svc, highlightBookingId }: ServiceBlockProps) {
  const activeSignups = svc.signups.filter((s) => ACTIVE_STATUSES.has(s.status));
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
      {activeSignups.length === 0 ? (
        <p className="text-xs italic text-muted-foreground">
          No volunteers signed up yet.
        </p>
      ) : (
        <ul className="space-y-1 text-sm">
          {activeSignups.map((s) => (
            <SignupRow
              key={s.booking_id}
              signup={s}
              highlight={s.booking_id === highlightBookingId}
            />
          ))}
        </ul>
      )}
    </div>
  );
}

interface SignupRowProps {
  signup: EventRosterSignup;
  highlight?: boolean;
}

function SignupRow({ signup, highlight }: SignupRowProps) {
  const display = (signup.name ?? "").trim() || "—";
  return (
    <li
      className={`flex flex-wrap items-center justify-between gap-2 rounded px-2 py-1 ${
        highlight ? "bg-primary/10" : ""
      }`}
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

interface CancelledRowProps {
  sg: EventRosterSignup & { service_name: string };
}

function CancelledRow({ sg }: CancelledRowProps) {
  const display = (sg.name ?? "").trim() || "—";
  const tone =
    sg.status === BookingStatus.CANCELLED
      ? "text-muted-foreground"
      : sg.status === BookingStatus.NO_SHOW
        ? "text-red-700 dark:text-red-300"
        : "text-muted-foreground";
  return (
    <Link
      to={`/bookings/${sg.booking_id}`}
      className="flex flex-wrap items-center justify-between gap-2 rounded border bg-muted/30 px-3 py-2 text-sm hover:bg-muted/50"
    >
      <div className="flex flex-col">
        <span className={`font-medium ${tone}`}>{display}</span>
        <span className="text-xs text-muted-foreground">
          {formatPhone(sg.phone)} · {sg.service_name} · was scheduled{" "}
          {formatDateTime(sg.scheduled_at)}
        </span>
      </div>
      <Badge variant="outline" className="text-[10px] uppercase">
        {sg.status.toLowerCase().replace("_", " ")}
      </Badge>
    </Link>
  );
}
