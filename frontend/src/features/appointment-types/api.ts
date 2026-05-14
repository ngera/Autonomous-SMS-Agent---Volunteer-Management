import api from "@/lib/api";
import type {
  AppointmentTypeResponse,
  AppointmentTypeCreate,
  AppointmentTypeUpdate,
  RelatedServiceResponse,
  RelatedServiceCreate,
} from "@/types/api";

export async function listAppointmentTypes(): Promise<AppointmentTypeResponse[]> {
  const { data } = await api.get<AppointmentTypeResponse[]>("/appointment-types");
  return data;
}

export async function listAppointmentTypesForTenant(
  tenantId: string
): Promise<AppointmentTypeResponse[]> {
  const { data } = await api.get<AppointmentTypeResponse[]>("/appointment-types", {
    headers: { "X-Tenant-Id": tenantId },
  });
  return data;
}

export async function createAppointmentType(
  body: AppointmentTypeCreate
): Promise<AppointmentTypeResponse> {
  const { data } = await api.post<AppointmentTypeResponse>("/appointment-types", body);
  return data;
}

export async function updateAppointmentType(
  id: string,
  body: AppointmentTypeUpdate
): Promise<AppointmentTypeResponse> {
  const { data } = await api.put<AppointmentTypeResponse>(`/appointment-types/${id}`, body);
  return data;
}

export async function deleteAppointmentType(id: string): Promise<void> {
  await api.delete(`/appointment-types/${id}`);
}

export async function getRelatedServices(
  typeId: string
): Promise<RelatedServiceResponse[]> {
  const { data } = await api.get<RelatedServiceResponse[]>(
    `/appointment-types/${typeId}/related`
  );
  return data;
}

export async function createRelatedService(
  typeId: string,
  body: RelatedServiceCreate
): Promise<RelatedServiceResponse> {
  const { data } = await api.post<RelatedServiceResponse>(
    `/appointment-types/${typeId}/related`,
    body
  );
  return data;
}

export async function deleteRelatedService(
  typeId: string,
  relatedId: string
): Promise<void> {
  await api.delete(`/appointment-types/${typeId}/related/${relatedId}`);
}
