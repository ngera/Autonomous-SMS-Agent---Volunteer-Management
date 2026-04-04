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
  save_conversation?: boolean;
}

export interface TestConversationResponse {
  reply: string;
  tool_calls: ToolCallInfo[];
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
