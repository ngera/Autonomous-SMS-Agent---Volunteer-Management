import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { StatusBadge } from "@/components/shared/status-badge";
import { formatDateTime } from "@/lib/utils";
import type { ConversationResponse } from "@/types/api";

interface ConversationMessageViewerProps {
  conversation: ConversationResponse;
}

export function ConversationMessageViewer({
  conversation,
}: ConversationMessageViewerProps) {
  const messages = conversation.message_history ?? [];

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <div className="space-y-1">
          <CardTitle className="text-base">
            {conversation.contact_phone}
          </CardTitle>
          <p className="text-xs text-muted-foreground">
            Started {formatDateTime(conversation.created_at)} · Last message{" "}
            {formatDateTime(conversation.last_message_at)}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <StatusBadge type="conversation" value={conversation.status} />
          {conversation.current_step && (
            <Badge variant="outline">{conversation.current_step}</Badge>
          )}
        </div>
      </CardHeader>
      <CardContent>
        {messages.length === 0 ? (
          <p className="text-sm text-muted-foreground">No messages.</p>
        ) : (
          <div className="space-y-3 max-h-96 overflow-y-auto">
            {messages.map((msg, i) => {
              const role = (msg.role as string) ?? "unknown";
              const content = (msg.content as string) ?? JSON.stringify(msg);
              const isSystem = role === "assistant" || role === "system";
              return (
                <div
                  key={i}
                  className={`flex ${isSystem ? "justify-start" : "justify-end"}`}
                >
                  <div
                    className={`max-w-[75%] rounded-lg px-3 py-2 text-sm ${
                      isSystem
                        ? "bg-muted text-foreground"
                        : "bg-primary text-primary-foreground"
                    }`}
                  >
                    <p className="text-xs font-medium mb-1 opacity-70">{role}</p>
                    <p className="whitespace-pre-wrap">{content}</p>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
