import api from "@/lib/api";
import type {
  DashboardSummary,
  TodaysBooking,
  WeeklySlotStatus,
  NotificationResponse,
} from "@/types/api";

export async function getDashboardSummary(): Promise<DashboardSummary> {
  const { data } = await api.get<DashboardSummary>("/dashboard/summary");
  return data;
}

export async function getTodaysBookings(): Promise<TodaysBooking[]> {
  const { data } = await api.get<TodaysBooking[]>("/dashboard/todays-bookings");
  return data;
}

export async function getWeeklySlotStatuses(offset: number = 0): Promise<WeeklySlotStatus[]> {
  const { data } = await api.get<WeeklySlotStatus[]>("/dashboard/weekly-slots", {
    params: { offset },
  });
  return data;
}

export async function sendSlotReminder(
  date: string,
  appointmentTypeId: string,
): Promise<{ sent_signup: number; sent_confirmation: number; total_volunteers: number }> {
  const { data } = await api.post("/dashboard/send-reminder", {
    date,
    appointment_type_id: appointmentTypeId,
  });
  return data;
}

export async function getNotifications(): Promise<NotificationResponse[]> {
  const { data } = await api.get<NotificationResponse[]>(
    "/dashboard/notifications"
  );
  return data;
}

export async function markNotificationRead(id: string): Promise<void> {
  await api.put(`/dashboard/notifications/${id}/read`);
}

import type { LiveEventRow } from "@/types/api";

export async function getLiveEvents(): Promise<LiveEventRow[]> {
  const { data } = await api.get<LiveEventRow[]>("/dashboard/live-events");
  return data;
}

// Unified Needs-You-Now feed. Aggregated server-side from pending
// SWITCH/ALSO, post-event reviews, suspensions, walk-up candidates,
// at-risk events, and (Phase 1) seeded dummy issue reports.
export interface AlertItem {
  id: string;
  source: string;
  severity: "high" | "medium" | "low";
  title: string;
  body: string | null;
  cta_label: string;
  cta_url: string;
  age_seconds: number;
  icon: string;
  accent:
    | "amber"
    | "red"
    | "blue"
    | "violet"
    | "rose"
    | "slate";
  context: Record<string, unknown> | null;
}

export async function getAlerts(): Promise<AlertItem[]> {
  const { data } = await api.get<AlertItem[]>("/dashboard/alerts");
  return data;
}

// ── Alert state (server-side snooze + dismiss) ──

export interface AlertStateRecord {
  alert_id: string;
  state: "snoozed" | "dismissed";
  snoozed_until: string | null;
  dismiss_reason: string | null;
  created_at: string;
  created_by_admin_id: string;
}

export async function listAlertState(): Promise<AlertStateRecord[]> {
  const { data } = await api.get<AlertStateRecord[]>("/dashboard/alert-state");
  return data;
}

export async function snoozeAlert(
  alertId: string,
  hours: number,
): Promise<AlertStateRecord> {
  const { data } = await api.post<AlertStateRecord>("/dashboard/alert-state", {
    alert_id: alertId,
    state: "snoozed",
    snooze_hours: hours,
  });
  return data;
}

export async function dismissAlert(
  alertId: string,
  reason: string,
): Promise<AlertStateRecord> {
  const { data } = await api.post<AlertStateRecord>("/dashboard/alert-state", {
    alert_id: alertId,
    state: "dismissed",
    dismiss_reason: reason,
  });
  return data;
}

export async function clearAlertState(alertId: string): Promise<void> {
  await api.delete(`/dashboard/alert-state/${encodeURIComponent(alertId)}`);
}

// ── Planning view ──

export interface PlanningCampaignSummary {
  id: string;
  status: string;
  waves_total: number;
  waves_completed: number;
}

export interface PlanningEvent {
  slot_id: string;
  /** 'specific' = backed by a SpecificDateSlot row (campaigns + Start Campaign allowed).
   *  'recurring' = generated from an AvailabilityRule; clicking Start Campaign
   *  on this row materializes a SpecificDateSlot server-side before the
   *  recruiter agent runs. */
  kind: "specific" | "recurring";
  /** Set when kind='recurring'. Frontend sends {rule_id, date} to
   *  /start-campaign so the server materializes a real slot before
   *  invoking the recruiter. */
  rule_id: string | null;
  label: string;
  location: string | null;
  date: string;            // ISO date
  days_until: number;
  bucket: "this_week" | "week_2" | "weeks_3_4" | "month_2";
  booked: number;
  capacity: number;
  min_required_total: number;
  fill_pct: number;
  campaign: PlanningCampaignSummary | null;
  health: "filled" | "filling" | "needs_campaign" | "not_started";
  time_range: string | null;
}

export async function getPlanning(
  startOffset: number = 8,
  endOffset: number = 60,
): Promise<PlanningEvent[]> {
  const { data } = await api.get<PlanningEvent[]>("/dashboard/planning", {
    params: { start_offset: startOffset, end_offset: endOffset },
  });
  return data;
}

// ── Recommendations ──

export interface Recommendation {
  id: string;
  kind: "start_campaign" | "push_wave" | "over_recruit" | "stagger";
  title: string;
  body: string;
  cta_label: string;
  cta_url: string;
  accent: "amber" | "red" | "blue" | "violet" | "rose" | "slate";
  context: Record<string, unknown> | null;
}

export async function getRecommendations(): Promise<Recommendation[]> {
  const { data } = await api.get<Recommendation[]>(
    "/dashboard/recommendations",
  );
  return data;
}

// ── Start Campaign (event card → recruiter agent) ──

export interface StartCampaignResponse {
  ok: boolean;
  agent_reply: string | null;
  synthetic_message: string;
  fell_through_to_llm: boolean;
  /** When the request used (rule_id + date), this is the new
   *  SpecificDateSlot id created server-side. Null for direct slot_id
   *  calls. */
  materialized_slot_id: string | null;
}

/** Specific event: pass `{ slotId }`.
 *  Recurring event: pass `{ ruleId, date }` and the server will
 *  materialize a real slot first. */
export type StartCampaignArgs =
  | { slotId: string }
  | { ruleId: string; date: string };

export async function startCampaignForEvent(
  args: StartCampaignArgs,
): Promise<StartCampaignResponse> {
  const body =
    "slotId" in args
      ? { slot_id: args.slotId }
      : { rule_id: args.ruleId, date: args.date };
  const { data } = await api.post<StartCampaignResponse>(
    "/dashboard/start-campaign",
    body,
  );
  return data;
}
