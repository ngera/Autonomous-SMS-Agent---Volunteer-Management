import type {
  AnnouncementStatus,
  BookingStatus,
  ConsentStatus,
  ContactSex,
  ContactStatus,
  ConversationStatus,
  AdminRole,
  SuspensionType,
  ReviewDecision,
  ReminderStatus,
  PatternConfidence,
  BookingEventType,
  ChangedBy,
} from "./enums";

// ── Generic ──

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

// ── Auth ──

export interface LoginRequest {
  email: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface RefreshRequest {
  refresh_token: string;
}

export interface PasswordResetRequest {
  email: string;
}

export interface MessageResponse {
  message: string;
}

// ── Dashboard ──

export interface DashboardSummary {
  todays_bookings_count: number;
  pending_conversations_count: number;
  reminders_today_count: number;
  unreviewed_suspensions_count: number;
  monthly_bookings: number;
  monthly_revenue: number;
  opt_in_rate: number;
  reminder_conversion_rate: number;
}

export interface TodaysBooking {
  id: string;
  contact_phone: string;
  contact_name: string | null;
  appointment_type_name: string;
  scheduled_at: string;
  status: string;
}

export interface NotificationResponse {
  id: string;
  type: string;
  title: string;
  body: string;
  reference_id: string | null;
  reference_type: string | null;
  created_at: string;
  read_at: string | null;
}

// ── Bookings ──

export interface BookingResponse {
  id: string;
  contact_phone: string;
  appointment_type_id: string;
  scheduled_at: string;
  confirmed_at: string | null;
  completed_at: string | null;
  status: BookingStatus;
  price_at_booking: number;
  calendar_event_id: string | null;
  ics_sequence: number;
  ics_new_url: string | null;
  ics_update_url: string | null;
  conversation_id: string | null;
  created_at: string;
  contact_name: string | null;
  appointment_type_name: string | null;
  duration_minutes: number | null;
}

export type BookingListResponse = PaginatedResponse<BookingResponse>;

export interface BookingCreate {
  contact_phone: string;
  appointment_type_id: string;
  scheduled_at: string;
  price_at_booking: number;
}

export interface RescheduleRequest {
  new_scheduled_at: string;
}

export interface StatusUpdateRequest {
  status: BookingStatus;
  notes?: string;
}

export interface BookingHistoryResponse {
  id: string;
  booking_id: string;
  event_type: BookingEventType;
  previous_scheduled_at: string | null;
  new_scheduled_at: string | null;
  previous_status: BookingStatus | null;
  new_status: BookingStatus | null;
  changed_by: ChangedBy;
  changed_by_admin_id: string | null;
  notes: string | null;
  created_at: string;
}

// ── Customers ──

export interface CustomerResponse {
  phone: string;
  name: string | null;
  email: string | null;
  sex: ContactSex | null;
  status: ContactStatus;
  reminder_preference_days: number;
  consent_status: ConsentStatus | null;
  preferred_appointment_type_ids: string[];
  created_at: string;
  updated_at: string;
}

export type CustomerListResponse = PaginatedResponse<CustomerResponse>;

export interface CustomerCreate {
  phone: string;
  name: string;
  email?: string;
  sex?: ContactSex;
  reminder_preference_days?: number;
  preferred_appointment_type_ids?: string[];
}

export interface CustomerUpdate {
  name?: string;
  email?: string;
  sex?: ContactSex | null;
  reminder_preference_days?: number;
  preferred_appointment_type_ids?: string[];
}

export interface CsvImportResponse {
  imported: number;
  skipped: number;
  errors: string[];
}

export interface OptOutRequest {
  reason: string;
}

// ── Patterns ──

export interface PatternResponse {
  id: string;
  contact_phone: string;
  appointment_type_id: string;
  completed_booking_count: number;
  calculated_interval_days: number | null;
  blended_interval_days: number | null;
  admin_default_days: number | null;
  confidence: PatternConfidence;
  outliers_removed: number;
  manual_override_days: number | null;
  last_calculated_at: string | null;
  next_due_date: string | null;
}

export interface PatternOverrideRequest {
  manual_override_days: number;
}

// ── Appointment Types ──

export interface AppointmentTypeResponse {
  id: string;
  name: string;
  duration_minutes: number;
  price: number;
  description: string | null;
  recurrence_weeks_default: number | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface AppointmentTypeCreate {
  name: string;
  duration_minutes: number;
  price: number;
  description?: string;
  recurrence_weeks_default?: number;
  is_active?: boolean;
}

export interface AppointmentTypeUpdate {
  name?: string;
  duration_minutes?: number;
  price?: number;
  description?: string;
  recurrence_weeks_default?: number;
  is_active?: boolean;
}

export interface RelatedServiceResponse {
  id: string;
  appointment_type_id: string;
  related_appointment_type_id: string;
  suggestion_message: string;
  created_at: string;
}

export interface RelatedServiceCreate {
  related_appointment_type_id: string;
  suggestion_message: string;
}

// ── Availability ──

export interface AvailabilityRuleResponse {
  id: string;
  day_of_week: number;
  label: string | null;
  start_time: string;
  end_time: string;
  slot_duration_minutes: number;
  buffer_minutes: number;
  is_active: boolean;
}

export interface AvailabilityRuleUpdate {
  day_of_week: number;
  label?: string;
  start_time: string;
  end_time: string;
  slot_duration_minutes: number;
  buffer_minutes?: number;
  is_active?: boolean;
}

export interface WeeklyScheduleUpdate {
  rules: AvailabilityRuleUpdate[];
}

export interface BlockedDateResponse {
  id: string;
  date_from: string;
  date_to: string;
  reason: string | null;
  created_at: string;
}

export interface BlockedDateCreate {
  date_from: string;
  date_to: string;
  reason?: string;
}

export interface SlotResponse {
  start: string;
  end: string;
}

// ── Reminders ──

export interface ReminderResponse {
  id: string;
  contact_phone: string;
  appointment_type_id: string;
  pattern_snapshot: Record<string, unknown> | null;
  scheduled_for: string;
  sent_at: string | null;
  follow_up_sent_at: string | null;
  status: ReminderStatus;
  converted_to_booking_id: string | null;
  skip_reason: string | null;
  created_at: string;
}

export interface ReminderListResponse {
  items: ReminderResponse[];
  total: number;
}

export interface ReminderTriggerRequest {
  contact_phone: string;
  appointment_type_id: string;
}

export interface ReminderUpdate {
  scheduled_for: string;
}

export interface ReminderCancelRequest {
  reason: string;
}

// ── Conversations ──

export interface ConversationResponse {
  id: string;
  contact_phone: string;
  message_history: Record<string, unknown>[];
  current_step: string | null;
  status: ConversationStatus;
  consent_verified_at: string | null;
  created_at: string;
  last_message_at: string;
}

export interface ConversationListResponse {
  items: ConversationResponse[];
  total: number;
}

// ── Suspensions ──

export interface SuspensionResponse {
  id: string;
  contact_phone: string;
  contact_name: string | null;
  suspended_at: string;
  suspension_type: SuspensionType;
  reason: string;
  strike_ids: string[] | null;
  conversation_id: string | null;
  notification_sent_at: string | null;
  reviewed_by_admin_id: string | null;
  reviewed_at: string | null;
  review_decision: ReviewDecision | null;
  review_notes: string | null;
  lifted_at: string | null;
}

export interface SuspensionListResponse {
  items: SuspensionResponse[];
  total: number;
}

export interface ReviewRequest {
  notes: string;
}

export interface ManualSuspendRequest {
  reason: string;
}

// ── Analytics ──

export interface BookingVolumePoint {
  period: string;
  count: number;
  appointment_type: string | null;
  status: string | null;
}

export interface RevenuePoint {
  period: string;
  revenue: number;
  appointment_type: string | null;
}

export interface RetentionMetrics {
  recurring_customer_rate: number;
  average_interval_accuracy: number;
  total_recurring_customers: number;
}

export interface ReminderAnalytics {
  total_sent: number;
  total_converted: number;
  conversion_rate: number;
  personal_conversion_rate: number;
  default_conversion_rate: number;
}

export interface ConsentFunnel {
  total_contacts: number;
  uncontacted: number;
  pending: number;
  opted_in: number;
  opted_out: number;
  opt_in_rate: number;
}

// ── Settings ──

export interface SystemSettingResponse {
  key: string;
  value: string;
  updated_at: string;
}

export interface SystemSettingsUpdate {
  settings: Record<string, string>;
}

// ── Admin Users ──

export interface AdminUserResponse {
  id: string;
  email: string;
  role: AdminRole;
  tenant_id: string | null;
  is_active: boolean;
  created_at: string;
  last_login_at: string | null;
}

export interface AdminUserCreate {
  email: string;
  password: string;
  role: AdminRole;
}

export interface AdminUserUpdate {
  role?: AdminRole;
  is_active?: boolean;
}

// ── Tenants ──

export interface TenantResponse {
  id: string;
  name: string;
  slug: string;
  is_active: boolean;
  business_name: string;
  business_domain: string;
  business_timezone: string;
  admin_panel_url: string;
  api_domain: string;
  twilio_phone_number: string | null;
  created_at: string;
  updated_at: string;
}

export interface TenantDetailResponse extends TenantResponse {
  has_twilio: boolean;
  has_anthropic: boolean;
  has_google_calendar: boolean;
  has_resend: boolean;
}

export interface TenantCreate {
  name: string;
  slug: string;
  business_name: string;
  business_domain?: string;
  business_timezone?: string;
  admin_panel_url?: string;
  api_domain?: string;
  twilio_account_sid?: string;
  twilio_auth_token?: string;
  twilio_phone_number?: string;
  anthropic_api_key?: string;
  google_client_id?: string;
  google_client_secret?: string;
  google_refresh_token?: string;
  resend_api_key?: string;
  resend_from_email?: string;
}

export interface TenantUpdate {
  name?: string;
  slug?: string;
  is_active?: boolean;
  business_name?: string;
  business_domain?: string;
  business_timezone?: string;
  admin_panel_url?: string;
  api_domain?: string;
  twilio_account_sid?: string;
  twilio_auth_token?: string;
  twilio_phone_number?: string;
  anthropic_api_key?: string;
  google_client_id?: string;
  google_client_secret?: string;
  google_refresh_token?: string;
  resend_api_key?: string;
  resend_from_email?: string;
}

export interface TenantListResponse {
  items: TenantResponse[];
  total: number;
}

// ── Announcements ──

export interface AnnouncementResponse {
  id: string;
  message: string;
  filter_appointment_type_ids: string[] | null;
  scheduled_at: string | null;
  sent_at: string | null;
  status: AnnouncementStatus;
  total_recipients: number;
  sent_count: number;
  failed_count: number;
  created_by_admin_id: string;
  created_at: string;
}

export type AnnouncementListResponse = PaginatedResponse<AnnouncementResponse>;

export interface AnnouncementCreate {
  message: string;
  filter_appointment_type_ids?: string[];
  scheduled_at?: string;
}
