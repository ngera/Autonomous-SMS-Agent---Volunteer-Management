import type {
  AnnouncementStatus,
  AvailabilitySlot,
  BookingStatus,
  ConsentStatus,
  ContactPreference,
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

export interface VolunteersByService {
  service_name: string;
  available: number;
  min_per_slot: number;
  max_per_slot: number;
  occurrences_30d: number;
  buffer: number;
  buffer_pct: number;
}

export interface DashboardSummary {
  todays_bookings_count: number;
  unreviewed_suspensions_count: number;
  suspended_or_banned_count: number;
  monthly_bookings: number;
  slots_needing_bookings: number;
  total_volunteers: number;
  volunteers_by_service: VolunteersByService[];
}

export interface RosterEntry {
  name: string;
  phone: string;
  visibility: "hidden" | "first_name" | "full_name";
}

export interface WeeklySlotStatus {
  date: string;
  day_name: string;
  window_label: string | null;
  window_time: string;
  service_name: string;
  appointment_type_id: string;
  min_required: number;
  max_allowed: number;
  booked: number;
  status: "needs_more" | "met_minimum" | "full";
  source: "recurring" | "one_time";
  source_id: string | null;
  location: string | null;
  allow_roster_sharing: boolean;
  roster: RosterEntry[];
  last_reminder_sent: string | null;
  last_announcement_sent: string | null;
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

export interface EventRosterSignup {
  booking_id: string;
  phone: string;
  name: string | null;
  status: BookingStatus;
  scheduled_at: string;
}

export interface EventRosterService {
  appointment_type_id: string;
  name: string;
  category: string;
  min_required: number;
  max_allowed: number;
  signups: EventRosterSignup[];
}

export interface EventRosterEvent {
  source: "specific_date" | "weekly_rule" | "ad_hoc";
  source_id: string | null;
  label: string | null;
  location: string | null;
  date: string;
  start_time: string;
  end_time: string;
}

export interface EventRosterResponse {
  event: EventRosterEvent | null;
  services: EventRosterService[];
}

// ── Customers ──

export interface WeeklyHourBlock {
  day_of_week: number; // 0=Mon..6=Sun
  start_time: string; // "HH:MM:SS" or "HH:MM"
  end_time: string;
}

export interface CustomerResponse {
  id: string;
  phone: string;
  name: string | null;
  email: string | null;
  sex: ContactSex | null;
  status: ContactStatus;
  all_services_enabled: boolean;
  background_check_required: boolean;
  availability: AvailabilitySlot[];
  weekly_hours: WeeklyHourBlock[];
  unavailable_dates: string[]; // ISO date strings (YYYY-MM-DD)
  total_minutes: number;
  reminder_preference_days: number;
  consent_status: ConsentStatus | null;
  preferred_appointment_type_ids: string[];
  created_at: string;
  updated_at: string;
}

export interface CustomerListResponse extends PaginatedResponse<CustomerResponse> {
  total_unfiltered: number;
}

export interface CustomerWithTenant extends CustomerResponse {
  tenant_id: string;
  tenant_name: string;
}

export interface CustomerCreate {
  phone: string;
  name: string;
  email?: string;
  sex?: ContactSex;
  all_services_enabled?: boolean;
  background_check_required?: boolean;
  availability?: AvailabilitySlot[];
  weekly_hours?: WeeklyHourBlock[];
  unavailable_dates?: string[];
  reminder_preference_days?: number;
  preferred_appointment_type_ids?: string[];
}

export interface CustomerUpdate {
  phone?: string;
  name?: string;
  email?: string;
  sex?: ContactSex | null;
  all_services_enabled?: boolean;
  background_check_required?: boolean;
  availability?: AvailabilitySlot[];
  weekly_hours?: WeeklyHourBlock[];
  unavailable_dates?: string[];
  reminder_preference_days?: number;
  preferred_appointment_type_ids?: string[];
}

export interface CsvImportResponse {
  imported: number;
  updated: number;
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

// ── Volunteer Stats ──

export interface VolunteerServiceStat {
  appointment_type_id: string;
  name: string;
  category: string | null;
  completed_bookings: number;
  total_minutes: number;
}

export interface VolunteerStatsResponse {
  total_completed_bookings: number;
  total_minutes: number;
  by_service: VolunteerServiceStat[];
}

export interface VolunteerHoursSummary {
  total_minutes_all_time: number;
  total_minutes_last_month: number;
}

// ── Appointment Types ──

export interface AppointmentTypeResponse {
  id: string;
  name: string;
  category: string;
  duration_minutes: number;
  price: number;
  description: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface AppointmentTypeCreate {
  name: string;
  category: string;
  duration_minutes: number;
  price: number;
  description?: string;
  is_active?: boolean;
}

export interface AppointmentTypeUpdate {
  name?: string;
  category?: string;
  duration_minutes?: number;
  price?: number;
  description?: string;
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

export interface ServiceSlotConfig {
  appointment_type_id: string;
  min_required: number;
  max_allowed: number;
}

export interface AvailabilityRuleResponse {
  id: string;
  day_of_week: number;
  label: string | null;
  location: string | null;
  start_time: string;
  end_time: string;
  buffer_minutes: number;
  service_config: ServiceSlotConfig[] | null;
  is_active: boolean;
  allow_roster_sharing: boolean;
}

export interface AvailabilityRuleUpdate {
  /** Send the existing rule's id so the server upserts in place
   *  (preserves the FK link from any materialized SpecificDateSlot).
   *  Leave undefined for brand-new rules. */
  id?: string;
  day_of_week: number;
  label?: string;
  location?: string;
  start_time: string;
  end_time: string;
  buffer_minutes?: number;
  service_config?: ServiceSlotConfig[] | null;
  is_active?: boolean;
  allow_roster_sharing?: boolean;
}

export interface RuleDriftEntry {
  field: string;
  from: unknown;
  to: unknown;
}

export interface SpecificDateSlotResponse {
  id: string;
  date: string;
  label: string | null;
  location: string | null;
  start_time: string;
  end_time: string;
  buffer_minutes: number;
  service_config: ServiceSlotConfig[] | null;
  is_active: boolean;
  allow_roster_sharing: boolean;
  description: string | null;
  /** When set, the slot was materialized from this rule. The
   *  propagation engine uses it to fan out rule edits. */
  availability_rule_id?: string | null;
  /** Set when the parent rule changed but this slot couldn't
   *  auto-absorb the diff (bookings or active campaign). Cleared
   *  via apply-rule-drift or ignore-rule-drift. */
  rule_drift_at?: string | null;
  rule_drift_summary?: RuleDriftEntry[] | null;
}

export interface SpecificDateSlotCreate {
  date: string;
  label?: string;
  location?: string;
  start_time: string;
  end_time: string;
  buffer_minutes?: number;
  service_config?: ServiceSlotConfig[] | null;
  is_active?: boolean;
  allow_roster_sharing?: boolean;
  description?: string;
}

export interface SpecificDateSlotUpdate {
  date?: string;
  label?: string;
  location?: string;
  start_time?: string;
  end_time?: string;
  buffer_minutes?: number;
  service_config?: ServiceSlotConfig[] | null;
  is_active?: boolean;
  allow_roster_sharing?: boolean;
  description?: string;
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
  triggering_message: string | null;
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
  phone: string | null;
  tenant_id: string | null;
  is_active: boolean;
  created_at: string;
  last_login_at: string | null;
}

export interface AdminUserCreate {
  email: string;
  password: string;
  role: AdminRole;
  phone?: string | null;
}

export interface AdminUserUpdate {
  role?: AdminRole;
  is_active?: boolean;
  phone?: string | null;
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
  phone: string | null;
  email: string | null;
  address_city: string | null;
  address_state: string | null;
  contact_name: string | null;
  contact_email: string | null;
  is_paused: boolean;
  paused_at: string | null;
  deactivated_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface TenantDetailResponse extends TenantResponse {
  address_street: string | null;
  address_zip: string | null;
  address_country: string | null;
  billing_email: string | null;
  billing_address_street: string | null;
  billing_address_city: string | null;
  billing_address_state: string | null;
  billing_address_zip: string | null;
  billing_address_country: string | null;
  contact_phone: string | null;
  contact_preference: ContactPreference | null;
  has_twilio: boolean;
  has_anthropic: boolean;
  has_google_calendar: boolean;
  has_resend: boolean;
  twilio_account_sid_masked: string | null;
  twilio_auth_token_masked: string | null;
  anthropic_api_key_masked: string | null;
  google_client_id_masked: string | null;
  google_client_secret_masked: string | null;
  google_refresh_token_masked: string | null;
  resend_api_key_masked: string | null;
  resend_from_email: string | null;
}

export interface TenantCreate {
  name: string;
  slug: string;
  business_name: string;
  business_domain?: string;
  business_timezone?: string;
  admin_panel_url?: string;
  api_domain?: string;
  phone?: string;
  email?: string;
  address_street?: string;
  address_city?: string;
  address_state?: string;
  address_zip?: string;
  address_country?: string;
  billing_email?: string;
  billing_address_street?: string;
  billing_address_city?: string;
  billing_address_state?: string;
  billing_address_zip?: string;
  billing_address_country?: string;
  contact_name?: string;
  contact_phone?: string;
  contact_email?: string;
  contact_preference?: ContactPreference;
  twilio_account_sid?: string;
  twilio_auth_token?: string;
  twilio_phone_number?: string;
  anthropic_api_key?: string;
  google_client_id?: string;
  google_client_secret?: string;
  google_refresh_token?: string;
  resend_api_key?: string;
  resend_from_email?: string;
  admin_email?: string;
  admin_password?: string;
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
  phone?: string;
  email?: string;
  address_street?: string;
  address_city?: string;
  address_state?: string;
  address_zip?: string;
  address_country?: string;
  billing_email?: string;
  billing_address_street?: string;
  billing_address_city?: string;
  billing_address_state?: string;
  billing_address_zip?: string;
  billing_address_country?: string;
  contact_name?: string;
  contact_phone?: string;
  contact_email?: string;
  contact_preference?: ContactPreference;
  is_paused?: boolean;
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

export interface TenantSummaryItem {
  id: string;
  name: string;
  slug: string;
  is_active: boolean;
  is_paused: boolean;
  customers: number;
  bookings: number;
  conversations: number;
  reminders: number;
  revenue: number;
}

export interface SuperAdminDashboardSummary {
  total_tenants: number;
  active_tenants: number;
  paused_tenants: number;
  total_customers: number;
  total_bookings: number;
  total_conversations: number;
  total_reminders: number;
  total_revenue: number;
  tenants: TenantSummaryItem[];
}

export interface AdminUserPasswordUpdate {
  password: string;
}

// ── Announcements ──

export interface EventContext {
  event_label?: string | null;
  event_date?: string | null;
  event_start_time?: string | null;
  event_end_time?: string | null;
  event_location?: string | null;
  service_name?: string | null;
  appointment_type_id?: string | null;
}

export type RecipientScope = "all" | "event_signups";

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
  event_context: EventContext | null;
  recipient_scope: RecipientScope;
  created_by_admin_id: string;
  created_at: string;
}

export type AnnouncementListResponse = PaginatedResponse<AnnouncementResponse>;

export interface AnnouncementCreate {
  message: string;
  filter_appointment_type_ids?: string[];
  scheduled_at?: string;
  event_context?: EventContext;
  recipient_scope?: RecipientScope;
}


// ── Recruitment Agent ──

export interface CampaignGoal {
  appointment_type_id: string;
  target: number;
  min_acceptable?: number | null;
}

export interface CampaignCreate {
  event_slot_id: string;
  goals?: CampaignGoal[];
}

export interface CampaignPlanPatch {
  policy?: Record<string, unknown>;
  message_templates?: Record<string, string>;
}

export interface WaveResponse {
  id: string;
  campaign_id: string;
  wave_number: number;
  appointment_type_id: string;
  status: import("./enums").WaveStatus;
  scheduled_at: string;
  targeted_contact_ids: string[] | null;
  selection_reason: string | null;
  announcement_id: string | null;
  sent_count: number;
  signups_attributed: number;
  created_at: string;
}

export interface ReportSummary {
  id: string;
  report_date: string;
  narrative: string | null;
  sent_via: "sms" | "none";
  delivered_at: string | null;
}

export interface CampaignResponse {
  id: string;
  tenant_id: string;
  event_slot_id: string;
  status: import("./enums").CampaignStatus;
  goals: Array<Record<string, unknown>>;
  policy: Record<string, unknown>;
  plan_summary: string | null;
  plan_preview: Record<string, unknown> | null;
  message_templates: Record<string, string> | null;
  created_by_admin_id: string;
  approved_by_admin_id: string | null;
  approved_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface CampaignDetailResponse extends CampaignResponse {
  waves: WaveResponse[];
  recent_reports: ReportSummary[];
  current_signups: Record<string, number>;
}

export interface FillPerService {
  service_name: string | null;
  target: number; // legacy alias for min_required
  min_required: number;
  max_allowed: number | null;
  signups: number;
}

export interface CampaignListItem {
  id: string;
  event_slot_id: string;
  event_label: string | null;
  event_date: string;
  days_to_event: number;
  status: import("./enums").CampaignStatus;
  fill_per_service: Record<string, FillPerService>;
  overall_fill_pct: number;
  last_wave_sent_at: string | null;
  next_wave_due_at: string | null;
  at_risk: boolean;
}

export interface CampaignAggregate {
  active_campaigns: number;
  total_volunteers_needed: number;
  total_signed_up: number;
  total_messaged_7d: number;
  at_risk_count: number;
}

export interface CampaignListResponse {
  items: CampaignListItem[];
  aggregate: CampaignAggregate;
  total: number;
}



// ────────────────────────────────────────────────────────────────────
// Event lifecycle plan — Phase 1 types
// ────────────────────────────────────────────────────────────────────

// Live Events dashboard panel (decision #21)
export interface LiveEventRow {
  slot_id: string;
  event_name: string;
  location: string | null;
  start_time: string;
  end_time: string;
  total_count: number;
  checked_in_count: number;
  missing_count: number;
  first_missing_names: string[];
  pending_switches: number;
  status_dot: "red" | "amber" | "green";
}

// Volunteer candidate (Row 4/5 walk-up capture)
export type CandidateStatus = "new" | "invited" | "dismissed";

export interface VolunteerCandidate {
  id: string;
  phone: string;
  first_seen_at: string;
  last_seen_at: string;
  occurrence_count: number;
  last_signal_slot_id: string | null;
  last_message_body: string | null;
  status: CandidateStatus;
  invited_at: string | null;
  dismissed_at: string | null;
  promoted_contact_id: string | null;
}

// Observability metric (decision #33)
export interface ObservabilityMetric {
  label: string;
  value: number;
  numerator: number;
  denominator: number;
  extra: Record<string, unknown> | null;
}


// Run-sheet (admin live during-event view)
export interface RunSheetVolunteer {
  booking_id: string;
  contact_id: string;
  name: string | null;
  phone: string;
  service_name: string | null;
  checked_in_at: string | null;
  checked_out_at: string | null;
  checked_in_source: string | null;
  late_minutes: number | null;
}

export interface RunSheetResponse {
  slot_id: string;
  event_name: string;
  location: string | null;
  start_time: string;
  end_time: string;
  total_count: number;
  checked_in_count: number;
  volunteers: RunSheetVolunteer[];
}


// Phase 3 — service log + mid-event switch
export interface PendingServiceEntry {
  id: string;
  booking_id: string;
  contact_name: string | null;
  contact_phone: string;
  target_service: string;
  created_at: string;
  version: number;
}

export interface ServiceEntryStatusResponse {
  id: string;
  status: "pending" | "approved" | "rejected" | "superseded";
  version: number;
  approved_at: string | null;
}


// Phase 4 — post-event review + grading
export type ReviewStatus = "pending" | "approved" | "no_show" | "skipped";

export interface ReviewSegment {
  in: string | null;
  out: string | null;
  source_in: string | null;
  source_out: string | null;
}

export interface BookingReviewRow {
  id: string;
  booking_id: string;
  contact_id: string;
  contact_name: string | null;
  status: ReviewStatus;
  grade: number | null;
  grade_notes: string | null;
  total_hours: number | null;
  segments: ReviewSegment[] | null;
  final_check_in_at: string | null;
  final_check_out_at: string | null;
  reviewed_at: string | null;
  unlocked_at: string | null;
  unlock_count: number;
}


// Phase 5 — recognition (milestones, badges, awards)
export type AwardKind = "milestone" | "badge" | "award";
export type AwardScope = "lifetime" | "per_event" | "per_period";
export type PeriodUnit = "month" | "quarter" | "year";

export interface AwardDefinitionRow {
  id: string;
  kind: AwardKind;
  key: string;
  label: string;
  description: string | null;
  icon_key: string | null;
  auto_criteria: Record<string, unknown> | null;
  uniqueness_scope: AwardScope;
  period_unit: PeriodUnit | null;
  is_active: boolean;
  created_at: string;
}

export interface DefinitionCreatePayload {
  kind: AwardKind;
  key: string;
  label: string;
  description?: string | null;
  icon_key?: string | null;
  auto_criteria?: Record<string, unknown> | null;
  uniqueness_scope: AwardScope;
  period_unit?: PeriodUnit | null;
}

export interface DefinitionUpdatePayload {
  label?: string;
  description?: string | null;
  icon_key?: string | null;
  auto_criteria?: Record<string, unknown> | null;
  is_active?: boolean;
}

export interface RecognitionRow {
  id: string;
  definition_id: string;
  definition_label: string;
  definition_kind: AwardKind;
  definition_icon_key: string | null;
  earned_at: string;
  period_key: string | null;
  earned_via_slot_id: string | null;
  granted_by_admin_id: string | null;
  notes: string | null;
}

export interface ManualGrantPayload {
  contact_id: string;
  definition_id: string;
  earned_via_slot_id?: string | null;
  notes?: string | null;
}
