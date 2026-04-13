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
