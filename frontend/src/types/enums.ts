export enum BookingStatus {
  SCHEDULED = "scheduled",
  RESCHEDULED = "rescheduled",
  COMPLETED = "completed",
  CANCELLED = "cancelled",
  NO_SHOW = "no_show",
}

export enum ContactStatus {
  ACTIVE = "active",
  SUSPENDED = "suspended",
  BANNED = "banned",
}

export enum ConsentStatus {
  UNCONTACTED = "uncontacted",
  PENDING = "pending",
  OPTED_IN = "opted_in",
  OPTED_OUT = "opted_out",
  BLOCKED = "blocked",
}

export enum ReminderStatus {
  PENDING = "pending",
  SENT = "sent",
  BOOKED = "booked",
  SKIPPED = "skipped",
  NO_RESPONSE = "no_response",
  CANCELLED = "cancelled",
}

export enum AdminRole {
  STAFF = "staff",
  MANAGER = "manager",
  OWNER = "owner",
}

export enum SuspensionType {
  AUTO_STRIKE = "auto_strike",
  AUTO_ABUSIVE = "auto_abusive",
  MANUAL = "manual",
}

export enum ReviewDecision {
  LIFTED = "lifted",
  CONFIRMED = "confirmed",
  BANNED = "banned",
}

export enum ConversationStatus {
  ACTIVE = "active",
  COMPLETED = "completed",
  SUSPENDED = "suspended",
  EXPIRED = "expired",
}

export enum PatternConfidence {
  DEFAULT = "default",
  EMERGING = "emerging",
  PERSONAL = "personal",
}

export enum BookingEventType {
  CREATED = "created",
  RESCHEDULED = "rescheduled",
  STATUS_CHANGED = "status_changed",
  CANCELLED = "cancelled",
}

export enum ChangedBy {
  ADMIN = "admin",
  SMS = "sms",
  SYSTEM = "system",
}
