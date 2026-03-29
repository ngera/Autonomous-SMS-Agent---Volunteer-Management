import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  listAnnouncements,
  createAnnouncement,
  cancelAnnouncement,
} from "../api";
import type { AnnouncementCreate } from "@/types/api";

export function useAnnouncements(page = 1) {
  return useQuery({
    queryKey: ["announcements", page],
    queryFn: () => listAnnouncements(page),
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
