import { useMemo } from "react";
import { useNavigate } from "react-router-dom";
import {
  format,
  addDays,
  isSameDay,
  isToday,
  getDay,
  parseISO,
  isWithinInterval,
  differenceInCalendarDays,
} from "date-fns";
import { AlertTriangle, CalendarDays, Repeat } from "lucide-react";
import { cn } from "@/lib/utils";
import type {
  AvailabilityRuleResponse,
  BlockedDateResponse,
  BookingResponse,
  ServiceSlotConfig,
  SpecificDateSlotResponse,
} from "@/types/api";
import { BookingStatus } from "@/types/enums";

const HOUR_START = 8; // 8 AM
const HOUR_END = 21; // 9 PM
const ROW_HEIGHT = 32; // px per 30-min slot
const TOTAL_SLOTS = (HOUR_END - HOUR_START) * 2;
const ALERT_DAYS_AHEAD = 2; // flag understaffed slots within this many days

const ACTIVE_STATUSES = new Set<string>([
  BookingStatus.SCHEDULED,
  BookingStatus.RESCHEDULED,
  BookingStatus.COMPLETED,
]);

// date-fns getDay: 0=Sunday, but availability rules use 0=Monday
function toRuleDow(dateFnsDay: number): number {
  return dateFnsDay === 0 ? 6 : dateFnsDay - 1;
}

function trimTime(t: string): string {
  return t.length >= 5 ? t.slice(0, 5) : t;
}

function fmtTimeRange(start: string, end: string): string {
  return `${trimTime(start)} – ${trimTime(end)}`;
}

function parseEventDateTime(dateStr: string, time: string): Date {
  // dateStr is "YYYY-MM-DD" and time is "HH:MM:SS"; build a local Date so
  // comparisons against booking timestamps work correctly.
  const [y, m, d] = dateStr.split("-").map(Number);
  const [hh, mm, ss] = time.split(":").map(Number);
  return new Date(y, m - 1, d, hh, mm, ss || 0);
}

interface WeeklyCalendarProps {
  weekStart: Date;
  bookings: BookingResponse[];
  availabilityRules: AvailabilityRuleResponse[];
  specificDateSlots: SpecificDateSlotResponse[];
  blockedDates: BlockedDateResponse[];
  isLoading: boolean;
}

interface EventCard {
  kind: "event";
  key: string;
  startDate: Date;
  endDate: Date;
  duration_minutes: number;
  name: string;
  active_count: number;
  min_required: number;
  max_allowed: number;
  has_config: boolean;
  representative_booking_id: string | null;
  event_cancelled: boolean;
  service_count: number;
  source: "specific" | "rule";
  source_id: string; // SpecificDateSlot.id or AvailabilityRule.id
  occurrence_date: string; // YYYY-MM-DD — needed by the weekly-rule roster route
}

interface SlotGroup {
  kind: "slot";
  key: string;
  startDate: Date;
  appointment_type_id: string;
  service_name: string;
  duration_minutes: number;
  active_count: number;
  min_required: number;
  max_allowed: number;
  representative_booking_id: string;
  event_cancelled: boolean;
}

type DayCard = EventCard | SlotGroup;

function getLimitsFromConfig(
  config: ServiceSlotConfig[] | null,
  typeId: string
): { min: number; max: number } | null {
  if (!config || config.length === 0) return { min: 1, max: 1 };
  for (const c of config) {
    if (c.appointment_type_id === typeId) {
      const min = c.min_required ?? 1;
      const max = c.max_allowed ?? min;
      return { min, max };
    }
  }
  return null;
}

function findOrphanLimits(
  date: Date,
  typeId: string,
  rules: AvailabilityRuleResponse[]
): { min: number; max: number } {
  const time = format(date, "HH:mm:ss");
  const dow = toRuleDow(getDay(date));
  for (const r of rules) {
    if (r.day_of_week !== dow || !r.is_active) continue;
    if (!(r.start_time <= time && r.end_time >= time)) continue;
    const limits = getLimitsFromConfig(r.service_config, typeId);
    if (limits) return limits;
  }
  return { min: 1, max: 1 };
}

