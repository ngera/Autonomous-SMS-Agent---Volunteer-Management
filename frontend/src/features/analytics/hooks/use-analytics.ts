import { useQuery } from "@tanstack/react-query";
import {
  getBookingAnalytics,
  getRevenueAnalytics,
  getRetentionMetrics,
  getReminderAnalytics,
  getConsentFunnel,
} from "../api";

export function useBookingAnalytics(months = 6) {
  return useQuery({
    queryKey: ["analytics", "bookings", months],
    queryFn: () => getBookingAnalytics(months),
  });
}

export function useRevenueAnalytics(months = 6) {
  return useQuery({
    queryKey: ["analytics", "revenue", months],
    queryFn: () => getRevenueAnalytics(months),
  });
}

export function useRetentionMetrics() {
  return useQuery({
    queryKey: ["analytics", "retention"],
    queryFn: getRetentionMetrics,
  });
}

export function useReminderAnalytics() {
  return useQuery({
    queryKey: ["analytics", "reminders"],
    queryFn: getReminderAnalytics,
  });
}

export function useConsentFunnel() {
  return useQuery({
    queryKey: ["analytics", "consent"],
    queryFn: getConsentFunnel,
  });
}
