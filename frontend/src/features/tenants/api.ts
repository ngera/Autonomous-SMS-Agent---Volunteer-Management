import api from "@/lib/api";
import type {
  TenantResponse,
  TenantDetailResponse,
  TenantCreate,
  TenantUpdate,
  TenantListResponse,
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
