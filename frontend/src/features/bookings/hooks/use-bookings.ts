import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  listBookings,
  getBooking,
  createBooking,
  rescheduleBooking,
  updateBookingStatus,
  cancelBooking,
  getBookingHistory,
  getAvailableSlots,
  type BookingFilters,
} from "../api";
import { useActiveTenantId } from "@/hooks/use-active-tenant";

export function useBookings(filters: BookingFilters) {
  const tenantId = useActiveTenantId();
  return useQuery({
    queryKey: ["bookings", tenantId, filters],
    queryFn: () => listBookings(filters),
    placeholderData: (prev) => prev,
    enabled: tenantId !== "none",
  });
}

export function useBooking(id: string) {
  const tenantId = useActiveTenantId();
  return useQuery({
    queryKey: ["bookings", tenantId, id],
    queryFn: () => getBooking(id),
    enabled: !!id && tenantId !== "none",
  });
}

export function useBookingHistory(id: string) {
  const tenantId = useActiveTenantId();
  return useQuery({
    queryKey: ["bookings", tenantId, id, "history"],
    queryFn: () => getBookingHistory(id),
    enabled: !!id && tenantId !== "none",
  });
}

export function useAvailableSlots(date: string, appointmentTypeId: string) {
  const tenantId = useActiveTenantId();
  return useQuery({
    queryKey: ["availability", "slots", tenantId, date, appointmentTypeId],
    queryFn: () => getAvailableSlots(date, appointmentTypeId),
    enabled: !!date && !!appointmentTypeId && tenantId !== "none",
  });
}

export function useCreateBooking() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: createBooking,
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["bookings"] });
      void qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}

export function useRescheduleBooking() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: { new_scheduled_at: string } }) =>
      rescheduleBooking(id, body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["bookings"] });
      void qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}

export function useUpdateBookingStatus() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: { status: string; notes?: string } }) =>
      updateBookingStatus(id, body as Parameters<typeof updateBookingStatus>[1]),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["bookings"] });
      void qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}

export function useCancelBooking() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: cancelBooking,
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["bookings"] });
      void qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}
