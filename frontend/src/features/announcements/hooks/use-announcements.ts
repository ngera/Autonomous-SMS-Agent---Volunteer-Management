import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  listAnnouncements,
  createAnnouncement,
  cancelAnnouncement,
  bulkDeleteAnnouncements,
} from "../api";
import type { AnnouncementCreate } from "@/types/api";
import { useActiveTenantId } from "@/hooks/use-active-tenant";

export function useAnnouncements(page = 1) {
  const tenantId = useActiveTenantId();
  return useQuery({
    queryKey: ["announcements", tenantId, page],
    queryFn: () => listAnnouncements(page),
    enabled: tenantId !== "none",
  });
}

export function useCreateAnnouncement() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: AnnouncementCreate) => createAnnouncement(body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["announcements"] });
    },
  });
}

export function useCancelAnnouncement() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => cancelAnnouncement(id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["announcements"] });
    },
  });
}

export function useBulkDeleteAnnouncements() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (ids: string[]) => bulkDeleteAnnouncements(ids),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["announcements"] });
    },
  });
}
