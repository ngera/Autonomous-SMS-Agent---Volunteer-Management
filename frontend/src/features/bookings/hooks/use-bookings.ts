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

export function useBookings(filters: BookingFilters) {
  return useQuery({
    queryKey: ["bookings", filters],
    queryFn: () => listBookings(filters),
    placeholderData: (prev) => prev,
  });
}

export function useBooking(id: string) {
  return useQuery({
    queryKey: ["bookings", id],
    queryFn: () => getBooking(id),
    enabled: !!id,
  });
}

export function useBookingHistory(id: string) {
  return useQuery({
    queryKey: ["bookings", id, "history"],
    queryFn: () => getBookingHistory(id),
    enabled: !!id,
  });
}

export function useAvailableSlots(date: string, appointmentTypeId: string) {
  return useQuery({
    queryKey: ["availability", "slots", date, appointmentTypeId],
    queryFn: () => getAvailableSlots(date, appointmentTypeId),
    enabled: !!date && !!appointmentTypeId,
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
