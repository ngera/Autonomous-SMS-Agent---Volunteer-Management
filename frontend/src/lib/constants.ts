import {
  BookingStatus,
  ConsentStatus,
  ReminderStatus,
  AdminRole,
  SuspensionType,
  ReviewDecision,
  ConversationStatus,
  PatternConfidence,
} from "@/types/enums";

export const BOOKING_STATUS_LABELS: Record<BookingStatus, string> = {
  [BookingStatus.SCHEDULED]: "Scheduled",
  [BookingStatus.RESCHEDULED]: "Rescheduled",
  [BookingStatus.COMPLETED]: "Completed",
  [BookingStatus.CANCELLED]: "Cancelled",
  [BookingStatus.NO_SHOW]: "No Show",
};

export const BOOKING_STATUS_COLORS: Record<BookingStatus, string> = {
  [BookingStatus.SCHEDULED]: "bg-blue-100 text-blue-800",
  [BookingStatus.RESCHEDULED]: "bg-amber-100 text-amber-800",
  [BookingStatus.COMPLETED]: "bg-green-100 text-green-800",
  [BookingStatus.CANCELLED]: "bg-red-100 text-red-800",
  [BookingStatus.NO_SHOW]: "bg-gray-100 text-gray-800",
};

export const CONSENT_STATUS_LABELS: Record<ConsentStatus, string> = {
  [ConsentStatus.UNCONTACTED]: "Uncontacted",
  [ConsentStatus.PENDING]: "Pending",
  [ConsentStatus.OPTED_IN]: "Opted In",
  [ConsentStatus.OPTED_OUT]: "Opted Out",
  [ConsentStatus.BLOCKED]: "Blocked",
};

export const CONSENT_STATUS_COLORS: Record<ConsentStatus, string> = {
  [ConsentStatus.UNCONTACTED]: "bg-gray-100 text-gray-800",
  [ConsentStatus.PENDING]: "bg-amber-100 text-amber-800",
  [ConsentStatus.OPTED_IN]: "bg-green-100 text-green-800",
  [ConsentStatus.OPTED_OUT]: "bg-red-100 text-red-800",
  [ConsentStatus.BLOCKED]: "bg-red-200 text-red-900",
};

export const REMINDER_STATUS_LABELS: Record<ReminderStatus, string> = {
  [ReminderStatus.PENDING]: "Pending",
  [ReminderStatus.SENT]: "Sent",
  [ReminderStatus.BOOKED]: "Booked",
  [ReminderStatus.SKIPPED]: "Skipped",
  [ReminderStatus.NO_RESPONSE]: "No Response",
  [ReminderStatus.CANCELLED]: "Cancelled",
};

export const REMINDER_STATUS_COLORS: Record<ReminderStatus, string> = {
  [ReminderStatus.PENDING]: "bg-amber-100 text-amber-800",
  [ReminderStatus.SENT]: "bg-blue-100 text-blue-800",
  [ReminderStatus.BOOKED]: "bg-green-100 text-green-800",
  [ReminderStatus.SKIPPED]: "bg-gray-100 text-gray-800",
  [ReminderStatus.NO_RESPONSE]: "bg-red-100 text-red-800",
  [ReminderStatus.CANCELLED]: "bg-gray-100 text-gray-800",
};

export const ADMIN_ROLE_LABELS: Record<AdminRole, string> = {
  [AdminRole.STAFF]: "Staff",
  [AdminRole.MANAGER]: "Manager",
  [AdminRole.OWNER]: "Owner",
  [AdminRole.SUPER_ADMIN]: "Super Admin",
};

export const ROLE_HIERARCHY: Record<AdminRole, number> = {
  [AdminRole.STAFF]: 0,
  [AdminRole.MANAGER]: 1,
  [AdminRole.OWNER]: 2,
  [AdminRole.SUPER_ADMIN]: 3,
};

export const SUSPENSION_TYPE_LABELS: Record<SuspensionType, string> = {
  [SuspensionType.AUTO_STRIKE]: "Auto (Strikes)",
  [SuspensionType.AUTO_ABUSIVE]: "Auto (Abusive)",
  [SuspensionType.MANUAL]: "Manual",
};

export const REVIEW_DECISION_LABELS: Record<ReviewDecision, string> = {
  [ReviewDecision.LIFTED]: "Lifted",
  [ReviewDecision.CONFIRMED]: "Confirmed",
  [ReviewDecision.BANNED]: "Banned",
};

export const CONVERSATION_STATUS_COLORS: Record<ConversationStatus, string> = {
  [ConversationStatus.ACTIVE]: "bg-green-100 text-green-800",
  [ConversationStatus.COMPLETED]: "bg-gray-100 text-gray-800",
  [ConversationStatus.SUSPENDED]: "bg-red-100 text-red-800",
  [ConversationStatus.EXPIRED]: "bg-amber-100 text-amber-800",
};

export const CONFIDENCE_LABELS: Record<PatternConfidence, string> = {
  [PatternConfidence.DEFAULT]: "Default",
  [PatternConfidence.EMERGING]: "Emerging",
  [PatternConfidence.PERSONAL]: "Personal",
};

export const CONFIDENCE_COLORS: Record<PatternConfidence, string> = {
  [PatternConfidence.DEFAULT]: "bg-gray-100 text-gray-800",
  [PatternConfidence.EMERGING]: "bg-amber-100 text-amber-800",
  [PatternConfidence.PERSONAL]: "bg-green-100 text-green-800",
};

export const DAYS_OF_WEEK = [
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
  "Sunday",
] as const;
