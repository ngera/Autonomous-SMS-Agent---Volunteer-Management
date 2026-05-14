import { useMemo } from "react";
import { useNavigate } from "react-router-dom";
import {
  addDays,
  differenceInCalendarDays,
  format,
  getDay,
} from "date-fns";
import { AlertTriangle, CalendarDays, Repeat } from "lucide-react";
import { DataTable, type Column } from "@/components/shared/data-table";
import { Badge } from "@/components/ui/badge";
import { formatDate } from "@/lib/utils";
import { BookingStatus } from "@/types/enums";
import type {
  AvailabilityRuleResponse,
  BookingResponse,
  SpecificDateSlotResponse,
} from "@/types/api";

const ACTIVE_STATUSES = new Set<string>([
  BookingStatus.SCHEDULED,
  BookingStatus.RESCHEDULED,
  BookingStatus.COMPLETED,
]);

const ALERT_DAYS_AHEAD = 2;

function toRuleDow(dateFnsDay: number): number {
  return dateFnsDay === 0 ? 6 : dateFnsDay - 1;
}

function trimTime(t: string): string {
  return t.length >= 5 ? t.slice(0, 5) : t;
}

function parseEventDateTime(dateStr: string, time: string): Date {
  const [y, m, d] = dateStr.split("-").map(Number);
  const [hh, mm, ss] = time.split(":").map(Number);
  return new Date(y, m - 1, d, hh, mm, ss || 0);
}

export interface EventRow {
  key: string;
  source: "specific" | "rule";
  source_id: string;
  date: string; // yyyy-MM-dd
  startDate: Date;
  endDate: Date;
  name: string;
  start_time: string;
  end_time: string;
  active_count: number;
  min_required: number;
  max_allowed: number;
  has_config: boolean;
  event_cancelled: boolean;
  service_count: number;
}

interface EventsTableProps {
  isLoading: boolean;
  fromDate: Date;
  toDate: Date; // inclusive
  availabilityRules: AvailabilityRuleResponse[];
  specificDateSlots: SpecificDateSlotResponse[];
  bookings: BookingResponse[];
}

