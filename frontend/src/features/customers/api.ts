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
} from "@/types/api";

export interface CustomerFilters {
  page?: number;
  page_size?: number;
  search?: string;
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

export async function deleteCustomer(phone: string): Promise<void> {
  await api.delete(`/customers/${encodeURIComponent(phone)}`);
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

export async function sendOptinOutreach(phone: string): Promise<void> {
  await api.post(`/customers/${encodeURIComponent(phone)}/optin-outreach`);
}

export async function manualOptout(
  phone: string,
  body: OptOutRequest
): Promise<void> {
  await api.post(`/customers/${encodeURIComponent(phone)}/optout`, body);
}
