import { useEffect, useMemo, useState } from "react";
import { Activity, CalendarRange, ChevronDown, Inbox } from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { cn } from "@/lib/utils";
import {
  useAlerts,
  useDashboardSummary,
  usePlanning,
  useRecommendations,
  useUpcomingEvents,
  useWeeklySlotStatuses,
} from "../hooks/use-dashboard";
import { useAlertState } from "../lib/alert-state";
import { AlertsFeed } from "../components/alerts-feed";
import { AlertsDonut } from "../components/alerts-donut";
import { DonationsChart } from "../components/donations-chart";
import { HeadsUpChart, HeadsUpPreviewList } from "../components/heads-up-chart";
import { VolunteerHealthChart } from "../components/volunteer-health-chart";
import { DonorsChart } from "../components/donors-chart";
import { CapacityPulse } from "../components/capacity-pulse";
import { LiveEventsPanel } from "../components/live-events-panel";
import { DashboardGreeting } from "../components/dashboard-greeting";
import { DashboardKpiRow } from "../components/dashboard-kpi-row";
import { PlanningView } from "../components/planning-view";
import { aggregateBySchedule } from "../lib/aggregate";
import { useLiveEvents } from "../hooks/use-dashboard";
import {
  type AlertCategory,
  categoryFor,
  groupForCategory,
} from "../lib/alert-categories";
import type { PlanningCampaignSummary } from "../api";

// Any campaign not in a terminal state counts as "running". Terminal
// = completed / cancelled / failed.
const TERMINAL_CAMPAIGN_STATUSES = new Set(["completed", "cancelled", "failed"]);
function isCampaignRunning(c: PlanningCampaignSummary | null): boolean {
  if (!c) return false;
  return !TERMINAL_CAMPAIGN_STATUSES.has(c.status);
}

/**
 * Dashboard — chart-first redesign.
 *
 *   Tab 1 · Needs You Now (default)
 *     - Live events panel pinned at top when running (auto-hides otherwise).
 *     - Capacity Pulse chart + This Week event cards (left 2/3)
 *       Alerts Donut + category legend (right 1/3)
 *     - Alerts feed below, filtered by donut selection.
 *
 *   Tab 2 · Planning (T+8 → T+60)
 *     - Recommendations + horizon timeline.
 */
