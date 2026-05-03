import { useQuery, useQueries, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  listCustomers,
  listCustomersForTenant,
  createCustomerForTenant,
  getCustomer,
  createCustomer,
  deleteCustomer,
  updateCustomer,
  importCustomersCsv,
  getCustomerBookings,
  getCustomerConversations,
  getCustomerPattern,
  getCustomerVolunteerStats,
  getVolunteerHoursSummary,
  setPatternOverride,
  clearPatternOverride,
  sendOptinOutreach,
  manualOptout,
  type CustomerFilters,
} from "../api";
import type {
  CustomerCreate,
  CustomerResponse,
  CustomerWithTenant,
  CustomerUpdate,
  PatternOverrideRequest,
  OptOutRequest,
  TenantResponse,
} from "@/types/api";
import { useActiveTenantId } from "@/hooks/use-active-tenant";

export function useCustomers(filters: CustomerFilters) {
  const tenantId = useActiveTenantId();
  return useQuery({
    queryKey: ["customers", tenantId, filters],
    queryFn: () => listCustomers(filters),
    placeholderData: (prev) => prev,
    enabled: tenantId !== "none",
  });
}

export function useMultiTenantCustomers(
  tenantIds: string[],
  tenants: TenantResponse[],
  filters: CustomerFilters
) {
  const results = useQueries({
    queries: tenantIds.map((tid) => ({
      queryKey: ["customers", tid, filters],
      queryFn: () => listCustomersForTenant(tid, filters),
    })),
  });

  const isLoading = results.some((r) => r.isLoading);
  const tenantMap = new Map(tenants.map((t) => [t.id, t.name]));

  const data: CustomerWithTenant[] = results.flatMap((r, i) =>
    (r.data?.items ?? []).map((c) => ({
      ...c,
      tenant_id: tenantIds[i],
      tenant_name: tenantMap.get(tenantIds[i]) ?? "Unknown",
    }))
  );

  // Sort by tenant name, then by customer name
  data.sort((a, b) => {
    const t = a.tenant_name.localeCompare(b.tenant_name);
    if (t !== 0) return t;
    return (a.name ?? "").localeCompare(b.name ?? "");
  });

  return { data, isLoading };
}

export function useCreateCustomerForTenant() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ tenantId, body }: { tenantId: string; body: CustomerCreate }) =>
      createCustomerForTenant(tenantId, body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["customers"] });
    },
  });
}

export function useCustomer(phone: string) {
  const tenantId = useActiveTenantId();
  return useQuery({
    queryKey: ["customers", tenantId, phone],
    queryFn: () => getCustomer(phone),
    enabled: !!phone && tenantId !== "none",
  });
}

export function useCustomerBookings(phone: string) {
  const tenantId = useActiveTenantId();
  return useQuery({
    queryKey: ["customers", tenantId, phone, "bookings"],
    queryFn: () => getCustomerBookings(phone),
    enabled: !!phone && tenantId !== "none",
  });
}

export function useCustomerConversations(phone: string) {
  const tenantId = useActiveTenantId();
  return useQuery({
    queryKey: ["customers", tenantId, phone, "conversations"],
    queryFn: () => getCustomerConversations(phone),
    enabled: !!phone && tenantId !== "none",
  });
}

export function useCustomerPattern(phone: string) {
  const tenantId = useActiveTenantId();
  return useQuery({
    queryKey: ["customers", tenantId, phone, "pattern"],
    queryFn: () => getCustomerPattern(phone),
    enabled: !!phone && tenantId !== "none",
  });
}

export function useCustomerVolunteerStats(phone: string) {
  const tenantId = useActiveTenantId();
  return useQuery({
    queryKey: ["customers", tenantId, phone, "volunteer-stats"],
    queryFn: () => getCustomerVolunteerStats(phone),
    enabled: !!phone && tenantId !== "none",
  });
}

export function useVolunteerHoursSummary() {
  const tenantId = useActiveTenantId();
  return useQuery({
    queryKey: ["customers", tenantId, "hours-summary"],
    queryFn: getVolunteerHoursSummary,
    enabled: tenantId !== "none",
  });
}

export function useUpdateCustomer() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ phone, body }: { phone: string; body: CustomerUpdate }) =>
      updateCustomer(phone, body),
    onSuccess: (data, variables) => {
      qc.setQueryData<CustomerResponse>(["customers", variables.phone], data);
      void qc.invalidateQueries({ queryKey: ["customers"] });
    },
  });
}

export function useCreateCustomer() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: CustomerCreate) => createCustomer(body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["customers"] });
    },
  });
}

export function useDeleteCustomer() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: deleteCustomer,
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["customers"] });
    },
  });
}

export function useImportCsv() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: importCustomersCsv,
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["customers"] });
    },
  });
}

export function useSetPatternOverride() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ phone, body }: { phone: string; body: PatternOverrideRequest }) =>
      setPatternOverride(phone, body),
    onSuccess: (_d, v) => {
      void qc.invalidateQueries({ queryKey: ["customers", v.phone, "pattern"] });
    },
  });
}

export function useClearPatternOverride() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: clearPatternOverride,
    onSuccess: (_d, phone) => {
      void qc.invalidateQueries({ queryKey: ["customers", phone, "pattern"] });
    },
  });
}

export function useSendOptinOutreach() {
  return useMutation({ mutationFn: sendOptinOutreach });
}

export function useManualOptout() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ phone, body }: { phone: string; body: OptOutRequest }) =>
      manualOptout(phone, body),
    onSuccess: (_d, v) => {
      void qc.invalidateQueries({ queryKey: ["customers", v.phone] });
      void qc.invalidateQueries({ queryKey: ["customers"] });
    },
  });
}
