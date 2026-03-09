import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import {
  BOOKING_STATUS_LABELS,
  BOOKING_STATUS_COLORS,
  CONSENT_STATUS_LABELS,
  CONSENT_STATUS_COLORS,
  REMINDER_STATUS_LABELS,
  REMINDER_STATUS_COLORS,
  CONVERSATION_STATUS_COLORS,
  CONFIDENCE_LABELS,
  CONFIDENCE_COLORS,
  SUSPENSION_TYPE_LABELS,
  REVIEW_DECISION_LABELS,
} from "@/lib/constants";
import type { BookingStatus, ConsentStatus, ReminderStatus, ConversationStatus, PatternConfidence, SuspensionType, ReviewDecision } from "@/types/enums";

type StatusType =
  | { type: "booking"; value: BookingStatus }
  | { type: "consent"; value: ConsentStatus }
  | { type: "reminder"; value: ReminderStatus }
  | { type: "conversation"; value: ConversationStatus }
  | { type: "confidence"; value: PatternConfidence }
  | { type: "suspension"; value: SuspensionType }
  | { type: "review"; value: ReviewDecision };

const STATUS_MAPS: Record<string, { labels: Record<string, string>; colors: Record<string, string> }> = {
  booking: { labels: BOOKING_STATUS_LABELS, colors: BOOKING_STATUS_COLORS },
  consent: { labels: CONSENT_STATUS_LABELS, colors: CONSENT_STATUS_COLORS },
  reminder: { labels: REMINDER_STATUS_LABELS, colors: REMINDER_STATUS_COLORS },
  conversation: { labels: { active: "Active", completed: "Completed", suspended: "Suspended", expired: "Expired" }, colors: CONVERSATION_STATUS_COLORS },
  confidence: { labels: CONFIDENCE_LABELS, colors: CONFIDENCE_COLORS },
  suspension: { labels: SUSPENSION_TYPE_LABELS, colors: { auto_strike: "bg-red-100 text-red-800", auto_abusive: "bg-red-200 text-red-900", manual: "bg-amber-100 text-amber-800" } },
  review: { labels: REVIEW_DECISION_LABELS, colors: { lifted: "bg-green-100 text-green-800", confirmed: "bg-red-100 text-red-800", banned: "bg-red-200 text-red-900" } },
};

export function StatusBadge(props: StatusType) {
  const map = STATUS_MAPS[props.type];
  const label = map?.labels[props.value] || props.value;
  const colorClass = map?.colors[props.value] || "bg-gray-100 text-gray-800";

  return (
    <Badge variant="outline" className={cn("border-0 font-medium", colorClass)}>
      {label}
    </Badge>
  );
}
