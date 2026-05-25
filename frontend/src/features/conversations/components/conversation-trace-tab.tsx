import { useQuery } from "@tanstack/react-query";
import { ArrowRight, AlertCircle, Box, Cpu, MessageSquare, Pause, Route as RouteIcon, Wrench } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { getConversationTrace, type AgentCallLogEvent } from "../api";

interface ConversationTraceTabProps {
  conversationId: string;
}

/**
 * Per-turn timeline of orchestrator routing + agent invocations + tool
 * calls + LLM calls. Reads from agent_call_log via /conversations/{id}/trace.
 *
 * Rendered as a flat list of events grouped by turn_id. Each event is
 * a small card with source → destination chip, event icon, and any
 * tool / model / latency detail.
 */
export function ConversationTraceTab({ conversationId }: ConversationTraceTabProps) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["conversation-trace", conversationId],
    queryFn: () => getConversationTrace(conversationId),
    // Refresh every 5s in case a turn is in flight while the panel is open
    refetchInterval: 5000,
  });

  if (isLoading) {
    return (
      <p className="text-sm text-muted-foreground py-6">Loading trace...</p>
    );
  }
  if (error) {
    return (
      <p className="text-sm text-destructive py-6">
        Failed to load trace.
      </p>
    );
  }
  if (!data || data.total_events === 0) {
    return (
      <Card>
        <CardContent className="py-6 text-sm text-muted-foreground">
          No agent activity yet for this conversation. Once the orchestrator
          routes a message, every routing decision + tool call + LLM call
          will appear here.
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      <div className="text-xs text-muted-foreground">
        {data.turns.length} turn{data.turns.length === 1 ? "" : "s"} ·{" "}
        {data.total_events} event{data.total_events === 1 ? "" : "s"}
      </div>
      {data.turns.map((turn, idx) => (
        <Card key={turn.turn_id}>
          <CardContent className="space-y-2 py-3">
            <div className="flex items-center justify-between text-xs text-muted-foreground">
              <span className="font-medium text-foreground">
                Turn {idx + 1}
              </span>
              <span className="font-mono">{turn.turn_id.slice(0, 8)}</span>
            </div>
            <div className="space-y-1.5">
              {turn.events.map((event) => (
                <EventRow key={event.id} event={event} />
              ))}
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

function EventRow({ event }: { event: AgentCallLogEvent }) {
  const isError = event.status === "error";
  return (
    <div
      className={cn(
        "flex items-start gap-2 rounded-md border border-border px-2 py-1.5 text-xs",
        isError && "border-destructive/40 bg-destructive/5"
      )}
    >
      <EventIcon eventType={event.event_type} />
      <div className="flex-1 space-y-1">
        <div className="flex items-center gap-1.5 flex-wrap">
          <AgentChip name={event.source_agent} />
          {event.destination_agent && (
            <>
              <ArrowRight className="h-3 w-3 text-muted-foreground" />
              <AgentChip name={event.destination_agent} />
            </>
          )}
          <Badge variant="outline" className="text-[10px]">
            {event.event_type}
          </Badge>
          {event.tool_name && (
            <Badge variant="secondary" className="text-[10px] font-mono">
              {event.tool_name}
            </Badge>
          )}
          {event.model_used && (
            <Badge variant="ghost" className="text-[10px] font-mono">
              {event.model_used.replace("claude-", "")}
            </Badge>
          )}
          {event.latency_ms != null && (
            <span className="text-[10px] text-muted-foreground font-mono">
              {event.latency_ms}ms
            </span>
          )}
        </div>
        {event.decision_reason && (
          <div className="text-muted-foreground">{event.decision_reason}</div>
        )}
        {event.tool_output_summary && (
          <div className="font-mono text-[11px] text-muted-foreground line-clamp-3">
            {event.tool_output_summary}
          </div>
        )}
        {event.error_message && (
          <div className="text-destructive">{event.error_message}</div>
        )}
      </div>
    </div>
  );
}

function AgentChip({ name }: { name: string }) {
  return (
    <span className="rounded bg-muted px-1.5 py-0.5 font-mono text-[10px] text-foreground">
      {name}
    </span>
  );
}

function EventIcon({ eventType }: { eventType: string }) {
  const Icon = (() => {
    switch (eventType) {
      case "route":
        return RouteIcon;
      case "tool_call":
        return Wrench;
      case "llm_call":
        return Cpu;
      case "send_sms":
        return MessageSquare;
      case "pause":
        return Pause;
      case "escalate":
        return AlertCircle;
      default:
        return Box;
    }
  })();
  return <Icon className="mt-0.5 h-3.5 w-3.5 shrink-0 text-muted-foreground" />;
}
