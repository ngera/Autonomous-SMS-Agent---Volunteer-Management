import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  listTenants,
  getTenant,
  createTenant,
  updateTenant,
  deactivateTenant,
} from "../api";
import type { TenantCreate, TenantUpdate } from "@/types/api";

export function useTenants() {
  return useQuery({
    queryKey: ["tenants"],
    queryFn: listTenants,
  });
}

export function useTenant(id: string) {
  return useQuery({
    queryKey: ["tenants", id],
    queryFn: () => getTenant(id),
    enabled: !!id,
  });
}

export function useCreateTenant() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: TenantCreate) => createTenant(body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["tenants"] });
    },
  });
}

export function useUpdateTenant() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: TenantUpdate }) =>
      updateTenant(id, body),
    onSuccess: (_data, variables) => {
      void qc.invalidateQueries({ queryKey: ["tenants"] });
      void qc.invalidateQueries({ queryKey: ["tenants", variables.id] });
    },
  });
}

export function useDeactivateTenant() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deactivateTenant(id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["tenants"] });
    },
  });
}
