import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  listSuspensions,
  getSuspension,
  liftSuspension,
  confirmSuspension,
  banUser,
  manualSuspend,
} from "../api";
import type { ReviewRequest, ManualSuspendRequest } from "@/types/api";

export function useSuspensions() {
  return useQuery({
    queryKey: ["suspensions"],
    queryFn: listSuspensions,
  });
}

export function useSuspension(id: string) {
  return useQuery({
    queryKey: ["suspensions", id],
    queryFn: () => getSuspension(id),
    enabled: !!id,
  });
}

export function useLiftSuspension() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: ReviewRequest }) =>
      liftSuspension(id, body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["suspensions"] });
    },
  });
}

export function useConfirmSuspension() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: ReviewRequest }) =>
      confirmSuspension(id, body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["suspensions"] });
    },
  });
}

export function useBanUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: ReviewRequest }) =>
      banUser(id, body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["suspensions"] });
    },
  });
}

export function useManualSuspend() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      phone,
      body,
    }: {
      phone: string;
      body: ManualSuspendRequest;
    }) => manualSuspend(phone, body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["suspensions"] });
    },
  });
}
