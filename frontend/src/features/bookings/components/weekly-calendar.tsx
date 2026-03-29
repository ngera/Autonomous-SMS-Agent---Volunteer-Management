import { useNavigate } from "react-router-dom";
import { format, addDays, isSameDay, isToday, getDay, parseISO, isWithinInterval } from "date-fns";
import { cn, formatPhone } from "@/lib/utils";
import type { BookingResponse, AvailabilityRuleResponse, BlockedDateResponse } from "@/types/api";

const HOUR_START = 8; // 8 AM
const HOUR_END = 21; // 9 PM
const ROW_HEIGHT = 32; // px per 30-min slot
const TOTAL_SLOTS = (HOUR_END - HOUR_START) * 2;

const STATUS_COLORS: Record<string, string> = {
  SCHEDULED: "bg-blue-100 border-blue-300 text-blue-900",
  RESCHEDULED: "bg-amber-100 border-amber-300 text-amber-900",
  COMPLETED: "bg-green-100 border-green-300 text-green-900",
  CANCELLED: "bg-gray-100 border-gray-300 text-gray-500 line-through",
  NO_SHOW: "bg-red-100 border-red-300 text-red-900",
};

// date-fns getDay: 0=Sunday, but availability rules use 0=Monday
// Convert date-fns day (0=Sun) to rule day_of_week (0=Mon)
function toRuleDow(dateFnsDay: number): number {
  return dateFnsDay === 0 ? 6 : dateFnsDay - 1;
}

interface WeeklyCalendarProps {
  weekStart: Date;
  bookings: BookingResponse[];
  availabilityRules: AvailabilityRuleResponse[];
  blockedDates: BlockedDateResponse[];
  isLoading: boolean;
}

export function WeeklyCalendar({
  weekStart,
  bookings,
  availabilityRules,
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

  function isDayBlocked(day: Date): boolean {
    return blockedDates.some((bd) => {
      const from = parseISO(bd.date_from);
      const to = parseISO(bd.date_to);
      return isWithinInterval(day, { start: from, end: to });
    });
  }

  function getAvailabilityForDay(day: Date): AvailabilityRuleResponse | undefined {
    const ruleDow = toRuleDow(getDay(day));
    return availabilityRules.find((r) => r.day_of_week === ruleDow && r.is_active);
  }

  function getAvailabilityPosition(rule: AvailabilityRuleResponse) {
    const [startH, startM] = rule.start_time.split(":").map(Number);
    const [endH, endM] = rule.end_time.split(":").map(Number);
    const startMinutes = startH * 60 + startM - HOUR_START * 60;
    const endMinutes = endH * 60 + endM - HOUR_START * 60;
    if (startMinutes < 0 || endMinutes <= startMinutes) return null;
    const top = (startMinutes / 30) * ROW_HEIGHT;
    const height = ((endMinutes - startMinutes) / 30) * ROW_HEIGHT;
    return { top, height };
  }

  function getBookingsForDay(day: Date) {
    return bookings.filter((b) => {
      const d = new Date(b.scheduled_at);
      return isSameDay(d, day);
    });
  }

  function getBookingPosition(booking: BookingResponse) {
    const d = new Date(booking.scheduled_at);
    const minutesSinceStart = d.getHours() * 60 + d.getMinutes() - HOUR_START * 60;
    if (minutesSinceStart < 0) return null;
    const top = (minutesSinceStart / 30) * ROW_HEIGHT;
    const durationMin = booking.duration_minutes ?? 30;
    const height = Math.max((durationMin / 30) * ROW_HEIGHT - 2, ROW_HEIGHT - 2);
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
          const dayBookings = getBookingsForDay(day);
          const blocked = isDayBlocked(day);
          const rule = getAvailabilityForDay(day);
          const availPos = rule ? getAvailabilityPosition(rule) : null;

          return (
            <div
              key={day.toISOString()}
              className={cn("relative border-l")}
              style={{ height: TOTAL_SLOTS * ROW_HEIGHT }}
            >
              {/* Grid lines */}
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

              {/* Blocked day overlay */}
              {blocked && (
                <div className="absolute inset-0 bg-red-50/60 z-[1]" />
              )}

              {/* Available time window */}
              {!blocked && availPos && (
                <div
                  className="absolute left-0 right-0 bg-green-50 border-y border-green-200 z-[1]"
                  style={{ top: availPos.top, height: availPos.height }}
                />
              )}

              {/* Today highlight (only in non-available area) */}
              {isToday(day) && !blocked && (
                <div className="absolute inset-0 bg-primary/5 z-0" />
              )}

              {/* Booking cards */}
              {dayBookings.map((booking) => {
                const pos = getBookingPosition(booking);
                if (!pos) return null;
                const statusClass =
                  STATUS_COLORS[booking.status] ?? STATUS_COLORS.SCHEDULED;
                return (
                  <button
                    key={booking.id}
                    className={cn(
                      "absolute left-1 right-1 rounded border px-1.5 py-0.5 text-left text-xs cursor-pointer overflow-hidden z-10 hover:opacity-80 transition-opacity",
                      statusClass
                    )}
                    style={{ top: pos.top, height: pos.height }}
                    onClick={() => navigate(`/bookings/${booking.id}`)}
                  >
                    <div className="font-semibold truncate leading-tight">
                      {format(new Date(booking.scheduled_at), "h:mm a")}
                      {booking.duration_minutes ? ` (${booking.duration_minutes}m)` : ""}
                    </div>
                    <div className="truncate leading-tight">
                      {booking.contact_name || formatPhone(booking.contact_phone)}
                    </div>
                    {pos.height > ROW_HEIGHT && booking.appointment_type_name && (
                      <div className="truncate text-[10px] opacity-75 leading-tight">
                        {booking.appointment_type_name}
                      </div>
                    )}
                  </button>
                );
              })}
            </div>
          );
        })}
      </div>
    </div>
  );
}
