import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getUpcomingReminders,
  getReminderHistory,
  triggerReminder,
  updateReminder,
  cancelReminder,
  getReminderAnalytics,
} from "../api";
import type { ReminderTriggerRequest, ReminderUpdate, ReminderCancelRequest } from "@/types/api";

export function useUpcomingReminders() {
  return useQuery({
    queryKey: ["reminders", "upcoming"],
    queryFn: getUpcomingReminders,
  });
}

export function useReminderHistory(page: number, pageSize: number) {
  return useQuery({
    queryKey: ["reminders", "history", page, pageSize],
    queryFn: () => getReminderHistory(page, pageSize),
  });
}

export function useTriggerReminder() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: ReminderTriggerRequest) => triggerReminder(body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["reminders"] });
    },
  });
}

export function useUpdateReminder() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: ReminderUpdate }) =>
      updateReminder(id, body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["reminders"] });
    },
  });
}

export function useCancelReminder() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: ReminderCancelRequest }) =>
      cancelReminder(id, body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["reminders"] });
    },
  });
}

export function useReminderAnalytics() {
  return useQuery({
    queryKey: ["reminders", "analytics"],
    queryFn: getReminderAnalytics,
  });
}
