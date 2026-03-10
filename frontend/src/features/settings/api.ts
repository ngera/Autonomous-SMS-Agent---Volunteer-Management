import api from "@/lib/api";
import type {
  SystemSettingResponse,
  SystemSettingsUpdate,
  AdminUserResponse,
  AdminUserCreate,
  AdminUserUpdate,
  MessageResponse,
} from "@/types/api";

// ── Settings ──

export async function getSettings(): Promise<SystemSettingResponse[]> {
  const { data } = await api.get<SystemSettingResponse[]>("/settings");
  return data;
}

export async function updateSettings(
  body: SystemSettingsUpdate
): Promise<MessageResponse> {
  const { data } = await api.put<MessageResponse>("/settings", body);
  return data;
}

// ── Admin Users ──

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
  id: string,
  body: AdminUserUpdate
): Promise<AdminUserResponse> {
  const { data } = await api.put<AdminUserResponse>(`/admin-users/${id}`, body);
  return data;
}
