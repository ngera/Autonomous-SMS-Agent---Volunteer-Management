import api from "@/lib/api";
import type {
  BookingVolumePoint,
  RevenuePoint,
  RetentionMetrics,
  ReminderAnalytics,
  ConsentFunnel,
} from "@/types/api";

export async function getBookingAnalytics(
  months = 6
): Promise<BookingVolumePoint[]> {
  const { data } = await api.get<BookingVolumePoint[]>("/analytics/bookings", {
    params: { months },
  });
  return data;
}

export async function getRevenueAnalytics(
  months = 6
): Promise<RevenuePoint[]> {
  const { data } = await api.get<RevenuePoint[]>("/analytics/revenue", {
    params: { months },
  });
  return data;
}

export async function getRetentionMetrics(): Promise<RetentionMetrics> {
  const { data } = await api.get<RetentionMetrics>("/analytics/retention");
  return data;
}

export async function getReminderAnalytics(): Promise<ReminderAnalytics> {
  const { data } = await api.get<ReminderAnalytics>("/analytics/reminders");
  return data;
}

export async function getConsentFunnel(): Promise<ConsentFunnel> {
  const { data } = await api.get<ConsentFunnel>("/analytics/consent");
  return data;
}
