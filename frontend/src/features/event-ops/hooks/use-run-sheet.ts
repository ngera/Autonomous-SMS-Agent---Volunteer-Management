import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  adminCheckin,
  adminCheckout,
  approvePendingEntry,
  getPendingForSlot,
  getRunSheet,
  rejectPendingEntry,
} from "../api";

export function useRunSheet(slotId: string | undefined) {
  return useQuery({
    queryKey: ["run-sheet", slotId],
    queryFn: () => getRunSheet(slotId!),
    enabled: !!slotId,
    refetchInterval: 30_000,
    refetchIntervalInBackground: false,
  });
}

export function useAdminCheckin(slotId: string | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      bookingId,
      at,
    }: {
      bookingId: string;
      at?: string | null;
    }) => adminCheckin(bookingId, at),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["run-sheet", slotId] });
      qc.invalidateQueries({ queryKey: ["dashboard", "live-events"] });
    },
  });
}

export function useAdminCheckout(slotId: string | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      bookingId,
      at,
    }: {
      bookingId: string;
      at?: string | null;
    }) => adminCheckout(bookingId, at),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["run-sheet", slotId] });
      qc.invalidateQueries({ queryKey: ["dashboard", "live-events"] });
    },
  });
}

export function usePendingForSlot(slotId: string | undefined) {
  return useQuery({
    queryKey: ["service-log", "pending", slotId],
    queryFn: () => getPendingForSlot(slotId!),
    enabled: !!slotId,
    refetchInterval: 30_000,
    refetchIntervalInBackground: false,
  });
}

export function useApprovePending(slotId: string | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      entryId,
      expectedVersion,
    }: {
      entryId: string;
      expectedVersion: number;
    }) => approvePendingEntry(entryId, expectedVersion),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["service-log", "pending", slotId] });
      qc.invalidateQueries({ queryKey: ["dashboard", "live-events"] });
    },
  });
}

export function useRejectPending(slotId: string | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      entryId,
      expectedVersion,
      reason,
    }: {
      entryId: string;
      expectedVersion: number;
      reason?: string | null;
    }) => rejectPendingEntry(entryId, expectedVersion, reason),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["service-log", "pending", slotId] });
      qc.invalidateQueries({ queryKey: ["dashboard", "live-events"] });
    },
  });
}
