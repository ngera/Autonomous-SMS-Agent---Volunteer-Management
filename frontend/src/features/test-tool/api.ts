import api from "@/lib/api";

export interface ToolCallInfo {
  tool: string;
  input: Record<string, unknown>;
  output: string;
}

export interface TestConversationRequest {
  message: string;
  mode: "customer" | "admin";
  history: { role: string; content: string }[];
  phone?: string;
  use_test_user?: boolean;
  save_conversation?: boolean;
}

export interface TestConversationResponse {
  reply: string;
  tool_calls: ToolCallInfo[];
  screened?: boolean;
  strike_number?: number | null;
}

export async function sendTestMessage(
  body: TestConversationRequest,
): Promise<TestConversationResponse> {
  const { data } = await api.post<TestConversationResponse>(
    "/test-conversation",
    body,
  );
  return data;
}
