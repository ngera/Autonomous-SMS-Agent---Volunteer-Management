import { useQuery } from "@tanstack/react-query";
import { searchConversations, type ConversationSearchFilters } from "../api";

export function useConversations(filters: ConversationSearchFilters) {
  return useQuery({
    queryKey: ["conversations", filters],
    queryFn: () => searchConversations(filters),
    enabled: !!filters.search,
    placeholderData: (prev) => prev,
  });
}
