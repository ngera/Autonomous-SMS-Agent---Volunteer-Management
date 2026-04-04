import api from "@/lib/api";
import type {
  TenantResponse,
  TenantDetailResponse,
  TenantCreate,
  TenantUpdate,
  TenantListResponse,
  SuperAdminDashboardSummary,
  AdminUserResponse,
  AdminUserCreate,
  AdminUserUpdate,
  AdminUserPasswordUpdate,
} from "@/types/api";

export async function listTenants(): Promise<TenantListResponse> {
  const { data } = await api.get<TenantListResponse>("/tenants");
  return data;
}

export async function getTenant(id: string): Promise<TenantDetailResponse> {
  const { data } = await api.get<TenantDetailResponse>(`/tenants/${id}`);
  return data;
}

export async function createTenant(
  body: TenantCreate
): Promise<TenantResponse> {
  const { data } = await api.post<TenantResponse>("/tenants", body);
  return data;
}

export async function updateTenant(
  id: string,
  body: TenantUpdate
): Promise<TenantResponse> {
  const { data } = await api.put<TenantResponse>(`/tenants/${id}`, body);
  return data;
}

export async function deactivateTenant(id: string): Promise<void> {
  await api.delete(`/tenants/${id}`);
}

export async function pauseTenant(id: string): Promise<TenantResponse> {
  const { data } = await api.post<TenantResponse>(`/tenants/${id}/pause`);
  return data;
}

export async function unpauseTenant(id: string): Promise<TenantResponse> {
  const { data } = await api.post<TenantResponse>(`/tenants/${id}/unpause`);
  return data;
}

export async function reactivateTenant(id: string): Promise<TenantResponse> {
  const { data } = await api.post<TenantResponse>(`/tenants/${id}/reactivate`);
  return data;
}

// ── Super Admin Dashboard ──

export async function getSuperAdminDashboard(
  tenantIds?: string[]
): Promise<SuperAdminDashboardSummary> {
  const params = tenantIds?.length ? { tenant_ids: tenantIds.join(",") } : {};
  const { data } = await api.get<SuperAdminDashboardSummary>(
    "/tenants/dashboard/summary",
    { params }
  );
  return data;
}

// ── Admin User Management (tenant-scoped via X-Tenant-Id) ──

export async function listAdminUsers(): Promise<AdminUserResponse[]> {
  const { data } = await api.get<AdminUserResponse[]>("/admin-users");
  return data;
}

export async function createAdminUser(
  body: AdminUserCreate
): Promise<AdminUserResponse> {
  const { data } = await api.post<AdminUserResponse>("/admin-users", body);
  return data;
}

export async function updateAdminUser(
  userId: string,
  body: AdminUserUpdate
): Promise<AdminUserResponse> {
  const { data } = await api.put<AdminUserResponse>(
    `/admin-users/${userId}`,
    body
  );
  return data;
}

export async function updateAdminUserPassword(
  userId: string,
  body: AdminUserPasswordUpdate
): Promise<void> {
  await api.put(`/admin-users/${userId}/password`, body);
}
