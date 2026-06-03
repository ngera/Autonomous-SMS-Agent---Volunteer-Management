import api from "@/lib/api";
import type { VolunteerCandidate } from "@/types/api";

export async function listCandidates(
  statusFilter?: string
): Promise<VolunteerCandidate[]> {
  const { data } = await api.get<VolunteerCandidate[]>("/candidates", {
    params: statusFilter ? { status_filter: statusFilter } : {},
  });
  return data;
}

export async function inviteCandidate(
  id: string,
  name: string
): Promise<VolunteerCandidate> {
  const { data } = await api.post<VolunteerCandidate>(
    `/candidates/${id}/invite`,
    { name }
  );
  return data;
}

export async function dismissCandidate(
  id: string,
  notes?: string | null
): Promise<VolunteerCandidate> {
  const { data } = await api.post<VolunteerCandidate>(
    `/candidates/${id}/dismiss`,
    { notes: notes ?? null }
  );
  return data;
}
