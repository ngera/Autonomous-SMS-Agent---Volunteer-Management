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

export interface BulkDeleteConversationsPayload {
  /** ISO datetime — delete conversations whose last_message_at is older than this. */
  older_than?: string | null;
  contact_phone?: string | null;
  ids?: string[] | null;
}

export async function bulkDeleteConversations(
  payload: BulkDeleteConversationsPayload
): Promise<{ deleted_count: number }> {
  const { data } = await api.delete<{ deleted_count: number }>(
    "/conversations",
    { data: payload }
  );
  return data;
}

// Path A graph-shaped audit trace for one conversation. Rendered by
// the Trace tab on the conversation detail view.
export interface AgentCallLogEvent {
  id: string;
  created_at: string | null;
  source_agent: string;
  destination_agent: string | null;
  event_type: string;
  decision_reason: string | null;
  state_snapshot: Record<string, unknown> | null;
  tool_name: string | null;
  tool_input: Record<string, unknown> | null;
  tool_output_summary: string | null;
  model_used: string | null;
  input_tokens: number | null;
  output_tokens: number | null;
  latency_ms: number | null;
  status: string;
  error_message: string | null;
}

export interface ConversationTrace {
  conversation_id: string;
  turns: { turn_id: string; events: AgentCallLogEvent[] }[];
  total_events: number;
}

export async function getConversationTrace(
  conversationId: string,
  limit = 200
): Promise<ConversationTrace> {
  const { data } = await api.get<ConversationTrace>(
    `/conversations/${conversationId}/trace`,
    { params: { limit } }
  );
  return data;
}
