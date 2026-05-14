import api from "@/lib/api";
import type {
  CustomerCreate,
  CustomerListResponse,
  CustomerResponse,
  CustomerUpdate,
  CsvImportResponse,
  BookingResponse,
  ConversationResponse,
  PatternResponse,
  PatternOverrideRequest,
  OptOutRequest,
  VolunteerStatsResponse,
  VolunteerHoursSummary,
} from "@/types/api";
import type { ContactStatus, ConsentStatus, AvailabilitySlot } from "@/types/enums";

export interface CustomerFilters {
  page?: number;
  page_size?: number;
  search?: string;
  status?: ContactStatus;
  consent_status?: ConsentStatus;
  background_check_required?: boolean;
  availability?: AvailabilitySlot;
}

export async function listCustomers(
  filters: CustomerFilters = {}
): Promise<CustomerListResponse> {
  const { data } = await api.get<CustomerListResponse>("/customers", {
    params: filters,
  });
  return data;
}

export async function listCustomersForTenant(
  tenantId: string,
  filters: CustomerFilters = {}
): Promise<CustomerListResponse> {
  const { data } = await api.get<CustomerListResponse>("/customers", {
    params: filters,
    headers: { "X-Tenant-Id": tenantId },
  });
  return data;
}

export async function getCustomer(phone: string): Promise<CustomerResponse> {
  const { data } = await api.get<CustomerResponse>(
    `/customers/${encodeURIComponent(phone)}`
  );
  return data;
}

export async function createCustomer(
  body: CustomerCreate
): Promise<CustomerResponse> {
  const { data } = await api.post<CustomerResponse>("/customers", body);
  return data;
}

export async function createCustomerForTenant(
  tenantId: string,
  body: CustomerCreate
): Promise<CustomerResponse> {
  const { data } = await api.post<CustomerResponse>("/customers", body, {
    headers: { "X-Tenant-Id": tenantId },
  });
  return data;
}

export interface DeleteCustomerResult {
  action: "deleted" | "archived";
  booking_count?: number;
  conversation_count?: number;
}

export async function deleteCustomer(phone: string): Promise<DeleteCustomerResult> {
  const { data } = await api.delete<DeleteCustomerResult>(
    `/customers/${encodeURIComponent(phone)}`
  );
  return data;
}

export async function updateCustomer(
  phone: string,
  body: CustomerUpdate
): Promise<CustomerResponse> {
  const { data } = await api.put<CustomerResponse>(
    `/customers/${encodeURIComponent(phone)}`,
    body
  );
  return data;
}

export async function importCustomersCsv(
  file: File
): Promise<CsvImportResponse> {
  const formData = new FormData();
  formData.append("file", file);
  const { data } = await api.post<CsvImportResponse>(
    "/customers/import",
    formData,
    { headers: { "Content-Type": "multipart/form-data" } }
  );
  return data;
}

export async function getCustomerBookings(
  phone: string
): Promise<BookingResponse[]> {
  const { data } = await api.get<BookingResponse[]>(
    `/customers/${encodeURIComponent(phone)}/bookings`
  );
  return data;
}

export async function getCustomerConversations(
  phone: string
): Promise<ConversationResponse[]> {
  const { data } = await api.get<ConversationResponse[]>(
    `/customers/${encodeURIComponent(phone)}/conversations`
  );
  return data;
}

export async function getCustomerPattern(
  phone: string
): Promise<PatternResponse[]> {
  const { data } = await api.get<PatternResponse[]>(
    `/customers/${encodeURIComponent(phone)}/pattern`
  );
  return data;
}

export async function setPatternOverride(
  phone: string,
  body: PatternOverrideRequest
): Promise<PatternResponse> {
  const { data } = await api.put<PatternResponse>(
    `/customers/${encodeURIComponent(phone)}/pattern/override`,
    body
  );
  return data;
}

export async function clearPatternOverride(phone: string): Promise<void> {
  await api.delete(`/customers/${encodeURIComponent(phone)}/pattern/override`);
}

export async function getCustomerVolunteerStats(
  phone: string
): Promise<VolunteerStatsResponse> {
  const { data } = await api.get<VolunteerStatsResponse>(
    `/customers/${encodeURIComponent(phone)}/volunteer-stats`
  );
  return data;
}

export interface RecentMessage {
  role: "user" | "assistant";
  content: string;
  timestamp: string;
}

export interface RecentMessagesResponse {
  messages: RecentMessage[];
  days: number;
}

export async function getCustomerRecentMessages(
  phone: string,
  days: number = 7
): Promise<RecentMessagesResponse> {
  const { data } = await api.get<RecentMessagesResponse>(
    `/customers/${encodeURIComponent(phone)}/recent-messages`,
    { params: { days } }
  );
  return data;
}

export async function getVolunteerHoursSummary(): Promise<VolunteerHoursSummary> {
  const { data } = await api.get<VolunteerHoursSummary>("/customers/hours-summary");
  return data;
}

export async function sendOptinOutreach(phone: string): Promise<void> {
  await api.post(`/customers/${encodeURIComponent(phone)}/optin-outreach`);
}

export async function manualOptout(
  phone: string,
  body: OptOutRequest
): Promise<void> {
  await api.post(`/customers/${encodeURIComponent(phone)}/optout`, body);
}