export function EventsTable({
  isLoading,
  fromDate,
  toDate,
  availabilityRules,
  specificDateSlots,
  bookings,
}: EventsTableProps) {
  const navigate = useNavigate();

  const events = useMemo<EventRow[]>(() => {
    const rows: EventRow[] = [];

    // 1) Specific-date events in range
    for (const sds of specificDateSlots) {
      const eventStart = parseEventDateTime(sds.date, sds.start_time);
      const eventEnd = parseEventDateTime(sds.date, sds.end_time);
      if (eventStart < fromDate || eventStart > toDate) continue;

      const allowedIds =
        sds.service_config && sds.service_config.length > 0
          ? new Set(sds.service_config.map((c) => c.appointment_type_id))
          : null;
      const hasConfig = (sds.service_config?.length ?? 0) > 0;
      const minTotal = (sds.service_config ?? []).reduce(
        (s, c) => s + (c.min_required ?? 1),
        0
      );
      const maxTotal = (sds.service_config ?? []).reduce(
        (s, c) => s + (c.max_allowed ?? c.min_required ?? 1),
        0
      );

      let active = 0;
      for (const b of bookings) {
        const bDate = new Date(b.scheduled_at);
        if (bDate < eventStart || bDate > eventEnd) continue;
        if (allowedIds !== null && !allowedIds.has(b.appointment_type_id))
          continue;
        if (ACTIVE_STATUSES.has(b.status)) active += 1;
      }

      rows.push({
        key: `specific-${sds.id}`,
        source: "specific",
        source_id: sds.id,
        date: sds.date,
        startDate: eventStart,
        endDate: eventEnd,
        name: sds.label?.trim() || "Event",
        start_time: sds.start_time,
        end_time: sds.end_time,
        active_count: active,
        min_required: hasConfig ? minTotal : 0,
        max_allowed: hasConfig ? maxTotal : 0,
        has_config: hasConfig,
        event_cancelled: !sds.is_active,
        service_count: sds.service_config?.length ?? 0,
      });
    }

    // 2) Weekly-rule occurrences for each date in range
    const totalDays = Math.max(
      0,
      differenceInCalendarDays(toDate, fromDate) + 1
    );
    for (let i = 0; i < totalDays; i++) {
      const day = addDays(fromDate, i);
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

        const allowedIds =
          rule.service_config && rule.service_config.length > 0
            ? new Set(rule.service_config.map((c) => c.appointment_type_id))
            : null;
        const hasConfig = (rule.service_config?.length ?? 0) > 0;
        const minTotal = (rule.service_config ?? []).reduce(
          (s, c) => s + (c.min_required ?? 1),
          0
        );
        const maxTotal = (rule.service_config ?? []).reduce(
          (s, c) => s + (c.max_allowed ?? c.min_required ?? 1),
          0
        );

        let active = 0;
        for (const b of bookings) {
          const bDate = new Date(b.scheduled_at);
          if (bDate < ruleStart || bDate > ruleEnd) continue;
          if (allowedIds !== null && !allowedIds.has(b.appointment_type_id))
            continue;
          if (ACTIVE_STATUSES.has(b.status)) active += 1;
        }

        const dayKey = format(day, "yyyy-MM-dd");
        rows.push({
          key: `rule-${rule.id}-${dayKey}`,
          source: "rule",
          source_id: rule.id,
          date: dayKey,
          startDate: ruleStart,
          endDate: ruleEnd,
          name: rule.label?.trim() || "Weekly window",
          start_time: rule.start_time,
          end_time: rule.end_time,
          active_count: active,
          min_required: hasConfig ? minTotal : 0,
          max_allowed: hasConfig ? maxTotal : 0,
          has_config: hasConfig,
          event_cancelled: false,
          service_count: rule.service_config?.length ?? 0,
        });
      }
    }

    rows.sort((a, b) => a.startDate.getTime() - b.startDate.getTime());
    return rows;
  }, [fromDate, toDate, specificDateSlots, availabilityRules, bookings]);

  const today = useMemo(() => new Date(), []);

  const columns: Column<EventRow>[] = [
    {
      key: "date",
      header: "Date",
      render: (e) => formatDate(e.date),
    },
    {
      key: "name",
      header: "Event",
      render: (e) => (
        <div className="flex items-center gap-2">
          {e.source === "rule" ? (
            <Repeat
              className="h-3.5 w-3.5 shrink-0 text-muted-foreground"
              aria-label="Recurring"
            />
          ) : (
            <CalendarDays
              className="h-3.5 w-3.5 shrink-0 text-muted-foreground"
              aria-label="One-time"
            />
          )}
          <span className={e.event_cancelled ? "line-through text-muted-foreground" : ""}>
            {e.name}
          </span>
          {e.event_cancelled && (
            <Badge variant="outline" className="text-[10px] uppercase">
              Cancelled
            </Badge>
          )}
        </div>
      ),
    },
    {
      key: "time",
      header: "Time",
      render: (e) => `${trimTime(e.start_time)} – ${trimTime(e.end_time)}`,
    },
    {
      key: "type",
      header: "Type",
      render: (e) => (
        <Badge variant="secondary" className="text-[10px] uppercase">
          {e.source === "rule" ? "Recurring" : "One-time"}
        </Badge>
      ),
    },
    {
      key: "booked",
      header: "Booked / Min",
      className: "text-right tabular-nums",
      render: (e) =>
        e.has_config
          ? `${e.active_count} / ${e.min_required}`
          : `${e.active_count}`,
    },
    {
      key: "max",
      header: "Max",
      className: "text-right tabular-nums",
      render: (e) => (e.has_config ? e.max_allowed : "—"),
    },
    {
      key: "needs",
      header: "Status",
      render: (e) => {
        if (e.event_cancelled) return null;
        if (!e.has_config) return null;
        const needed = Math.max(0, e.min_required - e.active_count);
        if (needed === 0) {
          return (
            <Badge variant="secondary" className="text-[10px]">
              Filled
            </Badge>
          );
        }
        const daysAway = differenceInCalendarDays(e.startDate, today);
        const alert = daysAway >= 0 && daysAway <= ALERT_DAYS_AHEAD;
        return (
          <Badge
            variant="outline"
            className={
              alert
                ? "text-[10px] border-red-300 bg-red-50 text-red-900 dark:border-red-900 dark:bg-red-950 dark:text-red-200"
                : "text-[10px] border-amber-300 bg-amber-50 text-amber-900 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-200"
            }
          >
            {alert && <AlertTriangle className="mr-1 inline h-3 w-3" />}
            need {needed} more
          </Badge>
        );
      },
    },
  ];

  return (
    <DataTable
      columns={columns}
      data={events}
      isLoading={isLoading}
      emptyMessage="No events in this date range."
      onRowClick={(e) =>
        navigate(
          e.source === "specific"
            ? `/events/specific/${e.source_id}`
            : `/events/rule/${e.source_id}/${e.date}`
        )
      }
    />
  );
}
