import api from "@/lib/api";
import type {
  AnnouncementResponse,
  AnnouncementListResponse,
  AnnouncementCreate,
} from "@/types/api";

export async function listAnnouncements(
  page = 1,
  pageSize = 20
): Promise<AnnouncementListResponse> {
  const { data } = await api.get<AnnouncementListResponse>("/announcements", {
    params: { page, page_size: pageSize },
  });
  return data;
}

export async function getAnnouncement(
  id: string
): Promise<AnnouncementResponse> {
  const { data } = await api.get<AnnouncementResponse>(
    `/announcements/${id}`
  );
  return data;
}

export async function createAnnouncement(
  body: AnnouncementCreate
): Promise<AnnouncementResponse> {
  const { data } = await api.post<AnnouncementResponse>(
    "/announcements",
    body
  );
  return data;
}

export async function cancelAnnouncement(id: string): Promise<void> {
  await api.delete(`/announcements/${id}`);
}

export async function bulkDeleteAnnouncements(
  ids: string[]
): Promise<{ deleted: number }> {
  const { data } = await api.post<{ deleted: number }>(
    "/announcements/bulk-delete",
    { ids }
  );
  return data;
}
