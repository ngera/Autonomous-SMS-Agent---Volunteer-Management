import api from "@/lib/api";
import type {
  ReminderResponse,
  ReminderListResponse,
  ReminderTriggerRequest,
  ReminderUpdate,
  ReminderCancelRequest,
  ReminderAnalytics,
} from "@/types/api";

export async function getUpcomingReminders(): Promise<ReminderListResponse> {
  const { data } = await api.get<ReminderListResponse>("/reminders/upcoming");
  return data;
}

export async function getReminderHistory(
  page: number,
  pageSize: number
): Promise<ReminderListResponse> {
  const { data } = await api.get<ReminderListResponse>("/reminders/history", {
    params: { page, page_size: pageSize },
  });
  return data;
}

export async function triggerReminder(
  body: ReminderTriggerRequest
): Promise<ReminderResponse> {
  const { data } = await api.post<ReminderResponse>("/reminders/trigger", body);
  return data;
}

export async function updateReminder(
  id: string,
  body: ReminderUpdate
): Promise<ReminderResponse> {
  const { data } = await api.put<ReminderResponse>(`/reminders/${id}`, body);
  return data;
}

export async function cancelReminder(
  id: string,
  body: ReminderCancelRequest
): Promise<void> {
  await api.delete(`/reminders/${id}`, { data: body });
}

export async function getReminderAnalytics(): Promise<ReminderAnalytics> {
  const { data } = await api.get<ReminderAnalytics>("/reminders/analytics");
  return data;
}
