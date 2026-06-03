import { useEffect, useMemo, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { usePrompts, useUpdateSettings } from "../hooks/use-settings";
import { useTenantFilter } from "@/context/tenant-filter-context";

export interface PromptEntry {
  key: string;
  label: string;
  description?: string;
  rows?: number;
  category?: string;
}

// Workflow categories for the AI prompts page. Order here drives the
// order of the category selector. Keep them in lifecycle order so an
// admin can scan top-to-bottom through the volunteer journey.
export const AI_PROMPT_CATEGORIES = [
  "System",
  "Volunteer Chat",
  "Admin Chat",
  "Recruitment Campaigns",
  "Volunteer Info Queries",
  "No Live Event",
  "Check-in / Check-out",
  "Mid-Event Service Change",
  "Walk-ups (Unknown Phone)",
  "Roster Pings & Reviews",
  "Admin SMS Commands",
  "Reserve (Admin Scheduling)",
  "Recognition",
] as const;

const AI_PROMPT_ENTRIES: PromptEntry[] = [
  {
    key: "prompt_customer_system",
    label: "Volunteer SMS Prompt",
    description:
      "System prompt for customer SMS conversations (tool_use mode). Template variables: {business_name}, {custom_instructions}",
    rows: 8,
    category: "Volunteer Chat",
  },
  {
    key: "prompt_admin_system",
    label: "Admin SMS Prompt",
    description:
      "System prompt for admin SMS conversations (tool_use mode). Template variables: {business_name}, {custom_instructions}",
    rows: 8,
    category: "Admin Chat",
  },
  {
    key: "prompt_recruitment_agent",
    label: "Recruitment Agent Prompt (Campaign Planner)",
    description:
      "System prompt for the Volunteer Recruitment Agent's planner. Runs once per campaign to gather facts via tools and propose policy + message templates + wave preview. The agent's final sentence becomes the SMS sent to the admin. No template variables; tool descriptions are passed separately.",
    rows: 12,
    category: "Recruitment Campaigns",
  },
  {
    key: "prompt_recruitment_reporter",
    label: "Recruitment Reporter Prompt (Daily Admin SMS)",
    description:
      "System prompt for the Recruitment Agent's daily progress SMS to the admin. Generates the 2-3 sentence update with fill rate, recent wave activity, and next action — kept under 300 chars to fit one SMS. Edit to change tone, length, what to lead with, or whether to allow emojis. The payload (numbers) is provided to the AI separately; this prompt only controls voice and structure.",
    rows: 8,
    category: "Recruitment Campaigns",
  },
  {
    key: "prompt_recruitment_approval",
    label: "Recruitment Approval Routing",
    description:
      "Routing rule injected into the Admin SMS Prompt that tells the AI how to recognize an admin 'approve' reply (yes / go / lgtm / etc.) and force-call the approve_recruitment_campaign tool. Edit to add/remove trigger words or tighten the wording. Substituted into the admin prompt at the {recruitment_approval} placeholder.",
    rows: 8,
    category: "Recruitment Campaigns",
  },
  {
    key: "prompt_recruitment_start",
    label: "Recruitment Start Routing",
    description:
      "Routing rule injected into the Admin SMS Prompt that recognizes start-planning intent ('plan for X', 'recruit for X', 'fill X', etc.) and force-calls start_recruitment_campaign. Backstopped by a server-side regex router + Haiku classifier (decisions #20 and #22) so this prompt rule is a complementary first line — the system stays reliable even when admins reword the trigger. Substituted into the admin prompt at the {recruitment_start} placeholder.",
    rows: 8,
    category: "Recruitment Campaigns",
  },
  {
    key: "prompt_recruitment_delete",
    label: "Recruitment Delete Routing",
    description:
      "Routing rule injected into the Admin SMS Prompt that recognizes explicit DELETE intent on a recruitment campaign and force-calls delete_recruitment_campaign. Includes a verb-disambiguation rule so 'cancel' / 'pause' / 'remove' do NOT trigger a destructive delete (decision #21). Substituted into the admin prompt at the {recruitment_delete} placeholder.",
    rows: 8,
    category: "Recruitment Campaigns",
  },
  {
    key: "prompt_customer_service_presentation",
    label: "Service Presentation (Volunteer SMS)",
    description:
      "Tells the volunteer assistant how to present services from list_services — include the next upcoming event (date, time, location) alongside each service so volunteers don't have to ask a follow-up question. Substituted into the Volunteer SMS Prompt at the {service_presentation} placeholder. Edit to adjust how aggressively to surface event details or what to say when a service has no upcoming opportunities.",
    rows: 6,
    category: "Volunteer Chat",
  },
  {
    key: "prompt_customer_roster_saved",
    label: "Roster Visibility — Saved Default (Volunteer SMS)",
    description:
      "Injected into the volunteer's per-turn context when they HAVE already chosen a roster-visibility preference on a prior booking. Tells the AI to OMIT share_on_roster on book_appointment (the saved value is used automatically) and not to re-ask. Placeholder {saved_display} is filled at runtime with the volunteer's saved choice (e.g. 'full name (Barbara Nguyen)').",
    rows: 8,
    category: "Volunteer Chat",
  },
  {
    key: "prompt_customer_roster_unset",
    label: "Roster Visibility — Ask First Time (Volunteer SMS)",
    description:
      "Injected when a volunteer has NO saved roster-visibility default — drives the one-time ask and contains the 'INTERPRETING THE ANSWER' rule that prevents the AI from re-asking 'I see you mentioned full name — were you answering my earlier question?'. Placeholders {first_name_choice} and {full_name_choice} are filled at runtime with the volunteer's actual name in parens.",
    rows: 10,
    category: "Volunteer Chat",
  },
  {
    key: "prompt_customer_booking_roster_hint",
    label: "Booking Confirmation Roster Hint (Volunteer SMS)",
    description:
      "Short hint appended to every booking confirmation telling the volunteer how they appear on the roster and how to change it. Placeholder {roster_display} is filled at runtime with the actual saved choice (e.g. 'first name only (Barbara)'). Edit the wording or trigger phrases for changing the preference.",
    rows: 4,
    category: "Volunteer Chat",
  },
  {
    key: "prompt_screener_system",
    label: "Message Screener Prompt",
    description:
      "Classifies inbound messages as RELEVANT, IRRELEVANT, or ABUSIVE before reaching the chatbot.",
    rows: 8,
    category: "System",
  },
  {
    key: "prompt_fallback_message",
    label: "Fallback Message",
    description: "Sent to customers when the AI cannot understand their message.",
    rows: 4,
    category: "System",
  },
  {
    key: "prompt_error_message",
    label: "Error Message",
    description: "Sent to customers when a technical error occurs.",
    rows: 4,
    category: "System",
  },

  // ── Event Lifecycle — Check-in (5) ──
  {
    key: "prompt_checkin_confirmation",
    label: "Check-in — Confirmation (Volunteer)",
    description:
      "Reply when a volunteer successfully checks in via HERE. Variables: {first_name}, {event_label}, {service_name}, {event_location}, {event_time}.",
    rows: 4,
    category: "Check-in / Check-out",
  },
  {
    key: "prompt_checkin_already_in",
    label: "Check-in — Already Checked In (Volunteer)",
    description:
      "Idempotent ack when a checked-in volunteer texts HERE again. Variables: {first_name}, {event_label}.",
    rows: 4,
    category: "Check-in / Check-out",
  },
  {
    key: "prompt_checkin_disambiguation",
    label: "Check-in — Multi-Event Picker (Volunteer)",
    description:
      "Sent when a volunteer with multiple live bookings texts HERE. Asks which event. Variables: {options_list}.",
    rows: 4,
    category: "Check-in / Check-out",
  },
  {
    key: "prompt_checkin_reentry_prompt",
    label: "Check-in — Re-entry Ask (Volunteer)",
    description:
      "Sent when a volunteer who already checked out texts HERE again — asks them to confirm they're returning (reply HERE-AGAIN or BACK). Variables: {first_name}, {event_label}.",
    rows: 4,
    category: "Check-in / Check-out",
  },
  {
    key: "prompt_checkin_reentry_confirmation",
    label: "Check-in — Re-entry Confirmed (Volunteer)",
    description:
      "Reply after a volunteer confirms re-entry with HERE-AGAIN/BACK. Variables: {first_name}, {event_label}.",
    rows: 4,
    category: "Check-in / Check-out",
  },

  // ── Event Lifecycle — Check-out (1) ──
  {
    key: "prompt_checkout_confirmation",
    label: "Check-out — Confirmation (Volunteer)",
    description:
      "Thank-you reply when a volunteer texts DONE. Variables: {first_name}, {event_label}.",
    rows: 4,
    category: "Check-in / Check-out",
  },

  // ── Event Lifecycle — Mid-event Service Change (5) ──
  {
    key: "prompt_service_switch_pending",
    label: "Service Switch — Pending Approval (Volunteer)",
    description:
      "Sent after a volunteer texts SWITCH <service>; tells them admin will confirm. Variables: {service_name}.",
    rows: 4,
    category: "Mid-Event Service Change",
  },
  {
    key: "prompt_service_add_pending",
    label: "Service Add — Pending Approval (Volunteer)",
    description:
      "Sent after a volunteer texts ALSO <service> to add a parallel service. Variables: {service_name}.",
    rows: 4,
    category: "Mid-Event Service Change",
  },
  {
    key: "prompt_service_unrecognized",
    label: "Service — Not Recognized (Volunteer)",
    description:
      "Fallback when SWITCH/ALSO names a service that doesn't exist or isn't on this event. Variables: {requested_service}, {available_services}.",
    rows: 4,
    category: "Mid-Event Service Change",
  },
  {
    key: "prompt_admin_service_approval_request",
    label: "Service Change — Admin Approval Request (Admin SMS)",
    description:
      "Admin alert when a volunteer requests SWITCH/ALSO. Variables: {first_name}, {from_service}, {to_service}, {event_label}, {request_id}.",
    rows: 4,
    category: "Mid-Event Service Change",
  },
  {
    key: "prompt_admin_service_approval_done",
    label: "Service Change — Volunteer Notified of Decision",
    description:
      "Sent to the volunteer after admin decides their SWITCH/ALSO. Variables: {first_name}, {service_name}, {decision} (approved/rejected).",
    rows: 4,
    category: "Mid-Event Service Change",
  },

  // ── Event Lifecycle — Walk-up / Unknown Phone (4) ──
  {
    key: "prompt_walkup_offer",
    label: "Walk-up — Open Slot Offer (Volunteer)",
    description:
      "Offer sent to a signed-up volunteer texting HERE for an event they're not on, when an open slot exists. Variables: {first_name}, {event_label}, {service_name}, {event_time}.",
    rows: 4,
    category: "Walk-ups (Unknown Phone)",
  },
  {
    key: "prompt_walkup_picker",
    label: "Walk-up — Multi-Slot Picker (Volunteer)",
    description:
      "Sent when more than one walk-up option is available. Variables: {options_list}.",
    rows: 4,
    category: "Walk-ups (Unknown Phone)",
  },
  {
    key: "prompt_walkup_confirmation",
    label: "Walk-up — Confirmed (Volunteer)",
    description:
      "Reply after admin promotes a walk-up candidate. Variables: {first_name}, {event_label}, {service_name}.",
    rows: 4,
    category: "Walk-ups (Unknown Phone)",
  },
  {
    key: "prompt_admin_walkup_candidate_notification",
    label: "Walk-up — Admin Notification (Admin SMS)",
    description:
      "Admin alert when an unknown phone texts HERE. Variables: {phone}, {inbound_message}, {admin_panel_url}.",
    rows: 4,
    category: "Walk-ups (Unknown Phone)",
  },

  // ── Event Lifecycle — No Live Event (3) ──
  {
    key: "prompt_no_event_future_booking",
    label: "No Live Event — Future Booking (Volunteer)",
    description:
      "Sent when a volunteer texts HERE and has no live event but has a future booking. Variables: {first_name}, {event_label}, {event_date}, {event_time}.",
    rows: 4,
    category: "No Live Event",
  },
  {
    key: "prompt_no_event_no_future_booking",
    label: "No Live Event — No Future Booking (Volunteer)",
    description:
      "Sent when a volunteer texts HERE and has nothing on the calendar. Variables: {first_name}.",
    rows: 4,
    category: "No Live Event",
  },
  {
    key: "prompt_no_event_cancelled",
    label: "No Live Event — Was Cancelled (Volunteer)",
    description:
      "Sent when the event the volunteer is asking about has been cancelled. Variables: {first_name}, {event_label}.",
    rows: 4,
    category: "No Live Event",
  },

  // ── Event Lifecycle — Roster Pings + Review (3) ──
  {
    key: "prompt_roster_status_ping",
    label: "Roster Ping — Auto Status Update (Admin SMS)",
    description:
      "Body of the auto-pings sent T-30 → T+60. Variables: {event_label}, {phase} (e.g. T-15), {checked_in_count}, {expected_count}, {late_list}, {no_show_list}.",
    rows: 6,
    category: "Roster Pings & Reviews",
  },
  {
    key: "prompt_roster_status_all_in",
    label: "Roster Ping — Everyone Checked In (Admin SMS)",
    description:
      "Sent in place of a normal ping when all booked volunteers are already checked in (suppression variant). Variables: {event_label}, {checked_in_count}.",
    rows: 4,
    category: "Roster Pings & Reviews",
  },
  {
    key: "prompt_post_event_review_available",
    label: "Post-Event — Review Ready (Admin SMS)",
    description:
      "Admin nudge when post-event reviews are pending. Variables: {event_label}, {pending_count}, {admin_panel_url}.",
    rows: 4,
    category: "Roster Pings & Reviews",
  },

  // ── Event Lifecycle — Admin SMS Commands (8) ──
  {
    key: "prompt_admin_checkin_success",
    label: "Admin Command — Check-in Done (Admin SMS)",
    description:
      "Reply after admin texts CHECKIN <name> successfully. Variables: {volunteer_name}, {event_label}.",
    rows: 4,
    category: "Admin SMS Commands",
  },
  {
    key: "prompt_admin_checkout_success",
    label: "Admin Command — Check-out Done (Admin SMS)",
    description:
      "Reply after admin texts CHECKOUT <name> successfully. Variables: {volunteer_name}, {event_label}.",
    rows: 4,
    category: "Admin SMS Commands",
  },
  {
    key: "prompt_admin_command_name_not_found",
    label: "Admin Command — Volunteer Not Found (Admin SMS)",
    description:
      "Reply when a CHECKIN/CHECKOUT/APPROVE etc. references a name that doesn't match any volunteer on the live roster. Variables: {requested_name}.",
    rows: 4,
    category: "Admin SMS Commands",
  },
  {
    key: "prompt_admin_command_disambiguation",
    label: "Admin Command — Multiple Name Matches (Admin SMS)",
    description:
      "Picker when a name partially matches several volunteers. Variables: {requested_name}, {candidates_list}.",
    rows: 4,
    category: "Admin SMS Commands",
  },
  {
    key: "prompt_admin_command_usage_help",
    label: "Admin Command — Usage Help (Admin SMS)",
    description:
      "Syntax help shown when an admin command can't be parsed (e.g. CHECKIN with no name and no linked self). No variables.",
    rows: 6,
    category: "Admin SMS Commands",
  },
  {
    key: "prompt_admin_super_admin_rejection",
    label: "Admin — Super-Admin Texting Tenant (Admin SMS)",
    description:
      "Reply when a SUPER_ADMIN texts any tenant Twilio number — bounces them to the admin panel. Variables: {admin_panel_url}.",
    rows: 4,
    category: "Admin SMS Commands",
  },
  {
    key: "prompt_admin_live_events_context_block",
    label: "Admin Context — Live Events Block (System Prompt)",
    description:
      "Cached system-prompt block injected into the admin LLM turn. Lists currently live events with counts. Variables: {events_list}. Edit to control how much detail the LLM sees.",
    rows: 8,
    category: "Admin SMS Commands",
  },
  {
    key: "prompt_admin_personal_bookings_context_block",
    label: "Admin Context — Personal Bookings Block (System Prompt)",
    description:
      "Cached system-prompt block listing the admin's own bookings so SMS like 'STATUS' default to event-status (not self). Variables: {bookings_list}.",
    rows: 6,
    category: "Admin SMS Commands",
  },

  // ── Event Lifecycle — RESERVE (Admin Scheduling SMS) (5) ──
  {
    key: "prompt_admin_reserve_event_picker",
    label: "Reserve — Event Picker (Admin SMS)",
    description:
      "First-stage RESERVE picker — lists upcoming events the admin can reserve a volunteer for. Variables: {events_list}.",
    rows: 4,
    category: "Reserve (Admin Scheduling)",
  },
  {
    key: "prompt_admin_reserve_service_picker",
    label: "Reserve — Service Picker (Admin SMS)",
    description:
      "Second-stage picker after admin chose an event. Variables: {event_label}, {services_list}.",
    rows: 4,
    category: "Reserve (Admin Scheduling)",
  },
  {
    key: "prompt_admin_reserve_confirmation",
    label: "Reserve — Success (Admin SMS)",
    description:
      "Confirmation after admin successfully reserves a volunteer for a service. Variables: {volunteer_name}, {event_label}, {service_name}, {event_time}.",
    rows: 4,
    category: "Reserve (Admin Scheduling)",
  },
  {
    key: "prompt_admin_reserve_no_capacity",
    label: "Reserve — Service Full (Admin SMS)",
    description:
      "Sent when admin tries to RESERVE for a service with zero open slots. Variables: {service_name}, {event_label}.",
    rows: 4,
    category: "Reserve (Admin Scheduling)",
  },
  {
    key: "prompt_admin_reserve_slot_filled",
    label: "Reserve — Slot Filled Mid-Flow (Admin SMS)",
    description:
      "Race-condition message when the chosen slot filled between picker and confirm (decision §12.4). Variables: {service_name}, {event_label}.",
    rows: 4,
    category: "Reserve (Admin Scheduling)",
  },

  // ── Event Lifecycle — Volunteer Info Queries (2) ──
  {
    key: "prompt_list_events_response",
    label: "List Upcoming Events (Volunteer)",
    description:
      "Reply when a volunteer asks 'what events are coming up?'. Variables: {first_name}, {events_list}.",
    rows: 4,
    category: "Volunteer Info Queries",
  },
  {
    key: "prompt_list_bookings_response",
    label: "List My Bookings (Volunteer)",
    description:
      "Reply when a volunteer asks 'what am I signed up for?'. Variables: {first_name}, {bookings_list}.",
    rows: 4,
    category: "Volunteer Info Queries",
  },

  // ── Event Lifecycle — Recognition (1) ──
  {
    key: "prompt_recognition_congratulations",
    label: "Recognition — Congrats SMS (Volunteer)",
    description:
      "Opt-in congratulatory SMS sent when a volunteer earns a milestone/badge/award. Only fires if `recognition_congrats_enabled` is on. Variables: {first_name}, {recognition_label}.",
    rows: 4,
    category: "Recognition",
  },
];

const TEMPLATE_ENTRIES: PromptEntry[] = [
  {
    key: "prompt_announcement_header",
    label: "Announcement Header (event-tied)",
    description:
      "Prepended to every announcement that is tied to a specific event. Variables: {event_label}, {event_date}, {event_start_time}, {event_end_time}, {event_location}, {service_name}, {event_location_part} (a pre-formatted ' · {location}' or empty). Missing variables render as empty strings.",
    rows: 4,
    category: "Templates",
  },
  {
    key: "prompt_reminder_format",
    label: "Reminder Format (sign-up)",
    description:
      "Sent to volunteers who have NOT yet signed up when an admin clicks 'Send reminder' on an event. Variables: {service_name}, {date}. Missing variables render as empty strings.",
    rows: 4,
    category: "Templates",
  },
  {
    key: "prompt_recruitment_message",
    label: "Recruitment Agent Message",
    description:
      "Default SMS the Recruitment Agent sends to volunteers when a campaign's per-wave message_templates don't override it. Variables: {first_name}, {name_part} (' Alice' or empty), {event_label}, {event_date}, {event_start_time}, {event_end_time}, {hours} (computed duration, e.g. '2' or '1.5'), {event_location}, {service_name}. Keep under ~160 characters where possible.",
    rows: 4,
    category: "Templates",
  },
];

interface PromptEditorProps {
  entries?: PromptEntry[];
  title?: string;
  emptyMessage?: string;
}

export function PromptEditor({
  entries = AI_PROMPT_ENTRIES,
  title = "AI Prompts",
  emptyMessage = "Select a tenant from the filter above to view and edit AI prompts.",
}: PromptEditorProps) {
  const { selectedTenantIds, isSuperAdmin } = useTenantFilter();
  const hasTenant = !isSuperAdmin || selectedTenantIds.length === 1;
  const { data: prompts, isLoading } = usePrompts();
  const update = useUpdateSettings();

  const [values, setValues] = useState<Record<string, string>>({});
  const [defaults, setDefaults] = useState<Record<string, string>>({});
  const [savedOverrides, setSavedOverrides] = useState<Record<string, boolean>>({});
  const [selectedKey, setSelectedKey] = useState<string>(entries[0]?.key ?? "");
  const [savedSnapshot, setSavedSnapshot] = useState<Record<string, string>>({});

  // Available categories on the current entries list, in canonical workflow
  // order. We only surface the category selector when there are 3+ distinct
  // categories (Templates page has 1 — no value in showing the selector).
  const categories = useMemo(() => {
    const present = new Set<string>();
    for (const e of entries) {
      if (e.category) present.add(e.category);
    }
    const ordered = AI_PROMPT_CATEGORIES.filter((c) => present.has(c));
    const extras = [...present].filter(
      (c) => !AI_PROMPT_CATEGORIES.includes(c as (typeof AI_PROMPT_CATEGORIES)[number])
    );
    return [...ordered, ...extras];
  }, [entries]);

  const showCategoryFilter = categories.length >= 3;
  const [selectedCategory, setSelectedCategory] = useState<string>("__ALL__");

  useEffect(() => {
    if (prompts) {
      const valMap: Record<string, string> = {};
      const defMap: Record<string, string> = {};
      const overrideMap: Record<string, boolean> = {};
      for (const p of prompts) {
        valMap[p.key] = p.value;
        defMap[p.key] = p.default_value ?? p.value;
        overrideMap[p.key] = !p.is_default;
      }
      setValues(valMap);
      setDefaults(defMap);
      setSavedOverrides(overrideMap);
      setSavedSnapshot(valMap);
    } else {
      setValues({});
      setDefaults({});
      setSavedOverrides({});
      setSavedSnapshot({});
    }
  }, [prompts]);

  // Entries narrowed by the active category filter.
  const visibleEntries = useMemo(() => {
    if (selectedCategory === "__ALL__") return entries;
    return entries.filter((e) => e.category === selectedCategory);
  }, [entries, selectedCategory]);

  // If the entries list ever changes (e.g., switching between AI / Templates
  // tabs, or picking a category), reset the selected key to the first
  // visible one when the current selection isn't in view.
  useEffect(() => {
    if (
      visibleEntries.length > 0 &&
      !visibleEntries.some((e) => e.key === selectedKey)
    ) {
      setSelectedKey(visibleEntries[0].key);
    }
  }, [visibleEntries, selectedKey]);

  const selectedEntry = useMemo(
    () =>
      visibleEntries.find((e) => e.key === selectedKey) ??
      entries.find((e) => e.key === selectedKey) ??
      visibleEntries[0] ??
      entries[0],
    [entries, visibleEntries, selectedKey]
  );

  // Per-key dirty tracking so the dropdown can flag unsaved edits when the
  // user switches between prompts without saving first.
  const dirtyKeys = useMemo(() => {
    const out = new Set<string>();
    for (const e of entries) {
      const current = values[e.key];
      const saved = savedSnapshot[e.key];
      if (current !== undefined && saved !== undefined && current !== saved) {
        out.add(e.key);
      }
    }
    return out;
  }, [entries, values, savedSnapshot]);

  function handleSaveSelected() {
    if (!selectedEntry) return;
    const subset: Record<string, string> = {
      [selectedEntry.key]: values[selectedEntry.key] ?? "",
    };
    update.mutate({ settings: subset });
  }

  function handleSaveAll() {
    const subset: Record<string, string> = {};
    for (const e of entries) {
      if (dirtyKeys.has(e.key)) subset[e.key] = values[e.key] ?? "";
    }
    if (Object.keys(subset).length === 0) return;
    update.mutate({ settings: subset });
  }

  function handleReset(key: string) {
    const def = defaults[key];
    if (def !== undefined) {
      setValues((prev) => ({ ...prev, [key]: def }));
    }
  }

  if (!hasTenant) {
    return (
      <Card>
        <CardContent className="py-8 text-center text-sm text-muted-foreground">
          {emptyMessage}
        </CardContent>
      </Card>
    );
  }

  if (isLoading) {
    return (
      <Card>
        <CardContent className="py-8 text-center text-sm text-muted-foreground">
          Loading...
        </CardContent>
      </Card>
    );
  }

  if (!selectedEntry) {
    return null;
  }

  const current = values[selectedEntry.key] ?? "";
  const def = defaults[selectedEntry.key] ?? "";
  const isOverride = !!savedOverrides[selectedEntry.key];
  const canReset = current !== def;
  const isDirty = dirtyKeys.has(selectedEntry.key);
  const dirtyCount = dirtyKeys.size;

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 gap-3">
        <CardTitle className="text-base">{title}</CardTitle>
        <div className="flex items-center gap-2">
          {dirtyCount > 1 && (
            <Button
              variant="outline"
              size="sm"
              onClick={handleSaveAll}
              disabled={update.isPending}
              title={`Save all ${dirtyCount} unsaved prompts`}
            >
              Save All ({dirtyCount})
            </Button>
          )}
          <Button
            size="sm"
            onClick={handleSaveSelected}
            disabled={update.isPending || !isDirty}
          >
            {update.isPending ? "Saving…" : "Save"}
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {showCategoryFilter && (
          <div className="space-y-2">
            <Label className="text-sm font-medium">Category</Label>
            <Select
              value={selectedCategory}
              onValueChange={setSelectedCategory}
            >
              <SelectTrigger className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="__ALL__">
                  All categories ({entries.length})
                </SelectItem>
                {categories.map((c) => {
                  const count = entries.filter((e) => e.category === c).length;
                  const dirtyInCat = entries.filter(
                    (e) => e.category === c && dirtyKeys.has(e.key)
                  ).length;
                  return (
                    <SelectItem key={c} value={c}>
                      {c} ({count})
                      {dirtyInCat > 0 && ` · ${dirtyInCat} unsaved`}
                    </SelectItem>
                  );
                })}
              </SelectContent>
            </Select>
          </div>
        )}
        <div className="space-y-2">
          <Label className="text-sm font-medium">Prompt</Label>
          <Select value={selectedEntry.key} onValueChange={setSelectedKey}>
            <SelectTrigger className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {visibleEntries.map((e) => {
                const overridden = !!savedOverrides[e.key];
                const dirty = dirtyKeys.has(e.key);
                const suffix =
                  dirty && overridden
                    ? " · unsaved, customized"
                    : dirty
                      ? " · unsaved"
                      : overridden
                        ? " · customized"
                        : "";
                return (
                  <SelectItem key={e.key} value={e.key}>
                    {e.label}
                    {suffix}
                  </SelectItem>
                );
              })}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-2">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <Label className="text-sm font-medium">
                {selectedEntry.label}
              </Label>
              {isOverride && (
                <Badge variant="secondary" className="text-[10px]">
                  Customized
                </Badge>
              )}
              {isDirty && (
                <Badge
                  variant="outline"
                  className="text-[10px] border-amber-500 text-amber-700 dark:text-amber-400"
                >
                  Unsaved
                </Badge>
              )}
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => handleReset(selectedEntry.key)}
              disabled={!canReset}
              title={
                canReset
                  ? "Replace with the latest shipped default"
                  : "Already matches the latest default"
              }
            >
              Reset to Default
            </Button>
          </div>
          {selectedEntry.description && (
            <p className="text-xs text-muted-foreground">
              {selectedEntry.description}
            </p>
          )}
          <Textarea
            className="min-h-[160px] font-mono text-sm"
            value={current}
            onChange={(e) =>
              setValues((prev) => ({
                ...prev,
                [selectedEntry.key]: e.target.value,
              }))
            }
            rows={selectedEntry.rows ?? 8}
          />
        </div>
      </CardContent>
    </Card>
  );
}

export { AI_PROMPT_ENTRIES, TEMPLATE_ENTRIES };
