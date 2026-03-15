import api from "@/lib/api";
import type { ConversationListResponse } from "@/types/api";

export interface ConversationSearchFilters {
  search?: string;
  page?: number;
  page_size?: number;
}

export async function searchConversations(
  filters: ConversationSearchFilters = {}
): Promise<ConversationListResponse> {
  const { data } = await api.get<ConversationListResponse>("/conversations", {
    params: filters,
  });
  return data;
}
