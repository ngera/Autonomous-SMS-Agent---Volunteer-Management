import { useMutation } from "@tanstack/react-query";
import { sendTestMessage, type TestConversationRequest } from "../api";

export function useTestConversation() {
  return useMutation({
    mutationFn: (body: TestConversationRequest) => sendTestMessage(body),
  });
}
