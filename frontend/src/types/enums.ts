export const BookingStatus = {
  SCHEDULED: "scheduled",
  RESCHEDULED: "rescheduled",
  COMPLETED: "completed",
  CANCELLED: "cancelled",
  NO_SHOW: "no_show",
} as const;
export type BookingStatus = (typeof BookingStatus)[keyof typeof BookingStatus];

export const ContactSex = {
  MALE: "male",
  FEMALE: "female",
  NON_BINARY: "non_binary",
  PREFER_NOT_TO_SAY: "prefer_not_to_say",
} as const;
export type ContactSex = (typeof ContactSex)[keyof typeof ContactSex];

export const AnnouncementStatus = {
  DRAFT: "draft",
  SCHEDULED: "scheduled",
  SENDING: "sending",
  SENT: "sent",
  FAILED: "failed",
} as const;
export type AnnouncementStatus = (typeof AnnouncementStatus)[keyof typeof AnnouncementStatus];

export const ContactStatus = {
  ACTIVE: "active",
  SUSPENDED: "suspended",
  BANNED: "banned",
} as const;
export type ContactStatus = (typeof ContactStatus)[keyof typeof ContactStatus];

export const ConsentStatus = {
  UNCONTACTED: "uncontacted",
  PENDING: "pending",
  OPTED_IN: "opted_in",
  OPTED_OUT: "opted_out",
  BLOCKED: "blocked",
} as const;
export type ConsentStatus = (typeof ConsentStatus)[keyof typeof ConsentStatus];

export const ReminderStatus = {
  PENDING: "pending",
  SENT: "sent",
  BOOKED: "booked",
  SKIPPED: "skipped",
  NO_RESPONSE: "no_response",
  CANCELLED: "cancelled",
} as const;
export type ReminderStatus = (typeof ReminderStatus)[keyof typeof ReminderStatus];

export const AdminRole = {
  STAFF: "staff",
  MANAGER: "manager",
  OWNER: "owner",
  SUPER_ADMIN: "super_admin",
} as const;
export type AdminRole = (typeof AdminRole)[keyof typeof AdminRole];

export const SuspensionType = {
  AUTO_STRIKE: "auto_strike",
  AUTO_ABUSIVE: "auto_abusive",
  MANUAL: "manual",
} as const;
export type SuspensionType = (typeof SuspensionType)[keyof typeof SuspensionType];

export const ReviewDecision = {
  LIFTED: "lifted",
  CONFIRMED: "confirmed",
  BANNED: "banned",
} as const;
export type ReviewDecision = (typeof ReviewDecision)[keyof typeof ReviewDecision];

export const ConversationStatus = {
  ACTIVE: "active",
  COMPLETED: "completed",
  SUSPENDED: "suspended",
  EXPIRED: "expired",
} as const;
export type ConversationStatus = (typeof ConversationStatus)[keyof typeof ConversationStatus];

export const PatternConfidence = {
  DEFAULT: "default",
  EMERGING: "emerging",
  PERSONAL: "personal",
} as const;
export type PatternConfidence = (typeof PatternConfidence)[keyof typeof PatternConfidence];

export const BookingEventType = {
  CREATED: "created",
  RESCHEDULED: "rescheduled",
  STATUS_CHANGED: "status_changed",
  CANCELLED: "cancelled",
} as const;
export type BookingEventType = (typeof BookingEventType)[keyof typeof BookingEventType];

export const ChangedBy = {
  ADMIN: "admin",
  SMS: "sms",
  SYSTEM: "system",
} as const;
export type ChangedBy = (typeof ChangedBy)[keyof typeof ChangedBy];

export const ContactPreference = {
  EMAIL: "email",
  PHONE: "phone",
  SMS: "sms",
} as const;
export type ContactPreference = (typeof ContactPreference)[keyof typeof ContactPreference];

export const AvailabilitySlot = {
  WEEKDAY_AM: "weekday_am",
  WEEKDAY_PM: "weekday_pm",
  WEEKDAY_EVE: "weekday_eve",
  WEEKEND_AM: "weekend_am",
  WEEKEND_PM: "weekend_pm",
  WEEKEND_EVE: "weekend_eve",
} as const;
export type AvailabilitySlot = (typeof AvailabilitySlot)[keyof typeof AvailabilitySlot];

export const AVAILABILITY_OPTIONS: { value: AvailabilitySlot; label: string; short: string }[] = [
  { value: AvailabilitySlot.WEEKDAY_AM, label: "Weekday AM", short: "Wkd AM" },
  { value: AvailabilitySlot.WEEKDAY_PM, label: "Weekday PM", short: "Wkd PM" },
  { value: AvailabilitySlot.WEEKDAY_EVE, label: "Weekday eve", short: "Wkd eve" },
  { value: AvailabilitySlot.WEEKEND_AM, label: "Weekend AM", short: "Wkn AM" },
  { value: AvailabilitySlot.WEEKEND_PM, label: "Weekend PM", short: "Wkn PM" },
  { value: AvailabilitySlot.WEEKEND_EVE, label: "Weekend eve", short: "Wkn eve" },
];
