import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Plus, ChevronLeft, ChevronRight, Calendar, List } from "lucide-react";
import {
  addDays,
  startOfWeek,
  endOfWeek,
  addWeeks,
  subWeeks,
  format,
  parseISO,
} from "date-fns";
import { PageHeader } from "@/components/shared/page-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/hooks/use-auth";
import { AdminRole } from "@/types/enums";
import { WeeklyCalendar } from "../components/weekly-calendar";
import { EventsTable } from "../components/events-table";
import { useBookings } from "../hooks/use-bookings";
import {
  useAvailabilityRules,
  useBlockedDates,
  useSpecificDateSlots,
} from "@/features/availability/hooks/use-availability";

type ViewMode = "calendar" | "list";

export function BookingsPage() {
  const navigate = useNavigate();
  const { hasRole } = useAuth();
  const [view, setView] = useState<ViewMode>("calendar");

  // Calendar state
  const [weekStart, setWeekStart] = useState(() =>
    startOfWeek(new Date(), { weekStartsOn: 0 })
  );
  const weekEnd = endOfWeek(weekStart, { weekStartsOn: 0 });

  // List state (events list) — default to a 30-day window from today.
  const today = useMemo(() => new Date(), []);
  const [listFrom, setListFrom] = useState<string>(format(today, "yyyy-MM-dd"));
  const [listTo, setListTo] = useState<string>(format(addDays(today, 30), "yyyy-MM-dd"));

  const listFromDate = useMemo(() => parseISO(listFrom), [listFrom]);
  const listToDate = useMemo(() => {
    const d = parseISO(listTo);
    // include the entire end day
    return new Date(d.getFullYear(), d.getMonth(), d.getDate(), 23, 59, 59);
  }, [listTo]);

  const calendarBookings = useBookings(
    view === "calendar"
      ? {
          page: 1,
          page_size: 200,
          date_from: format(weekStart, "yyyy-MM-dd'T'00:00:00"),
          date_to: format(weekEnd, "yyyy-MM-dd'T'23:59:59"),
        }
      : { page: 1, page_size: 1 }
  );

  const listBookings = useBookings(
    view === "list"
      ? {
          page: 1,
          page_size: 500, // pull all bookings in range so event counts are accurate
          date_from: `${listFrom}T00:00:00`,
          date_to: `${listTo}T23:59:59`,
        }
      : { page: 1, page_size: 1 }
  );

  const availabilityRules = useAvailabilityRules();
  const blockedDates = useBlockedDates();
  const specificDateSlots = useSpecificDateSlots();

  return (
    <div className="space-y-4">
      <PageHeader
        title="Calendar"
        description="Manage all appointments and events."
        actions={
          <div className="flex items-center gap-2">
            <div className="flex border rounded-md overflow-hidden">
              <Button
                variant={view === "calendar" ? "default" : "ghost"}
                size="sm"
                className="rounded-none"
                onClick={() => setView("calendar")}
              >
                <Calendar className="h-4 w-4 mr-1" />
                Calendar
              </Button>
              <Button
                variant={view === "list" ? "default" : "ghost"}
                size="sm"
                className="rounded-none"
                onClick={() => setView("list")}
              >
                <List className="h-4 w-4 mr-1" />
                List
              </Button>
            </div>
            {hasRole(AdminRole.MANAGER) && (
              <>
                <Button onClick={() => navigate("/bookings/new")}>
                  <Plus className="mr-2 h-4 w-4" />
                  New Appt
                </Button>
                <Button
                  variant="outline"
                  onClick={() => navigate("/availability?tab=specific")}
                >
                  <Plus className="mr-2 h-4 w-4" />
                  Add event
                </Button>
              </>
            )}
          </div>
        }
      />

      {view === "calendar" && (
        <>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setWeekStart(subWeeks(weekStart, 1))}
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() =>
                setWeekStart(startOfWeek(new Date(), { weekStartsOn: 0 }))
              }
            >
              Today
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setWeekStart(addWeeks(weekStart, 1))}
            >
              <ChevronRight className="h-4 w-4" />
            </Button>
            <span className="text-sm font-medium text-muted-foreground ml-2">
              {format(weekStart, "MMM d")} – {format(weekEnd, "MMM d, yyyy")}
            </span>
          </div>

          <div className="flex items-center gap-4 text-xs">
            <div className="flex items-center gap-1">
              <div className="w-3 h-3 rounded bg-green-100 border border-green-300" />
              <span>Available</span>
            </div>
            <div className="flex items-center gap-1">
              <div className="w-3 h-3 rounded bg-blue-100 border border-blue-300" />
              <span>Booked</span>
            </div>
            <div className="flex items-center gap-1">
              <div className="w-3 h-3 rounded bg-red-100 border border-red-300" />
              <span>Blocked</span>
            </div>
          </div>

          <WeeklyCalendar
            weekStart={weekStart}
            bookings={calendarBookings.data?.items ?? []}
            availabilityRules={availabilityRules.data ?? []}
            specificDateSlots={specificDateSlots.data ?? []}
            blockedDates={blockedDates.data ?? []}
            isLoading={calendarBookings.isLoading}
          />
        </>
      )}

      {view === "list" && (
        <>
          <div className="flex flex-wrap items-end gap-3">
            <div className="space-y-1">
              <Label className="text-xs">From</Label>
              <Input
                type="date"
                value={listFrom}
                onChange={(e) => setListFrom(e.target.value)}
                className="h-9 w-40"
              />
            </div>
            <div className="space-y-1">
              <Label className="text-xs">To</Label>
              <Input
                type="date"
                value={listTo}
                onChange={(e) => setListTo(e.target.value)}
                className="h-9 w-40"
              />
            </div>
          </div>

          <EventsTable
            isLoading={
              listBookings.isLoading ||
              availabilityRules.isLoading ||
              specificDateSlots.isLoading
            }
            fromDate={listFromDate}
            toDate={listToDate}
            availabilityRules={availabilityRules.data ?? []}
            specificDateSlots={specificDateSlots.data ?? []}
            bookings={listBookings.data?.items ?? []}
          />
        </>
      )}
    </div>
  );
}
