import api from "@/lib/api";
import type {
  SuspensionResponse,
  SuspensionListResponse,
  ReviewRequest,
  ManualSuspendRequest,
} from "@/types/api";

export async function listSuspensions(): Promise<SuspensionListResponse> {
  const { data } = await api.get<SuspensionListResponse>("/suspensions");
  return data;
}

export async function getSuspension(id: string): Promise<SuspensionResponse> {
  const { data } = await api.get<SuspensionResponse>(`/suspensions/${id}`);
  return data;
}

export async function liftSuspension(
  id: string,
  body: ReviewRequest
): Promise<SuspensionResponse> {
  const { data } = await api.post<SuspensionResponse>(
    `/suspensions/${id}/lift`,
    body
  );
  return data;
}

export async function confirmSuspension(
  id: string,
  body: ReviewRequest
): Promise<SuspensionResponse> {
  const { data } = await api.post<SuspensionResponse>(
    `/suspensions/${id}/confirm`,
    body
  );
  return data;
}

export async function banUser(
  id: string,
  body: ReviewRequest
): Promise<SuspensionResponse> {
  const { data } = await api.post<SuspensionResponse>(
    `/suspensions/${id}/ban`,
    body
  );
  return data;
}

export async function manualSuspend(
  phone: string,
  body: ManualSuspendRequest
): Promise<SuspensionResponse> {
  const { data } = await api.post<SuspensionResponse>(
    `/suspensions/customers/${encodeURIComponent(phone)}/suspend`,
    body
  );
  return data;
}