export function DashboardPage() {
  const summary = useDashboardSummary();
  const weekly = useWeeklySlotStatuses(0);
  const upcoming = useUpcomingEvents();
  const planning = usePlanning();
  const liveEvents = useLiveEvents();
  const { data: alerts } = useAlerts();
  const { data: recommendations } = useRecommendations();
  const alertState = useAlertState();

  // Lifted out of <Tabs> so the KPI row above can switch its
  // headline ("Events this week" vs "Events 15-60 days") based on
  // which tab the admin is looking at.
  const [tab, setTab] = useState<"now" | "planning" | "org_health">("now");

  const [alertCategory, setAlertCategory] =
    useState<AlertCategory | null>(null);
  // Heads-up bar selection is separate from the Decisions donut filter —
  // clicking a heads-up bar should drive the dummy preview list below
  // the chart, not retro-filter the Decisions feed.
  const [headsUpCategory, setHeadsUpCategory] =
    useState<AlertCategory | null>(null);

  // Persisted across reloads so admins who keep Decisions collapsed
  // don't have to re-collapse it every time they open the dashboard.
  // Decisions is open by default; Heads-up is closed by default
  // (informational items shouldn't fight for the admin's attention
  // when the action queue is the priority).
  const [decisionsOpen, setDecisionsOpen] = useState<boolean>(() => {
    if (typeof window === "undefined") return true;
    return localStorage.getItem("dashboard-decisions-open") !== "0";
  });
  useEffect(() => {
    try {
      localStorage.setItem(
        "dashboard-decisions-open",
        decisionsOpen ? "1" : "0",
      );
    } catch {
      // Quota / privacy mode — ignore.
    }
  }, [decisionsOpen]);
  // Heads-up section now lives on the Org Health tab, which is
  // entirely about looking — open by default. Admins who don't want
  // to see it can collapse and the preference persists.
  const [headsUpOpen, setHeadsUpOpen] = useState<boolean>(() => {
    if (typeof window === "undefined") return true;
    return localStorage.getItem("dashboard-heads-up-open") !== "0";
  });
  useEffect(() => {
    try {
      localStorage.setItem(
        "dashboard-heads-up-open",
        headsUpOpen ? "1" : "0",
      );
    } catch {
      // Quota / privacy mode — ignore.
    }
  }, [headsUpOpen]);

  const aggregated = useMemo(
    () => aggregateBySchedule(weekly.data ?? []),
    [weekly.data],
  );
  const needingVolunteers = useMemo(
    () => aggregated.filter((e) => e.any_needs_more).length,
    [aggregated],
  );

  const visibleAlerts = useMemo(() => {
    if (!alerts) return [];
    const now = Date.now();
    return alerts.filter((a) => {
      const snoozedUntil = alertState.snoozedUntil(a.id);
      if (snoozedUntil && snoozedUntil > now) return false;
      if (alertState.dismissedRecord(a.id)) return false;
      return true;
    });
  }, [alerts, alertState]);
  const visibleAlertCount = visibleAlerts.length;
  const { decisionsCount, headsUpCount, headsUpAlerts } = useMemo(() => {
    let d = 0;
    let h = 0;
    const hList: typeof visibleAlerts = [];
    for (const a of visibleAlerts) {
      if (groupForCategory(categoryFor(a)) === "decisions") {
        d += 1;
      } else {
        h += 1;
        hList.push(a);
      }
    }
    return { decisionsCount: d, headsUpCount: h, headsUpAlerts: hList };
  }, [visibleAlerts]);

  const hasLiveEvents = (liveEvents.data?.length ?? 0) > 0;

  const recurringCount = useMemo(
    () => aggregated.filter((e) => e.source === "recurring").length,
    [aggregated],
  );
  const oneTimeCount = useMemo(
    () => aggregated.filter((e) => e.source === "one_time").length,
    [aggregated],
  );
  // Total minimum staffing required this week, and how many of those
  // slots are still below minimum (the "open slots" headline number).
  const totalRequired = useMemo(
    () => aggregated.reduce((s, e) => s + e.min_required, 0),
    [aggregated],
  );
  const openMin = useMemo(
    () =>
      aggregated.reduce(
        (s, e) => s + Math.max(0, e.min_required - e.booked),
        0,
      ),
    [aggregated],
  );

  // Needs-You-Now horizon (T+0 → T+14) aggregates — pulled from the
  // same source the Capacity Pulse on this tab uses (useUpcomingEvents),
  // so the headline KPIs match the chart underneath. The old
  // useWeeklySlotStatuses path covered only 7 days and undercounted
  // events in the second week of the horizon.
  const upcomingEvents = upcoming.data ?? [];
  const upcomingRecurring = useMemo(
    () => upcomingEvents.filter((e) => e.kind === "recurring").length,
    [upcomingEvents],
  );
  const upcomingSpecific = upcomingEvents.length - upcomingRecurring;
  const upcomingTotalRequired = useMemo(
    () => upcomingEvents.reduce((s, e) => s + e.min_required_total, 0),
    [upcomingEvents],
  );
  const upcomingOpenMin = useMemo(
    () =>
      upcomingEvents.reduce(
        (s, e) => s + Math.max(0, e.min_required_total - e.booked),
        0,
      ),
    [upcomingEvents],
  );
  const upcomingAtRisk = useMemo(
    () =>
      upcomingEvents.filter((e) => e.booked < e.min_required_total).length,
    [upcomingEvents],
  );
  const upcomingCampaignsRunning = useMemo(
    () => upcomingEvents.filter((e) => isCampaignRunning(e.campaign)).length,
    [upcomingEvents],
  );

  // Planning horizon (T+15 → T+60) aggregates — mirror the same
  // metrics the Needs-You-Now KPIs show, but for the longer horizon
  // so the headers stay coherent when the admin switches tabs.
  const planningEvents = planning.data ?? [];
  const planningRecurring = useMemo(
    () => planningEvents.filter((e) => e.kind === "recurring").length,
    [planningEvents],
  );
  const planningSpecific = planningEvents.length - planningRecurring;
  const planningTotalRequired = useMemo(
    () => planningEvents.reduce((s, e) => s + e.min_required_total, 0),
    [planningEvents],
  );
  const planningOpenMin = useMemo(
    () =>
      planningEvents.reduce(
        (s, e) => s + Math.max(0, e.min_required_total - e.booked),
        0,
      ),
    [planningEvents],
  );
  const planningAtRisk = useMemo(
    () =>
      planningEvents.filter((e) => e.booked < e.min_required_total).length,
    [planningEvents],
  );
  const planningCampaignsRunning = useMemo(
    () => planningEvents.filter((e) => isCampaignRunning(e.campaign)).length,
    [planningEvents],
  );

  // Pick the KPI shape that matches the active tab. Active Volunteers
  // dropped — the headline numbers should track the tab's horizon.
  const kpiProps =
    tab === "planning"
      ? {
          eventsLabel: "Events 15–60 days",
          eventsCount: planningEvents.length,
          eventsSubline:
            planningEvents.length > 0
              ? `${planningRecurring} recurring · ${planningSpecific} one-time`
              : undefined,
          openSlotsValue:
            planningTotalRequired > 0
              ? `${planningOpenMin} / ${planningTotalRequired}`
              : planningOpenMin,
          openSlotsSubline:
            planningTotalRequired > 0
              ? "Below minimum / total required"
              : "All minimums met",
          atRiskCount: planningAtRisk,
          atRiskSubline:
            planningEvents.length > 0
              ? `of ${planningEvents.length} below minimum`
              : "No events in horizon",
          campaignsValue:
            planningEvents.length > 0
              ? `${planningCampaignsRunning} / ${planningEvents.length}`
              : 0,
          campaignsSubline: "Events with an active campaign",
          isLoading: planning.isLoading,
        }
      : {
          eventsLabel: "Events next 2 weeks",
          eventsCount: upcomingEvents.length,
          eventsSubline:
            upcomingEvents.length > 0
              ? `${upcomingRecurring} recurring · ${upcomingSpecific} one-time`
              : undefined,
          openSlotsValue:
            upcomingTotalRequired > 0
              ? `${upcomingOpenMin} / ${upcomingTotalRequired}`
              : upcomingOpenMin,
          openSlotsSubline:
            upcomingTotalRequired > 0
              ? "Below minimum / total required"
              : "All minimums met",
          atRiskCount: upcomingAtRisk,
          atRiskSubline:
            upcomingEvents.length > 0
              ? `of ${upcomingEvents.length} below minimum`
              : "No events in horizon",
          campaignsValue:
            upcomingEvents.length > 0
              ? `${upcomingCampaignsRunning} / ${upcomingEvents.length}`
              : 0,
          campaignsSubline: "Events with an active campaign",
          isLoading: upcoming.isLoading,
        };

  return (
    <div className="space-y-6">
      <DashboardGreeting
        eventsThisWeek={aggregated.length}
        needingVolunteers={needingVolunteers}
        isLoading={summary.isLoading || weekly.isLoading}
      />

      <Tabs
        value={tab}
        onValueChange={(v) => setTab(v as "now" | "planning" | "org_health")}
        className="space-y-5"
      >
        <TabsList className="bg-muted/60">
          <TabsTrigger value="now" className="gap-2">
            <Inbox className="h-3.5 w-3.5" />
            Needs you now
            {decisionsCount > 0 && (
              <CountBadge value={decisionsCount} tone="urgent" />
            )}
          </TabsTrigger>
          <TabsTrigger value="planning" className="gap-2">
            <CalendarRange className="h-3.5 w-3.5" />
            Planning
            {recommendations && recommendations.length > 0 && (
              <CountBadge value={recommendations.length} tone="info" />
            )}
          </TabsTrigger>
          <TabsTrigger value="org_health" className="gap-2">
            <Activity className="h-3.5 w-3.5" />
            Org health
            {headsUpCount > 0 && (
              <CountBadge value={headsUpCount} tone="info" />
            )}
          </TabsTrigger>
        </TabsList>

        {/* KPI row sits between the tab strip and its content so the
            headline numbers match whichever horizon is selected.
            Hidden on Org health — that tab's surfaces carry their
            own headline numbers (donation totals, volunteer counts)
            and the operational events/open-slots KPIs don't apply. */}
        {tab !== "org_health" && <DashboardKpiRow {...kpiProps} />}

        <TabsContent value="now" className="space-y-6">
          {/* Live events — pinned at the top when active */}
          {hasLiveEvents && <LiveEventsPanel />}

          {/* Hero row: Capacity Pulse (rich rows) on the left,
              Donations preview on the right. The pulse rows carry
              event metadata + Start Campaign inline; donations is a
              preview surface for the upcoming campaign feature. */}
          <div className="grid gap-4 xl:grid-cols-3">
            <div className="xl:col-span-2">
              <CapacityPulse />
            </div>
            <div className="xl:col-span-1">
              <DonationsChart />
            </div>
          </div>

          {/* Action row: Alerts breakdown (donut, Decisions categories
              only) on the left, the Decisions feed on the right.
              Putting them side-by-side ties the donut filter to the
              feed it's filtering with no scroll. items-start so
              columns size to their content instead of stretching to
              match each other — keeps the Heads-up section directly
              below the taller column with no dead space. */}
          <div className="grid items-start gap-4 xl:grid-cols-3">
            <div className="xl:col-span-1">
              <AlertsDonut
                selected={alertCategory}
                onSelect={setAlertCategory}
              />
            </div>
            <div className="xl:col-span-2">
              <section>
                <button
                  type="button"
                  onClick={() => setDecisionsOpen((o) => !o)}
                  className="group mb-3 flex w-full items-baseline gap-3 rounded-md py-1 text-left hover:bg-muted/40"
                  aria-expanded={decisionsOpen}
                >
                  <ChevronDown
                    className={cn(
                      "h-4 w-4 shrink-0 self-center text-muted-foreground transition-transform",
                      !decisionsOpen && "-rotate-90",
                    )}
                  />
                  <div>
                    <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                      Decisions
                    </p>
                    <h2 className="text-base font-semibold">
                      {alertCategory
                        ? "Filtered decisions"
                        : "Things that need a call from you"}
                    </h2>
                  </div>
                  {decisionsCount > 0 && (
                    <CountBadge value={decisionsCount} tone="urgent" />
                  )}
                  <p className="ml-auto hidden text-xs text-muted-foreground sm:block">
                    {decisionsOpen
                      ? "Resolve on the CTA, snooze, or dismiss."
                      : "Click to expand"}
                  </p>
                </button>
                {decisionsOpen && (
                  // Capped-height container with its own vertical
                  // scrollbar. max-h (not h) so the container only
                  // grows to fit content — when there are 1-2 items
                  // it sits tight against the Heads-up section
                  // instead of reserving 420px of empty space, and
                  // only when the feed overflows does the scrollbar
                  // appear.
                  <div className="max-h-[420px] overflow-y-auto pr-1">
                    <AlertsFeed
                      categoryFilter={alertCategory}
                      groupFilter="decisions"
                    />
                  </div>
                )}
              </section>
            </div>
          </div>

        </TabsContent>

        <TabsContent value="planning">
          <PlanningView />
        </TabsContent>

        <TabsContent value="org_health" className="space-y-6">
          {/* Two-column row of org-level preview charts: volunteer
              base health on the left, donor base composition on the
              right. Stack vertically on narrower screens. */}
          <div className="grid gap-4 xl:grid-cols-2">
            <VolunteerHealthChart />
            <DonorsChart />
          </div>

          {/* Heads-up — informational items (walk-ups, complaints,
              feedback, hallucinations, token-usage flags, open
              issues). Lives here instead of Needs-You-Now because
              these are organisation-level signals to monitor, not
              decisions that need a call today. Expanded by default
              on this tab since the whole tab is about looking. */}
          <section>
            <button
              type="button"
              onClick={() => setHeadsUpOpen((o) => !o)}
              className="group mb-3 flex w-full items-baseline gap-3 rounded-md py-1 text-left hover:bg-muted/40"
              aria-expanded={headsUpOpen}
            >
              <ChevronDown
                className={cn(
                  "h-4 w-4 shrink-0 self-center text-muted-foreground transition-transform",
                  !headsUpOpen && "-rotate-90",
                )}
              />
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                  Heads up
                </p>
                <h2 className="text-base font-semibold">
                  Things to know about
                </h2>
              </div>
              {headsUpCount > 0 && (
                <CountBadge value={headsUpCount} tone="info" />
              )}
              <p className="ml-auto hidden text-xs text-muted-foreground sm:block">
                {headsUpOpen
                  ? "Walk-ups, complaints, feedback, AI alerts."
                  : "Click to expand"}
              </p>
            </button>
            {headsUpOpen && (
              <div className="space-y-4">
                <HeadsUpChart
                  alerts={headsUpAlerts}
                  selectedCategory={headsUpCategory}
                  onSelectCategory={setHeadsUpCategory}
                />
                {headsUpCategory ? (
                  <HeadsUpPreviewList category={headsUpCategory} />
                ) : (
                  <AlertsFeed
                    categoryFilter={alertCategory}
                    groupFilter="heads_up"
                  />
                )}
              </div>
            )}
          </section>
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
