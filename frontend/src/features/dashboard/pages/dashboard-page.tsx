import { useMemo } from "react";
import { CalendarRange, Inbox } from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { cn } from "@/lib/utils";
import {
  useAlerts,
  useDashboardSummary,
  useRecommendations,
  useWeeklySlotStatuses,
} from "../hooks/use-dashboard";
import { useAlertState } from "../lib/alert-state";
import { AlertsFeed } from "../components/alerts-feed";
import { LiveEventsPanel } from "../components/live-events-panel";
import { ThisWeekStrip } from "../components/this-week-strip";
import { DashboardGreeting } from "../components/dashboard-greeting";
import { DashboardKpiRow } from "../components/dashboard-kpi-row";
import { PlanningView } from "../components/planning-view";
import { aggregateBySchedule } from "../lib/aggregate";

/**
 * Dashboard — two-view redesign (Phase 1).
 *
 *   Tab 1 · Needs You Now (default)
 *     - Live events (when running)
 *     - Unified alerts feed (decisions, regardless of horizon)
 *     - This week's operational glance (Today / Tomorrow / Rest of week)
 *
 *   Tab 2 · Planning (1–60 days, ships Phase 2)
 *     - Placeholder for now
 *
 * Snooze + dismiss live in localStorage until Phase 3 adds a server table.
 */
export function DashboardPage() {
  const summary = useDashboardSummary();
  const weekly = useWeeklySlotStatuses(0);
  const { data: alerts } = useAlerts();
  const { data: recommendations } = useRecommendations();
  const alertState = useAlertState();

  const aggregated = useMemo(
    () => aggregateBySchedule(weekly.data ?? []),
    [weekly.data],
  );
  const needingVolunteers = useMemo(
    () => aggregated.filter((e) => e.any_needs_more).length,
    [aggregated],
  );

  // Visible alert count (after subtracting locally-dismissed + snoozed).
  const visibleAlertCount = useMemo(() => {
    if (!alerts) return 0;
    const now = Date.now();
    return alerts.filter((a) => {
      const snoozedUntil = alertState.snoozedUntil(a.id);
      if (snoozedUntil && snoozedUntil > now) return false;
      if (alertState.dismissedRecord(a.id)) return false;
      return true;
    }).length;
  }, [alerts, alertState]);

  const recurringCount = useMemo(
    () => aggregated.filter((e) => e.source === "recurring").length,
    [aggregated],
  );
  const oneTimeCount = useMemo(
    () => aggregated.filter((e) => e.source === "one_time").length,
    [aggregated],
  );

  return (
    <div className="space-y-6">
      <DashboardGreeting
        eventsThisWeek={aggregated.length}
        needingVolunteers={needingVolunteers}
        isLoading={summary.isLoading || weekly.isLoading}
      />

      <DashboardKpiRow
        totalVolunteers={summary.data?.total_volunteers}
        eventsThisWeek={aggregated.length}
        recurringCount={recurringCount}
        oneTimeCount={oneTimeCount}
        openSlots={summary.data?.slots_needing_bookings}
        monthlyBookings={summary.data?.monthly_bookings}
        isLoading={summary.isLoading || weekly.isLoading}
      />

      <Tabs defaultValue="now" className="space-y-5">
        <TabsList className="bg-muted/60">
          <TabsTrigger value="now" className="gap-2">
            <Inbox className="h-3.5 w-3.5" />
            Needs you now
            {visibleAlertCount > 0 && (
              <CountBadge value={visibleAlertCount} tone="urgent" />
            )}
          </TabsTrigger>
          <TabsTrigger value="planning" className="gap-2">
            <CalendarRange className="h-3.5 w-3.5" />
            Planning
            {recommendations && recommendations.length > 0 && (
              <CountBadge value={recommendations.length} tone="info" />
            )}
          </TabsTrigger>
        </TabsList>

        <TabsContent value="now" className="space-y-6">
          {/* Live events — auto-hides when nothing's live */}
          <LiveEventsPanel />

          {/* Unified alerts feed */}
          <section>
            <SectionHeader
              eyebrow="Decisions"
              title="Things that need a call from you"
              hint="Resolve on the CTA, snooze, or dismiss with a reason."
            />
            <AlertsFeed />
          </section>

          {/* This week */}
          <section>
            <SectionHeader
              eyebrow="This week"
              title="What's happening soon"
              hint="Operational glance — fill bars are live; click a card to open."
            />
            <ThisWeekStrip />
          </section>
        </TabsContent>

        <TabsContent value="planning">
          <PlanningView />
        </TabsContent>
      </Tabs>
    </div>
  );
}

function SectionHeader({
  eyebrow,
  title,
  hint,
}: {
  eyebrow: string;
  title: string;
  hint?: string;
}) {
  return (
    <div className="mb-3 flex items-baseline gap-3">
      <div>
        <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
          {eyebrow}
        </p>
        <h2 className="text-base font-semibold">{title}</h2>
      </div>
      {hint && (
        <p className="ml-auto hidden text-xs text-muted-foreground sm:block">
          {hint}
        </p>
      )}
    </div>
  );
}

function CountBadge({ value, tone }: { value: number; tone: "urgent" | "info" }) {
  return (
    <span
      className={cn(
        "ml-1 inline-flex h-5 min-w-5 items-center justify-center rounded-full px-1.5 text-[10px] font-bold tabular-nums",
        tone === "urgent"
          ? "bg-amber-500 text-white"
          : "bg-sky-500 text-white",
      )}
    >
      {value}
    </span>
  );
}
