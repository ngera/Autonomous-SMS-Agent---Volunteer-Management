import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getAvailabilityRules,
  updateAvailabilityRules,
  getBlockedDates,
  createBlockedDate,
  deleteBlockedDate,
  listSpecificDateSlots,
  createSpecificDateSlot,
  updateSpecificDateSlot,
  deleteSpecificDateSlot,
  getSlotPreview,
} from "../api";
import type {
  WeeklyScheduleUpdate,
  BlockedDateCreate,
  SpecificDateSlotCreate,
  SpecificDateSlotUpdate,
} from "@/types/api";
import { useActiveTenantId } from "@/hooks/use-active-tenant";

export function useAvailabilityRules() {
  const tenantId = useActiveTenantId();
  return useQuery({
    queryKey: ["availability", "rules", tenantId],
    queryFn: getAvailabilityRules,
    enabled: tenantId !== "none",
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
  const tenantId = useActiveTenantId();
  return useQuery({
    queryKey: ["availability", "blocked-dates", tenantId],
    queryFn: getBlockedDates,
    enabled: tenantId !== "none",
  });
}

export function useCreateBlockedDate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ body, force }: { body: BlockedDateCreate; force?: boolean }) =>
      createBlockedDate(body, { force }),
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

export function useSpecificDateSlots() {
  const tenantId = useActiveTenantId();
  return useQuery({
    queryKey: ["availability", "specific-slots", tenantId],
    queryFn: listSpecificDateSlots,
    enabled: tenantId !== "none",
  });
}

export function useCreateSpecificDateSlot() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ body, force }: { body: SpecificDateSlotCreate; force?: boolean }) =>
      createSpecificDateSlot(body, { force }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["availability", "specific-slots"] });
    },
  });
}

export function useUpdateSpecificDateSlot() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      body,
      force,
    }: {
      id: string;
      body: SpecificDateSlotUpdate;
      force?: boolean;
    }) => updateSpecificDateSlot(id, body, { force }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["availability", "specific-slots"] });
    },
  });
}

export function useDeleteSpecificDateSlot() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: deleteSpecificDateSlot,
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["availability", "specific-slots"] });
    },
  });
}

export function useSlotPreview(date: string, appointmentTypeId: string) {
  const tenantId = useActiveTenantId();
  return useQuery({
    queryKey: ["availability", "slots", tenantId, date, appointmentTypeId],
    queryFn: () => getSlotPreview(date, appointmentTypeId),
    enabled: !!date && !!appointmentTypeId && tenantId !== "none",
  });
}
