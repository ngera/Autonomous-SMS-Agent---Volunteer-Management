import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getDashboardSummary,
  getTodaysBookings,
  getWeeklySlotStatuses,
  sendSlotReminder,
  getNotifications,
  markNotificationRead,
} from "../api";
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
 * Planning horizon — events in T+8 → T+60 grouped by week bucket.
 * Polled every 5 min since the data changes slowly (events get
 * scheduled, campaigns get started).
 */
export function usePlanning() {
  const tenantId = useActiveTenantId();
  return useQuery({
    queryKey: ["dashboard", "planning", tenantId],
    queryFn: getPlanning,
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
