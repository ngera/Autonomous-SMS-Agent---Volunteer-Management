import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  listAppointmentTypes,
  createAppointmentType,
  updateAppointmentType,
  deleteAppointmentType,
  getRelatedServices,
  createRelatedService,
  deleteRelatedService,
} from "../api";
import type {
  AppointmentTypeCreate,
  AppointmentTypeUpdate,
  RelatedServiceCreate,
} from "@/types/api";
import { useActiveTenantId } from "@/hooks/use-active-tenant";

export function useAppointmentTypes() {
  const tenantId = useActiveTenantId();
  return useQuery({
    queryKey: ["appointment-types", tenantId],
    queryFn: listAppointmentTypes,
    enabled: tenantId !== "none",
  });
}

export function useRelatedServices(typeId: string) {
  const tenantId = useActiveTenantId();
  return useQuery({
    queryKey: ["appointment-types", tenantId, typeId, "related"],
    queryFn: () => getRelatedServices(typeId),
    enabled: !!typeId && tenantId !== "none",
  });
}

export function useCreateAppointmentType() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: AppointmentTypeCreate) => createAppointmentType(body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["appointment-types"] });
    },
  });
}

export function useUpdateAppointmentType() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: AppointmentTypeUpdate }) =>
      updateAppointmentType(id, body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["appointment-types"] });
    },
  });
}

export function useDeleteAppointmentType() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: deleteAppointmentType,
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["appointment-types"] });
    },
  });
}

export function useCreateRelatedService() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ typeId, body }: { typeId: string; body: RelatedServiceCreate }) =>
      createRelatedService(typeId, body),
    onSuccess: (_data, variables) => {
      void qc.invalidateQueries({
        queryKey: ["appointment-types", variables.typeId, "related"],
      });
    },
  });
}

export function useDeleteRelatedService() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ typeId, relatedId }: { typeId: string; relatedId: string }) =>
      deleteRelatedService(typeId, relatedId),
    onSuccess: (_data, variables) => {
      void qc.invalidateQueries({
        queryKey: ["appointment-types", variables.typeId, "related"],
      });
    },
  });
}
