import { useQuery } from "@tanstack/react-query";
import {
  getBookingAnalytics,
  getRevenueAnalytics,
  getRetentionMetrics,
  getReminderAnalytics,
  getConsentFunnel,
} from "../api";
import { useActiveTenantId } from "@/hooks/use-active-tenant";

export function useBookingAnalytics(months = 6) {
  const tenantId = useActiveTenantId();
  return useQuery({
    queryKey: ["analytics", "bookings", tenantId, months],
    queryFn: () => getBookingAnalytics(months),
    enabled: tenantId !== "none",
  });
}

export function useRevenueAnalytics(months = 6) {
  const tenantId = useActiveTenantId();
  return useQuery({
    queryKey: ["analytics", "revenue", tenantId, months],
    queryFn: () => getRevenueAnalytics(months),
    enabled: tenantId !== "none",
  });
}

export function useRetentionMetrics() {
  const tenantId = useActiveTenantId();
  return useQuery({
    queryKey: ["analytics", "retention", tenantId],
    queryFn: getRetentionMetrics,
    enabled: tenantId !== "none",
  });
}

export function useReminderAnalytics() {
  const tenantId = useActiveTenantId();
  return useQuery({
    queryKey: ["analytics", "reminders", tenantId],
    queryFn: getReminderAnalytics,
    enabled: tenantId !== "none",
  });
}

export function useConsentFunnel() {
  const tenantId = useActiveTenantId();
  return useQuery({
    queryKey: ["analytics", "consent", tenantId],
    queryFn: getConsentFunnel,
    enabled: tenantId !== "none",
  });
}
