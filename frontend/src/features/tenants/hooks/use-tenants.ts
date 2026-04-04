import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  listTenants,
  getTenant,
  createTenant,
  updateTenant,
  deactivateTenant,
  pauseTenant,
  unpauseTenant,
  reactivateTenant,
  getSuperAdminDashboard,
  listAdminUsers,
  createAdminUser,
  updateAdminUser,
  updateAdminUserPassword,
} from "../api";
import type {
  TenantCreate,
  TenantUpdate,
  AdminUserCreate,
  AdminUserUpdate,
} from "@/types/api";

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

export function usePauseTenant() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => pauseTenant(id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["tenants"] });
    },
  });
}

export function useUnpauseTenant() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => unpauseTenant(id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["tenants"] });
    },
  });
}

export function useReactivateTenant() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => reactivateTenant(id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["tenants"] });
    },
  });
}

// ── Super Admin Dashboard ──

export function useSuperAdminDashboard(tenantIds?: string[]) {
  return useQuery({
    queryKey: ["super-admin-dashboard", tenantIds],
    queryFn: () => getSuperAdminDashboard(tenantIds),
  });
}

// ── Admin User Management ──

export function useTenantUsers(tenantId: string) {
  return useQuery({
    queryKey: ["tenant-users", tenantId],
    queryFn: listAdminUsers,
    enabled: !!tenantId,
  });
}

export function useCreateTenantUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: AdminUserCreate) => createAdminUser(body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["tenant-users"] });
    },
  });
}

export function useUpdateTenantUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ userId, body }: { userId: string; body: AdminUserUpdate }) =>
      updateAdminUser(userId, body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["tenant-users"] });
    },
  });
}

export function useUpdateTenantUserPassword() {
  return useMutation({
    mutationFn: ({ userId, password }: { userId: string; password: string }) =>
      updateAdminUserPassword(userId, { password }),
  });
}
