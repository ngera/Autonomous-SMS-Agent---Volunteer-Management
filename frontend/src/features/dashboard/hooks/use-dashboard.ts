import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getDashboardSummary,
  getTodaysBookings,
  getNotifications,
  markNotificationRead,
} from "../api";

export function useDashboardSummary() {
  return useQuery({
    queryKey: ["dashboard", "summary"],
    queryFn: getDashboardSummary,
  });
}

export function useTodaysBookings() {
  return useQuery({
    queryKey: ["dashboard", "todays-bookings"],
    queryFn: getTodaysBookings,
  });
}

export function useNotifications() {
  return useQuery({
    queryKey: ["dashboard", "notifications"],
    queryFn: getNotifications,
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
