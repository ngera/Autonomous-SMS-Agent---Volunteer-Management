import { useQuery } from "@tanstack/react-query";
import { searchConversations, type ConversationSearchFilters } from "../api";
import { useActiveTenantId } from "@/hooks/use-active-tenant";

export function useConversations(filters: ConversationSearchFilters) {
  const tenantId = useActiveTenantId();
  return useQuery({
    queryKey: ["conversations", tenantId, filters],
    queryFn: () => searchConversations(filters),
    enabled: tenantId !== "none",
    placeholderData: (prev) => prev,
  });
}
