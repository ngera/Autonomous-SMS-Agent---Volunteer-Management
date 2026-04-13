import api from "@/lib/api";
import type {
  DashboardSummary,
  TodaysBooking,
  WeeklySlotStatus,
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

export async function getWeeklySlotStatuses(offset: number = 0): Promise<WeeklySlotStatus[]> {
  const { data } = await api.get<WeeklySlotStatus[]>("/dashboard/weekly-slots", {
    params: { offset },
  });
  return data;
}

export async function sendSlotReminder(
  date: string,
  appointmentTypeId: string,
): Promise<{ sent_signup: number; sent_confirmation: number; total_volunteers: number }> {
  const { data } = await api.post("/dashboard/send-reminder", {
    date,
    appointment_type_id: appointmentTypeId,
  });
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
