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
import { useActiveTenantId } from "@/hooks/use-active-tenant";

export function useUpcomingReminders() {
  const tenantId = useActiveTenantId();
  return useQuery({
    queryKey: ["reminders", "upcoming", tenantId],
    queryFn: getUpcomingReminders,
    enabled: tenantId !== "none",
  });
}

export function useReminderHistory(page: number, pageSize: number) {
  const tenantId = useActiveTenantId();
  return useQuery({
    queryKey: ["reminders", "history", tenantId, page, pageSize],
    queryFn: () => getReminderHistory(page, pageSize),
    enabled: tenantId !== "none",
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
  const tenantId = useActiveTenantId();
  return useQuery({
    queryKey: ["reminders", "analytics", tenantId],
    queryFn: getReminderAnalytics,
    enabled: tenantId !== "none",
  });
}
