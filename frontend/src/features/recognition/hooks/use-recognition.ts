import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createDefinition,
  deactivateDefinition,
  grantRecognition,
  listDefinitions,
  listRecognitionsForContact,
  updateDefinition,
} from "../api";
import { useActiveTenantId } from "@/hooks/use-active-tenant";

export function useDefinitions(includeInactive: boolean = false) {
  const tenantId = useActiveTenantId();
  return useQuery({
    queryKey: ["recognition", "definitions", tenantId, includeInactive],
    queryFn: () => listDefinitions(includeInactive),
    enabled: tenantId !== "none",
  });
}

export function useCreateDefinition() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: createDefinition,
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ["recognition", "definitions"] }),
  });
}

export function useUpdateDefinition() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      body,
    }: {
      id: string;
      body: Parameters<typeof updateDefinition>[1];
    }) => updateDefinition(id, body),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ["recognition", "definitions"] }),
  });
}

export function useDeactivateDefinition() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: deactivateDefinition,
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ["recognition", "definitions"] }),
  });
}

export function useGrantRecognition() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: grantRecognition,
    onSuccess: (data) => {
      qc.invalidateQueries({
        queryKey: ["recognition", "contact"],
      });
      return data;
    },
  });
}

export function useRecognitionsForContact(contactId: string | undefined) {
  return useQuery({
    queryKey: ["recognition", "contact", contactId],
    queryFn: () => listRecognitionsForContact(contactId!),
    enabled: !!contactId,
  });
}
