import api from "@/lib/api";
import type {
  BookingListResponse,
  BookingResponse,
  BookingCreate,
  RescheduleRequest,
  StatusUpdateRequest,
  BookingHistoryResponse,
  EventRosterResponse,
  SlotResponse,
} from "@/types/api";

export interface BookingFilters {
  page?: number;
  page_size?: number;
  status?: string;
  appointment_type_id?: string;
  contact_phone?: string;
  date_from?: string;
  date_to?: string;
}

export async function listBookings(
  filters: BookingFilters = {}
): Promise<BookingListResponse> {
  const { data } = await api.get<BookingListResponse>("/bookings", {
    params: filters,
  });
  return data;
}

export async function getBooking(id: string): Promise<BookingResponse> {
  const { data } = await api.get<BookingResponse>(`/bookings/${id}`);
  return data;
}

export async function createBooking(
  body: BookingCreate
): Promise<BookingResponse> {
  const { data } = await api.post<BookingResponse>("/bookings", body);
  return data;
}

export async function rescheduleBooking(
  id: string,
  body: RescheduleRequest
): Promise<BookingResponse> {
  const { data } = await api.put<BookingResponse>(
    `/bookings/${id}/reschedule`,
    body
  );
  return data;
}

export async function updateBookingStatus(
  id: string,
  body: StatusUpdateRequest
): Promise<BookingResponse> {
  const { data } = await api.put<BookingResponse>(
    `/bookings/${id}/status`,
    body
  );
  return data;
}

export async function cancelBooking(id: string): Promise<void> {
  await api.delete(`/bookings/${id}`);
}

export async function getBookingHistory(
  id: string
): Promise<BookingHistoryResponse[]> {
  const { data } = await api.get<BookingHistoryResponse[]>(
    `/bookings/${id}/history`
  );
  return data;
}

export async function getBookingEventRoster(
  id: string
): Promise<EventRosterResponse> {
  const { data } = await api.get<EventRosterResponse>(
    `/bookings/${id}/event-roster`
  );
  return data;
}

export async function getSpecificSlotEventRoster(
  slotId: string
): Promise<EventRosterResponse> {
  const { data } = await api.get<EventRosterResponse>(
    `/availability/specific-slots/${slotId}/event-roster`
  );
  return data;
}

export async function getWeeklyRuleEventRoster(
  ruleId: string,
  date: string
): Promise<EventRosterResponse> {
  const { data } = await api.get<EventRosterResponse>(
    `/availability/rules/${ruleId}/event-roster`,
    { params: { date } }
  );
  return data;
}

export async function getAvailableSlots(
  date: string,
  appointmentTypeId: string
): Promise<SlotResponse[]> {
  const { data } = await api.get<SlotResponse[]>("/availability/slots", {
    params: { date, appointment_type_id: appointmentTypeId },
  });
  return data;
}
