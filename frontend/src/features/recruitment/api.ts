import api from "@/lib/api";
import type {
  CampaignCreate,
  CampaignDetailResponse,
  CampaignListResponse,
  CampaignPlanPatch,
  CampaignResponse,
  WaveResponse,
} from "@/types/api";
import type { CampaignStatus } from "@/types/enums";

export interface ListCampaignsParams {
  status?: CampaignStatus;
  at_risk_only?: boolean;
  date_from?: string;
  date_to?: string;
  page?: number;
  page_size?: number;
}

export async function listCampaigns(
  params: ListCampaignsParams = {}
): Promise<CampaignListResponse> {
  const { data } = await api.get<CampaignListResponse>(
    "/recruitment/campaigns",
    { params }
  );
  return data;
}

export async function getCampaign(
  id: string
): Promise<CampaignDetailResponse> {
  const { data } = await api.get<CampaignDetailResponse>(
    `/recruitment/campaigns/${id}`
  );
  return data;
}

export async function createCampaign(
  body: CampaignCreate
): Promise<CampaignResponse> {
  const { data } = await api.post<CampaignResponse>(
    "/recruitment/campaigns",
    body
  );
  return data;
}

export async function regenerateCampaignPlan(
  id: string
): Promise<CampaignResponse> {
  const { data } = await api.post<CampaignResponse>(
    `/recruitment/campaigns/${id}/regenerate-plan`
  );
  return data;
}

export async function editCampaignPlan(
  id: string,
  body: CampaignPlanPatch
): Promise<CampaignResponse> {
  const { data } = await api.patch<CampaignResponse>(
    `/recruitment/campaigns/${id}/plan`,
    body
  );
  return data;
}

export async function approveCampaign(
  id: string
): Promise<CampaignResponse> {
  const { data } = await api.post<CampaignResponse>(
    `/recruitment/campaigns/${id}/approve`
  );
  return data;
}

export async function pauseCampaign(id: string): Promise<CampaignResponse> {
  const { data } = await api.post<CampaignResponse>(
    `/recruitment/campaigns/${id}/pause`
  );
  return data;
}

export async function resumeCampaign(id: string): Promise<CampaignResponse> {
  const { data } = await api.post<CampaignResponse>(
    `/recruitment/campaigns/${id}/resume`
  );
  return data;
}

export async function cancelCampaign(id: string): Promise<CampaignResponse> {
  const { data } = await api.post<CampaignResponse>(
    `/recruitment/campaigns/${id}/cancel`
  );
  return data;
}

export async function restartCampaign(id: string): Promise<CampaignResponse> {
  const { data } = await api.post<CampaignResponse>(
    `/recruitment/campaigns/${id}/restart`
  );
  return data;
}

export async function deleteCampaign(id: string): Promise<void> {
  await api.delete(`/recruitment/campaigns/${id}`);
}

export interface WaveRecipient {
  contact_id: string;
  name: string | null;
  phone: string | null;
  deleted: boolean;
  /** Actually-delivered SMS body for this recipient (looked up from
   *  conversation history). Falls back to a re-render of the template
   *  when the conversation entry can't be matched. Null when the wave
   *  hasn't fired or no template was recorded. */
  message: string | null;
}

export interface WaveRecipientsResponse {
  wave_id: string;
  wave_number: number;
  status: string;
  sent_count: number;
  signups_attributed: number;
  recipient_count: number;
  announcement_id: string | null;
  /** Unrendered template SMS — shared across all recipients in this wave. */
  template_message: string | null;
  event_context: Record<string, unknown> | null;
  sent_at: string | null;
  recipients: WaveRecipient[];
}

export async function getWaveRecipients(
  id: string
): Promise<WaveRecipientsResponse> {
  const { data } = await api.get<WaveRecipientsResponse>(
    `/recruitment/waves/${id}/recipients`
  );
  return data;
}

export async function cancelWave(id: string): Promise<WaveResponse> {
  const { data } = await api.post<WaveResponse>(
    `/recruitment/waves/${id}/cancel`
  );
  return data;
}
