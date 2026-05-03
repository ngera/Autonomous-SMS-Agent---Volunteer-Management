import { useMemo } from "react";
import { DashboardGreeting } from "../components/dashboard-greeting";
import { DashboardKpiRow } from "../components/dashboard-kpi-row";
import { WeeklyScheduleList } from "../components/weekly-schedule-list";
import { NeedsAttentionPanel } from "../components/needs-attention-panel";
import { QuickActionsPanel } from "../components/quick-actions-panel";
import { UpcomingOneTimeEvents } from "../components/upcoming-one-time-events";
import {
  useDashboardSummary,
  useWeeklySlotStatuses,
} from "../hooks/use-dashboard";
import { aggregateBySchedule, fillPercent } from "../lib/aggregate";

export function DashboardPage() {
  const summary = useDashboardSummary();
  const weeklySlots = useWeeklySlotStatuses(0);

  const aggregated = useMemo(
    () => aggregateBySchedule(weeklySlots.data ?? []),
    [weeklySlots.data]
  );

  const recurringCount = useMemo(
    () => aggregated.filter((e) => e.source === "recurring").length,
    [aggregated]
  );
  const oneTimeCount = useMemo(
    () => aggregated.filter((e) => e.source === "one_time").length,
    [aggregated]
  );
  const needingVolunteers = useMemo(
    () => aggregated.filter((e) => e.any_needs_more).length,
    [aggregated]
  );
  const understaffed = useMemo(() => {
    const candidates = aggregated.filter((e) => e.any_needs_more);
    if (candidates.length === 0) return null;
    return candidates.reduce((worst, ev) =>
      fillPercent(ev.booked, ev.max_allowed) <
      fillPercent(worst.booked, worst.max_allowed)
        ? ev
        : worst
    );
  }, [aggregated]);
  const oneTimeEvents = useMemo(
    () => aggregated.filter((e) => e.source === "one_time"),
    [aggregated]
  );

  const isLoading = summary.isLoading || weeklySlots.isLoading;

  return (
    <div className="space-y-6">
      <DashboardGreeting
        eventsThisWeek={aggregated.length}
        needingVolunteers={needingVolunteers}
        isLoading={isLoading}
      />

      <DashboardKpiRow
        totalVolunteers={summary.data?.total_volunteers}
        eventsThisWeek={aggregated.length}
        recurringCount={recurringCount}
        oneTimeCount={oneTimeCount}
        openSlots={summary.data?.slots_needing_bookings}
        monthlyBookings={summary.data?.monthly_bookings}
        isLoading={isLoading}
      />

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <WeeklyScheduleList
            events={aggregated}
            isLoading={weeklySlots.isLoading}
          />
          <UpcomingOneTimeEvents
            events={oneTimeEvents}
            isLoading={weeklySlots.isLoading}
          />
        </div>

        <div className="space-y-6">
          <NeedsAttentionPanel
            understaffed={understaffed}
            unreviewedSuspensions={summary.data?.unreviewed_suspensions_count ?? 0}
            suspendedOrBanned={summary.data?.suspended_or_banned_count ?? 0}
            isLoading={isLoading}
          />
          <QuickActionsPanel />
        </div>
      </div>
    </div>
  );
}
