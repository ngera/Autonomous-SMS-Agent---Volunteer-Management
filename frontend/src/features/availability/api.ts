import api from "@/lib/api";
import type {
  AvailabilityRuleResponse,
  WeeklyScheduleUpdate,
  BlockedDateResponse,
  BlockedDateCreate,
  SpecificDateSlotResponse,
  SpecificDateSlotCreate,
  SlotResponse,
} from "@/types/api";

export async function getAvailabilityRules(): Promise<AvailabilityRuleResponse[]> {
  const { data } = await api.get<AvailabilityRuleResponse[]>("/availability/rules");
  return data;
}

export async function updateAvailabilityRules(
  body: WeeklyScheduleUpdate
): Promise<AvailabilityRuleResponse[]> {
  const { data } = await api.put<AvailabilityRuleResponse[]>("/availability/rules", body);
  return data;
}

export async function getBlockedDates(): Promise<BlockedDateResponse[]> {
  const { data } = await api.get<BlockedDateResponse[]>("/availability/blocked-dates");
  return data;
}

export async function createBlockedDate(body: BlockedDateCreate): Promise<BlockedDateResponse> {
  const { data } = await api.post<BlockedDateResponse>("/availability/blocked-dates", body);
  return data;
}

export async function deleteBlockedDate(id: string): Promise<void> {
  await api.delete(`/availability/blocked-dates/${id}`);
}

export async function listSpecificDateSlots(): Promise<SpecificDateSlotResponse[]> {
  const { data } = await api.get<SpecificDateSlotResponse[]>("/availability/specific-slots");
  return data;
}

export async function createSpecificDateSlot(body: SpecificDateSlotCreate): Promise<SpecificDateSlotResponse> {
  const { data } = await api.post<SpecificDateSlotResponse>("/availability/specific-slots", body);
  return data;
}

export async function deleteSpecificDateSlot(id: string): Promise<void> {
  await api.delete(`/availability/specific-slots/${id}`);
}

export async function getSlotPreview(
  date: string,
  appointmentTypeId: string
): Promise<SlotResponse[]> {
  const { data } = await api.get<SlotResponse[]>("/availability/slots", {
    params: { date, appointment_type_id: appointmentTypeId },
  });
  return data;
}
