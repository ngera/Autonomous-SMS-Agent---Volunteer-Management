import api from "@/lib/api";
import type {
  DashboardSummary,
  TodaysBooking,
  NotificationResponse,
} from "@/types/api";

export async function getDashboardSummary(): Promise<DashboardSummary> {
  const { data } = await api.get<DashboardSummary>("/dashboard/summary");
  return data;
}

export async function getTodaysBookings(): Promise<TodaysBooking[]> {
  const { data } = await api.get<TodaysBooking[]>("/dashboard/todays-bookings");
  return data;
}

export async function getNotifications(): Promise<NotificationResponse[]> {
  const { data } = await api.get<NotificationResponse[]>(
    "/dashboard/notifications"
  );
  return data;
}

export async function markNotificationRead(id: string): Promise<void> {
  await api.put(`/dashboard/notifications/${id}/read`);
}
