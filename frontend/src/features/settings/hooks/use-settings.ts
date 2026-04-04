import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getSettings,
  updateSettings,
  getPrompts,
  listAdminUsers,
  createAdminUser,
  updateAdminUser,
} from "../api";
import type {
  SystemSettingsUpdate,
  AdminUserCreate,
  AdminUserUpdate,
} from "@/types/api";
import { useActiveTenantId } from "@/hooks/use-active-tenant";

export function useSettings() {
  const tenantId = useActiveTenantId();
  return useQuery({
    queryKey: ["settings", tenantId],
    queryFn: getSettings,
    enabled: tenantId !== "none",
  });
}

export function useUpdateSettings() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: SystemSettingsUpdate) => updateSettings(body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["settings"] });
      void qc.invalidateQueries({ queryKey: ["prompts"] });
    },
  });
}

export function usePrompts() {
  const tenantId = useActiveTenantId();
  return useQuery({
    queryKey: ["prompts", tenantId],
    queryFn: getPrompts,
    enabled: tenantId !== "none",
  });
}

export function useAdminUsers() {
  const tenantId = useActiveTenantId();
  return useQuery({
    queryKey: ["admin-users", tenantId],
    queryFn: listAdminUsers,
    enabled: tenantId !== "none",
  });
}

export function useCreateAdminUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: AdminUserCreate) => createAdminUser(body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["admin-users"] });
    },
  });
}

export function useUpdateAdminUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: AdminUserUpdate }) =>
      updateAdminUser(id, body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["admin-users"] });
    },
  });
}