export function WeeklyCalendar({
  weekStart,
  bookings,
  availabilityRules,
  specificDateSlots,
  blockedDates,
  isLoading,
}: WeeklyCalendarProps) {
  const navigate = useNavigate();
  const days = Array.from({ length: 7 }, (_, i) => addDays(weekStart, i));
  const timeSlots = Array.from({ length: TOTAL_SLOTS }, (_, i) => {
    const totalMinutes = HOUR_START * 60 + i * 30;
    const hours = Math.floor(totalMinutes / 60);
    const minutes = totalMinutes % 60;
    return {
      hours,
      minutes,
      label: i % 2 === 0 ? format(new Date(2000, 0, 1, hours, minutes), "h:mm a") : "",
    };
  });

  // Build a per-day list of cards. Every specific-date event in the visible
  // week becomes a single card (regardless of how many services are inside),
  // showing name + start-end time + total booked vs total minimum across all
  // configured services. Bookings not covered by a specific-date event fall
  // back to per-(time, service) cards so weekly-window and ad-hoc bookings
  // are still visible.
  const cardsByDay = useMemo<Map<string, DayCard[]>>(() => {
    const result = new Map<string, DayCard[]>();
    const weekEnd = addDays(weekStart, 7);
    const coveredBookingIds = new Set<string>();

    // Quick lookup: which specific-date event (if any) covers a booking?
    function findCoveringEvent(b: BookingResponse): SpecificDateSlotResponse | null {
      const bDate = new Date(b.scheduled_at);
      for (const sds of specificDateSlots) {
        if (sds.date !== format(bDate, "yyyy-MM-dd")) continue;
        const eventStart = parseEventDateTime(sds.date, sds.start_time);
        const eventEnd = parseEventDateTime(sds.date, sds.end_time);
        if (bDate < eventStart || bDate > eventEnd) continue;
        if (sds.service_config && sds.service_config.length > 0) {
          const ids = new Set(
            sds.service_config.map((c) => c.appointment_type_id)
          );
          if (!ids.has(b.appointment_type_id)) continue;
        }
        return sds;
      }
      return null;
    }

    // 1) One card per specific-date event in this week.
    for (const sds of specificDateSlots) {
      const eventStart = parseEventDateTime(sds.date, sds.start_time);
      const eventEnd = parseEventDateTime(sds.date, sds.end_time);
      if (eventStart < weekStart || eventStart >= weekEnd) continue;

      const allowedTypeIds =
        sds.service_config && sds.service_config.length > 0
          ? new Set(sds.service_config.map((c) => c.appointment_type_id))
          : null;
      const hasConfig = (sds.service_config?.length ?? 0) > 0;
      const minTotal = (sds.service_config ?? []).reduce(
        (sum, c) => sum + (c.min_required ?? 1),
        0
      );
      const maxTotal = (sds.service_config ?? []).reduce(
        (sum, c) => sum + (c.max_allowed ?? c.min_required ?? 1),
        0
      );

      let active_count = 0;
      let activeRepresentative: string | null = null;
      let anyRepresentative: string | null = null;
      for (const b of bookings) {
        const bDate = new Date(b.scheduled_at);
        if (bDate < eventStart || bDate > eventEnd) continue;
        if (allowedTypeIds !== null && !allowedTypeIds.has(b.appointment_type_id))
          continue;
        coveredBookingIds.add(b.id);
        if (anyRepresentative === null) anyRepresentative = b.id;
        if (ACTIVE_STATUSES.has(b.status)) {
          active_count += 1;
          if (activeRepresentative === null) activeRepresentative = b.id;
        }
      }
      // Prefer an active booking as the click target so the detail page lands
      // on a live booking + its event roster. Fall back to any booking when
      // every signup is cancelled, so the card still navigates and the
      // EventRosterCard shows the cancelled signups (dimmed).
      const representative = activeRepresentative ?? anyRepresentative;

      const dayKey = format(eventStart, "yyyy-MM-dd");
      const list = result.get(dayKey) ?? [];
      list.push({
        kind: "event",
        key: `event-${sds.id}`,
        startDate: eventStart,
        endDate: eventEnd,
        duration_minutes: Math.max(
          15,
          Math.round((eventEnd.getTime() - eventStart.getTime()) / 60000)
        ),
        name: sds.label?.trim() || "Event",
        active_count,
        min_required: hasConfig ? minTotal : 0,
        max_allowed: hasConfig ? maxTotal : 0,
        has_config: hasConfig,
        representative_booking_id: representative,
        event_cancelled: !sds.is_active,
        service_count: sds.service_config?.length ?? 0,
        source: "specific",
        source_id: sds.id,
        occurrence_date: sds.date,
      });
      result.set(dayKey, list);
    }

    // 2) One card per weekly-rule occurrence in this week. Specific-date
    //    events take precedence — bookings they already claimed are skipped
    //    here so they aren't counted twice.
    for (let dayIdx = 0; dayIdx < 7; dayIdx++) {
      const day = addDays(weekStart, dayIdx);
      const dow = toRuleDow(getDay(day));
      for (const rule of availabilityRules) {
        if (!rule.is_active || rule.day_of_week !== dow) continue;
        const [sh, sm] = rule.start_time.split(":").map(Number);
        const [eh, em] = rule.end_time.split(":").map(Number);
        const ruleStart = new Date(
          day.getFullYear(),
          day.getMonth(),
          day.getDate(),
          sh,
          sm
        );
        const ruleEnd = new Date(
          day.getFullYear(),
          day.getMonth(),
          day.getDate(),
          eh,
          em
        );

        const allowedTypeIds =
          rule.service_config && rule.service_config.length > 0
            ? new Set(rule.service_config.map((c) => c.appointment_type_id))
            : null;
        const hasConfig = (rule.service_config?.length ?? 0) > 0;
        const minTotal = (rule.service_config ?? []).reduce(
          (sum, c) => sum + (c.min_required ?? 1),
          0
        );
        const maxTotal = (rule.service_config ?? []).reduce(
          (sum, c) => sum + (c.max_allowed ?? c.min_required ?? 1),
          0
        );

        let active_count = 0;
        let activeRepresentative: string | null = null;
        let anyRepresentative: string | null = null;
        for (const b of bookings) {
          if (coveredBookingIds.has(b.id)) continue;
          const bDate = new Date(b.scheduled_at);
          if (bDate < ruleStart || bDate > ruleEnd) continue;
          if (
            allowedTypeIds !== null &&
            !allowedTypeIds.has(b.appointment_type_id)
          ) {
            continue;
          }
          coveredBookingIds.add(b.id);
          if (anyRepresentative === null) anyRepresentative = b.id;
          if (ACTIVE_STATUSES.has(b.status)) {
            active_count += 1;
            if (activeRepresentative === null) activeRepresentative = b.id;
          }
        }

        const dayKey = format(day, "yyyy-MM-dd");
        const list = result.get(dayKey) ?? [];
        list.push({
          kind: "event",
          key: `rule-${rule.id}-${dayKey}`,
          startDate: ruleStart,
          endDate: ruleEnd,
          duration_minutes: Math.max(
            15,
            Math.round((ruleEnd.getTime() - ruleStart.getTime()) / 60000)
          ),
          name: rule.label?.trim() || "Weekly window",
          active_count,
          min_required: hasConfig ? minTotal : 0,
          max_allowed: hasConfig ? maxTotal : 0,
          has_config: hasConfig,
          representative_booking_id: activeRepresentative ?? anyRepresentative,
          event_cancelled: false,
          service_count: rule.service_config?.length ?? 0,
          source: "rule",
          source_id: rule.id,
          occurrence_date: dayKey,
        });
        result.set(dayKey, list);
      }
    }

    // 3) Per-(time, service) groups for any booking that wasn't absorbed by
    //    a specific-date event or weekly-rule card.
    const orphanMap = new Map<string, SlotGroup>();
    for (const b of bookings) {
      if (coveredBookingIds.has(b.id)) continue;
      const startDate = new Date(b.scheduled_at);
      const key = `slot|${b.scheduled_at}|${b.appointment_type_id}`;
      let group = orphanMap.get(key);
      if (!group) {
        const limits = findOrphanLimits(
          startDate,
          b.appointment_type_id,
          availabilityRules
        );
        group = {
          kind: "slot",
          key,
          startDate,
          appointment_type_id: b.appointment_type_id,
          service_name: b.appointment_type_name ?? "Unknown",
          duration_minutes: b.duration_minutes ?? 30,
          active_count: 0,
          min_required: limits.min,
          max_allowed: limits.max,
          representative_booking_id: b.id,
          event_cancelled: false,
        };
        orphanMap.set(key, group);
      }
      if (ACTIVE_STATUSES.has(b.status)) {
        group.active_count += 1;
        group.representative_booking_id = b.id;
      }
    }
    for (const group of orphanMap.values()) {
      const dayKey = format(group.startDate, "yyyy-MM-dd");
      const list = result.get(dayKey) ?? [];
      list.push(group);
      result.set(dayKey, list);
    }

    // Sort cards within each day by start time
    for (const list of result.values()) {
      list.sort((a, b) => a.startDate.getTime() - b.startDate.getTime());
    }

    return result;
  }, [bookings, availabilityRules, specificDateSlots, weekStart]);

  const today = useMemo(() => new Date(), []);

  function isDayBlocked(day: Date): boolean {
    return blockedDates.some((bd) => {
      const from = parseISO(bd.date_from);
      const to = parseISO(bd.date_to);
      return isWithinInterval(day, { start: from, end: to });
    });
  }

  function getCardPosition(card: DayCard) {
    const d = card.startDate;
    const minutesSinceStart = d.getHours() * 60 + d.getMinutes() - HOUR_START * 60;
    if (minutesSinceStart < 0) return null;
    const top = (minutesSinceStart / 30) * ROW_HEIGHT;
    const height = Math.max(
      (card.duration_minutes / 30) * ROW_HEIGHT - 2,
      ROW_HEIGHT - 2
    );
    return { top, height };
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-96 text-muted-foreground">
        Loading...
      </div>
    );
  }

  return (
    <div className="border rounded-lg overflow-auto bg-background">
      <div
        className="grid min-w-[800px]"
        style={{ gridTemplateColumns: "64px repeat(7, 1fr)" }}
      >
        {/* Header */}
        <div className="sticky top-0 z-20 bg-muted border-b p-2" />
        {days.map((day) => {
          const blocked = isDayBlocked(day);
          return (
            <div
              key={day.toISOString()}
              className={cn(
                "sticky top-0 z-20 border-b border-l p-2 text-center text-sm font-medium",
                blocked ? "bg-red-50" : isToday(day) ? "bg-primary/10" : "bg-muted"
              )}
            >
              <div className="text-muted-foreground">{format(day, "EEE")}</div>
              <div
                className={cn(
                  "text-lg",
                  blocked && "text-red-500",
                  isToday(day) && !blocked && "text-primary font-bold"
                )}
              >
                {format(day, "d")}
              </div>
              {blocked && (
                <div className="text-[10px] text-red-500 font-medium">BLOCKED</div>
              )}
            </div>
          );
        })}

        {/* Time gutter */}
        <div className="relative">
          {timeSlots.map((slot, i) => (
            <div
              key={i}
              className="border-b text-xs text-muted-foreground pr-2 text-right"
              style={{ height: ROW_HEIGHT }}
            >
              {slot.label && (
                <span className="relative -top-2">{slot.label}</span>
              )}
            </div>
          ))}
        </div>

        {/* Day columns */}
        {days.map((day) => {
          const dayKey = format(day, "yyyy-MM-dd");
          const cards = cardsByDay.get(dayKey) ?? [];
          const blocked = isDayBlocked(day);

          return (
            <div
              key={day.toISOString()}
              className={cn("relative border-l")}
              style={{ height: TOTAL_SLOTS * ROW_HEIGHT }}
            >
              {timeSlots.map((_, i) => (
                <div
                  key={i}
                  className={cn(
                    "absolute w-full border-b",
                    i % 2 === 0 ? "border-border" : "border-border/40"
                  )}
                  style={{ top: i * ROW_HEIGHT }}
                />
              ))}

              {blocked && <div className="absolute inset-0 bg-red-50/60 z-[1]" />}

              {isToday(day) && !blocked && (
                <div className="absolute inset-0 bg-primary/5 z-0" />
              )}

              {cards.map((card) => (
                <CardCell
                  key={card.key}
                  card={card}
                  pos={getCardPosition(card)}
                  today={today}
                  onOpen={(target) => navigate(target)}
                />
              ))}
            </div>
          );
        })}
      </div>

      <div className="flex flex-wrap items-center gap-4 border-t bg-muted/30 px-3 py-2 text-[11px] text-muted-foreground">
        <span className="flex items-center gap-1">
          <Repeat className="h-3 w-3" />
          Recurring
        </span>
        <span className="flex items-center gap-1">
          <CalendarDays className="h-3 w-3" />
          One-time
        </span>
        <span className="flex items-center gap-1">
          <span className="h-3 w-3 rounded border border-blue-300 bg-blue-100" />
          Filled
        </span>
        <span className="flex items-center gap-1">
          <span className="h-3 w-3 rounded border border-amber-300 bg-amber-100" />
          Below minimum
        </span>
        <span className="flex items-center gap-1">
          <span className="h-3 w-3 rounded border border-red-300 bg-red-100" />
          <AlertTriangle className="h-3 w-3 text-red-600" />
          Within {ALERT_DAYS_AHEAD} days &amp; below minimum
        </span>
        <span className="flex items-center gap-1">
          <span className="h-3 w-3 rounded border border-gray-300 bg-gray-100" />
          Event cancelled
        </span>
      </div>
    </div>
  );
}

