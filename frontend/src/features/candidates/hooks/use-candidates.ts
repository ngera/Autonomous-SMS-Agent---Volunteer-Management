import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  dismissCandidate,
  inviteCandidate,
  listCandidates,
} from "../api";
import { useActiveTenantId } from "@/hooks/use-active-tenant";

export function useCandidates(statusFilter?: string) {
  const tenantId = useActiveTenantId();
  return useQuery({
    queryKey: ["candidates", "list", tenantId, statusFilter ?? "all"],
    queryFn: () => listCandidates(statusFilter),
    enabled: tenantId !== "none",
  });
}

export function useInviteCandidate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, name }: { id: string; name: string }) =>
      inviteCandidate(id, name),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ["candidates"] }),
  });
}

export function useDismissCandidate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, notes }: { id: string; notes?: string | null }) =>
      dismissCandidate(id, notes),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ["candidates"] }),
  });
}
