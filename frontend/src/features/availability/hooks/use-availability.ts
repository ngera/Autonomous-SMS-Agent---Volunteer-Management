import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getAvailabilityRules,
  updateAvailabilityRules,
  getBlockedDates,
  createBlockedDate,
  deleteBlockedDate,
  getSlotPreview,
} from "../api";
import type { WeeklyScheduleUpdate, BlockedDateCreate } from "@/types/api";

export function useAvailabilityRules() {
  return useQuery({
    queryKey: ["availability", "rules"],
    queryFn: getAvailabilityRules,
  });
}

export function useUpdateAvailabilityRules() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: WeeklyScheduleUpdate) => updateAvailabilityRules(body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["availability", "rules"] });
    },
  });
}

export function useBlockedDates() {
  return useQuery({
    queryKey: ["availability", "blocked-dates"],
    queryFn: getBlockedDates,
  });
}

export function useCreateBlockedDate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: BlockedDateCreate) => createBlockedDate(body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["availability", "blocked-dates"] });
    },
  });
}

export function useDeleteBlockedDate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: deleteBlockedDate,
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["availability", "blocked-dates"] });
    },
  });
}

export function useSlotPreview(date: string, appointmentTypeId: string) {
  return useQuery({
    queryKey: ["availability", "slots", date, appointmentTypeId],
    queryFn: () => getSlotPreview(date, appointmentTypeId),
    enabled: !!date && !!appointmentTypeId,
  });
}
