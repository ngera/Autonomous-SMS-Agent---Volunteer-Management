import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  approveReview,
  flipNoShowToPending,
  listReviewsForEvent,
  skipReview,
  unlockReview,
} from "../api";

export function useReviewsForEvent(slotId: string | undefined) {
  return useQuery({
    queryKey: ["reviews", "event", slotId],
    queryFn: () => listReviewsForEvent(slotId!),
    enabled: !!slotId,
  });
}

function invalidateReviewQueries(qc: ReturnType<typeof useQueryClient>, slotId: string | undefined) {
  qc.invalidateQueries({ queryKey: ["reviews", "event", slotId] });
}

export function useApproveReview(slotId: string | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      reviewId,
      grade,
      notes,
    }: {
      reviewId: string;
      grade: number;
      notes?: string | null;
    }) => approveReview(reviewId, grade, notes),
    onSuccess: () => invalidateReviewQueries(qc, slotId),
  });
}

export function useSkipReview(slotId: string | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      reviewId,
      notes,
    }: {
      reviewId: string;
      notes?: string | null;
    }) => skipReview(reviewId, notes),
    onSuccess: () => invalidateReviewQueries(qc, slotId),
  });
}

export function useFlipNoShow(slotId: string | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (reviewId: string) => flipNoShowToPending(reviewId),
    onSuccess: () => invalidateReviewQueries(qc, slotId),
  });
}

export function useUnlockReview(slotId: string | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (reviewId: string) => unlockReview(reviewId),
    onSuccess: () => invalidateReviewQueries(qc, slotId),
  });
}
