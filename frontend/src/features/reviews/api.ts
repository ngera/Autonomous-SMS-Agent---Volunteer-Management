import api from "@/lib/api";
import type { BookingReviewRow } from "@/types/api";

export async function listReviewsForEvent(
  slotId: string
): Promise<BookingReviewRow[]> {
  const { data } = await api.get<BookingReviewRow[]>(
    `/reviews/event/${slotId}`
  );
  return data;
}

export async function approveReview(
  reviewId: string,
  grade: number,
  notes?: string | null
): Promise<BookingReviewRow> {
  const { data } = await api.post<BookingReviewRow>(
    `/reviews/${reviewId}/approve`,
    { grade, grade_notes: notes ?? null }
  );
  return data;
}

export async function skipReview(
  reviewId: string,
  notes?: string | null
): Promise<BookingReviewRow> {
  const { data } = await api.post<BookingReviewRow>(
    `/reviews/${reviewId}/skip`,
    { notes: notes ?? null }
  );
  return data;
}

export async function flipNoShowToPending(
  reviewId: string
): Promise<BookingReviewRow> {
  const { data } = await api.post<BookingReviewRow>(
    `/reviews/${reviewId}/flip-no-show`,
    {}
  );
  return data;
}

export async function unlockReview(
  reviewId: string
): Promise<BookingReviewRow> {
  const { data } = await api.post<BookingReviewRow>(
    `/reviews/${reviewId}/unlock`,
    {}
  );
  return data;
}