interface CardCellProps {
  card: DayCard;
  pos: { top: number; height: number } | null;
  today: Date;
  /** Receives a router path — booking detail, specific-event roster, or rule occurrence roster. */
  onOpen: (target: string) => void;
}

function CardCell({ card, pos, today, onOpen }: CardCellProps) {
  if (!pos) return null;

  const daysAway = differenceInCalendarDays(card.startDate, today);
  const understaffed =
    card.min_required > 0 && card.active_count < card.min_required;
  const showAlert =
    understaffed && daysAway >= 0 && daysAway <= ALERT_DAYS_AHEAD;

  const tone = card.event_cancelled
    ? "bg-gray-100 border-gray-300 text-gray-500 line-through"
    : showAlert
      ? "bg-red-100 border-red-300 text-red-900"
      : understaffed
        ? "bg-amber-100 border-amber-300 text-amber-900"
        : "bg-blue-100 border-blue-300 text-blue-900";

  let counter: string;
  if (card.kind === "event") {
    if (card.has_config && card.min_required > 0) {
      const needed = Math.max(0, card.min_required - card.active_count);
      counter = needed > 0
        ? `${card.active_count}/${card.min_required} min · need ${needed} more`
        : `${card.active_count}/${card.max_allowed || card.min_required} booked`;
    } else {
      counter = `${card.active_count} booked`;
    }
  } else {
    const needed = Math.max(0, card.min_required - card.active_count);
    counter = needed > 0
      ? `${card.active_count}/${card.max_allowed} · need ${needed} more`
      : `${card.active_count}/${card.max_allowed} booked`;
  }

  const timeRange =
    card.kind === "event"
      ? fmtTimeRange(format(card.startDate, "HH:mm"), format(card.endDate, "HH:mm"))
      : `${format(card.startDate, "h:mm a")}${
          card.duration_minutes ? ` (${card.duration_minutes}m)` : ""
        }`;

  const titleLine =
    card.kind === "event" ? card.name : card.service_name;

  const tooltip = showAlert
    ? `${counter} — ${
        daysAway === 0 ? "today" : daysAway === 1 ? "tomorrow" : `in ${daysAway} days`
      }`
    : counter;

  // Prefer linking to a specific booking when there is one (so the focal
  // booking + its action buttons show up on the detail page). Otherwise fall
  // back to the source-based event roster route so empty events still open.
  let target: string | null = null;
  if (card.representative_booking_id) {
    target = `/bookings/${card.representative_booking_id}`;
  } else if (card.kind === "event") {
    target = card.source === "specific"
      ? `/events/specific/${card.source_id}`
      : `/events/rule/${card.source_id}/${card.occurrence_date}`;
  }
  const clickable = target !== null;
  const isRecurring = card.kind === "event" && card.source === "rule";

  return (
    <button
      className={cn(
        "absolute left-1 right-1 rounded border px-1.5 py-0.5 text-left text-xs overflow-hidden z-10 transition-opacity",
        tone,
        clickable ? "cursor-pointer hover:opacity-80" : "cursor-default opacity-90"
      )}
      style={{ top: pos.top, height: pos.height }}
      title={tooltip}
      disabled={!clickable}
      onClick={() => {
        if (target) onOpen(target);
      }}
    >
      <div className="flex items-center gap-1 font-semibold leading-tight">
        {showAlert && (
          <AlertTriangle className="h-3 w-3 shrink-0 text-red-600" />
        )}
        {card.kind === "event" && (
          isRecurring ? (
            <Repeat
              className="h-3 w-3 shrink-0 opacity-70"
              aria-label="Recurring (weekly)"
            />
          ) : (
            <CalendarDays
              className="h-3 w-3 shrink-0 opacity-70"
              aria-label="One-time event"
            />
          )
        )}
        <span className="truncate">{titleLine}</span>
      </div>
      {pos.height > ROW_HEIGHT - 6 && (
        <div className="truncate text-[10px] opacity-80 leading-tight">
          {timeRange}
          {card.kind === "event" && card.service_count > 0
            ? ` · ${card.service_count} service${card.service_count === 1 ? "" : "s"}`
            : ""}
        </div>
      )}
      <div className="truncate text-[11px] leading-tight">{counter}</div>
    </button>
  );
}
