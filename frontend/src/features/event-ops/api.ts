import api from "@/lib/api";
import type {
  PendingServiceEntry,
  RunSheetResponse,
  ServiceEntryStatusResponse,
} from "@/types/api";

export async function getRunSheet(slotId: string): Promise<RunSheetResponse> {
  const { data } = await api.get<RunSheetResponse>(
    `/bookings/run-sheet/${slotId}`
  );
  return data;
}

export async function adminCheckin(
  bookingId: string,
  at?: string | null
): Promise<void> {
  await api.post(`/bookings/${bookingId}/checkin`, { at: at ?? null });
}

export async function adminCheckout(
  bookingId: string,
  at?: string | null
): Promise<void> {
  await api.post(`/bookings/${bookingId}/checkout`, { at: at ?? null });
}

// Phase 3 — pending service-log queue

export async function getPendingForSlot(
  slotId: string
): Promise<PendingServiceEntry[]> {
  const { data } = await api.get<PendingServiceEntry[]>(
    `/service-log/pending/${slotId}`
  );
  return data;
}

export async function approvePendingEntry(
  entryId: string,
  expectedVersion: number
): Promise<ServiceEntryStatusResponse> {
  const { data } = await api.post<ServiceEntryStatusResponse>(
    `/service-log/${entryId}/approve`,
    { expected_version: expectedVersion }
  );
  return data;
}

export async function rejectPendingEntry(
  entryId: string,
  expectedVersion: number,
  reason?: string | null
): Promise<ServiceEntryStatusResponse> {
  const { data } = await api.post<ServiceEntryStatusResponse>(
    `/service-log/${entryId}/reject`,
    { expected_version: expectedVersion, reason: reason ?? null }
  );
  return data;
}
