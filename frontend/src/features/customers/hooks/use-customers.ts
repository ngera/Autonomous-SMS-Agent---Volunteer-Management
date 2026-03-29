import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  listCustomers,
  getCustomer,
  createCustomer,
  deleteCustomer,
  updateCustomer,
  importCustomersCsv,
  getCustomerBookings,
  getCustomerConversations,
  getCustomerPattern,
  setPatternOverride,
  clearPatternOverride,
  sendOptinOutreach,
  manualOptout,
  type CustomerFilters,
} from "../api";
import type {
  CustomerCreate,
  CustomerResponse,
  CustomerUpdate,
  PatternOverrideRequest,
  OptOutRequest,
} from "@/types/api";

export function useCustomers(filters: CustomerFilters) {
  return useQuery({
    queryKey: ["customers", filters],
    queryFn: () => listCustomers(filters),
    placeholderData: (prev) => prev,
  });
}

export function useCustomer(phone: string) {
  return useQuery({
    queryKey: ["customers", phone],
    queryFn: () => getCustomer(phone),
    enabled: !!phone,
  });
}

export function useCustomerBookings(phone: string) {
  return useQuery({
    queryKey: ["customers", phone, "bookings"],
    queryFn: () => getCustomerBookings(phone),
    enabled: !!phone,
  });
}

export function useCustomerConversations(phone: string) {
  return useQuery({
    queryKey: ["customers", phone, "conversations"],
    queryFn: () => getCustomerConversations(phone),
    enabled: !!phone,
  });
}

export function useCustomerPattern(phone: string) {
  return useQuery({
    queryKey: ["customers", phone, "pattern"],
    queryFn: () => getCustomerPattern(phone),
    enabled: !!phone,
  });
}

export function useUpdateCustomer() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ phone, body }: { phone: string; body: CustomerUpdate }) =>
      updateCustomer(phone, body),
    onSuccess: (data, variables) => {
      qc.setQueryData<CustomerResponse>(["customers", variables.phone], data);
      void qc.invalidateQueries({ queryKey: ["customers", variables.phone] });
      void qc.invalidateQueries({
        predicate: (query) => {
          const key = query.queryKey;
          return (
            Array.isArray(key) &&
            key[0] === "customers" &&
            key.length > 1 &&
            typeof key[1] === "object" &&
            key[1] !== null &&
            !Array.isArray(key[1])
          );
        },
      });
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
