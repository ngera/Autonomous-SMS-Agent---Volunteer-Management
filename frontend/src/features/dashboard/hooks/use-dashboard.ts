import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getDashboardSummary,
  getTodaysBookings,
  getWeeklySlotStatuses,
  sendSlotReminder,
  getNotifications,
  markNotificationRead,
  startCampaignForEvent,
} from "../api";
import type { StartCampaignArgs } from "../api";
import { useActiveTenantId } from "@/hooks/use-active-tenant";

export function useDashboardSummary() {
  const tenantId = useActiveTenantId();
  return useQuery({
    queryKey: ["dashboard", "summary", tenantId],
    queryFn: getDashboardSummary,
    enabled: tenantId !== "none",
  });
}

export function useTodaysBookings() {
  const tenantId = useActiveTenantId();
  return useQuery({
    queryKey: ["dashboard", "todays-bookings", tenantId],
    queryFn: getTodaysBookings,
    enabled: tenantId !== "none",
  });
}

export function useWeeklySlotStatuses(offset: number = 0) {
  const tenantId = useActiveTenantId();
  return useQuery({
    queryKey: ["dashboard", "weekly-slots", tenantId, offset],
    queryFn: () => getWeeklySlotStatuses(offset),
    enabled: tenantId !== "none",
  });
}

export function useSendSlotReminder() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ date, appointmentTypeId }: { date: string; appointmentTypeId: string }) =>
      sendSlotReminder(date, appointmentTypeId),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["dashboard", "weekly-slots"] });
    },
  });
}

export function useNotifications() {
  const tenantId = useActiveTenantId();
  return useQuery({
    queryKey: ["dashboard", "notifications", tenantId],
    queryFn: getNotifications,
    enabled: tenantId !== "none",
  });
}

export function useMarkNotificationRead() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: markNotificationRead,
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: ["dashboard", "notifications"],
      });
    },
  });
}

import {
  getAlerts,
  getLiveEvents,
  getPlanning,
  getRecommendations,
} from "../api";

/**
 * Live Events panel — polls every 30s (decision #21 cadence). Auto-disabled
 * when not on the dashboard so we don't poll in the background.
 */
export function useLiveEvents() {
  const tenantId = useActiveTenantId();
  return useQuery({
    queryKey: ["dashboard", "live-events", tenantId],
    queryFn: getLiveEvents,
    enabled: tenantId !== "none",
    refetchInterval: 30_000,
    refetchIntervalInBackground: false,
  });
}

/**
 * Needs-You-Now unified alerts feed. Polls every 60s so dismissed alerts
 * stay clean and freshly-arriving ones (SWITCH/ALSO, walk-up candidates)
 * appear without a manual refresh.
 */
export function useAlerts() {
  const tenantId = useActiveTenantId();
  return useQuery({
    queryKey: ["dashboard", "alerts", tenantId],
    queryFn: getAlerts,
    enabled: tenantId !== "none",
    refetchInterval: 60_000,
    refetchIntervalInBackground: false,
  });
}

/**
 * Fire a synthetic admin SMS to the recruiter agent's start-campaign
 * router. Used by the event cards' "Start Campaign" button.
 */
export function useStartCampaign() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (args: StartCampaignArgs) => startCampaignForEvent(args),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}

/**
 * Planning horizon — events beyond the 2-week operational window
 * (T+15 → T+60). The 2-week boundary is the campaign-runway cutoff:
 * events sooner than 15 days are typically too imminent to start a
 * fresh multi-wave campaign for, so they're operational (Needs You
 * Now) rather than strategic (Planning).
 */
export function usePlanning() {
  const tenantId = useActiveTenantId();
  return useQuery({
    queryKey: ["dashboard", "planning", tenantId],
    queryFn: () => getPlanning(15, 60),
    enabled: tenantId !== "none",
    staleTime: 5 * 60_000,
  });
}

/**
 * Upcoming events for the Capacity Pulse — T-0 → T+14 (next 2 weeks).
 * Operational horizon: anything I can still influence by sending
 * reminders or making last-mile pushes.
 */
export function useUpcomingEvents() {
  const tenantId = useActiveTenantId();
  return useQuery({
    queryKey: ["dashboard", "upcoming", tenantId],
    queryFn: () => getPlanning(0, 14),
    enabled: tenantId !== "none",
    staleTime: 5 * 60_000,
  });
}

/**
 * AI / rule-based planning recommendations. Same cadence as planning
 * itself — recommendations only meaningfully change when underlying
 * events / campaigns change.
 */
export function useRecommendations() {
  const tenantId = useActiveTenantId();
  return useQuery({
    queryKey: ["dashboard", "recommendations", tenantId],
    queryFn: getRecommendations,
    enabled: tenantId !== "none",
    staleTime: 5 * 60_000,
  });
}
