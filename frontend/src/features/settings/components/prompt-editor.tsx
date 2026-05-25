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
}

const AI_PROMPT_ENTRIES: PromptEntry[] = [
  {
    key: "prompt_customer_system",
    label: "Volunteer SMS Prompt",
    description:
      "System prompt for customer SMS conversations (tool_use mode). Template variables: {business_name}, {custom_instructions}",
    rows: 8,
  },
  {
    key: "prompt_admin_system",
    label: "Admin SMS Prompt",
    description:
      "System prompt for admin SMS conversations (tool_use mode). Template variables: {business_name}, {custom_instructions}",
    rows: 8,
  },
  {
    key: "prompt_recruitment_agent",
    label: "Recruitment Agent Prompt (Campaign Planner)",
    description:
      "System prompt for the Volunteer Recruitment Agent's planner. Runs once per campaign to gather facts via tools and propose policy + message templates + wave preview. The agent's final sentence becomes the SMS sent to the admin. No template variables; tool descriptions are passed separately.",
    rows: 12,
  },
  {
    key: "prompt_recruitment_reporter",
    label: "Recruitment Reporter Prompt (Daily Admin SMS)",
    description:
      "System prompt for the Recruitment Agent's daily progress SMS to the admin. Generates the 2-3 sentence update with fill rate, recent wave activity, and next action — kept under 300 chars to fit one SMS. Edit to change tone, length, what to lead with, or whether to allow emojis. The payload (numbers) is provided to the AI separately; this prompt only controls voice and structure.",
    rows: 8,
  },
  {
    key: "prompt_recruitment_approval",
    label: "Recruitment Approval Routing",
    description:
      "Routing rule injected into the Admin SMS Prompt that tells the AI how to recognize an admin 'approve' reply (yes / go / lgtm / etc.) and force-call the approve_recruitment_campaign tool. Edit to add/remove trigger words or tighten the wording. Substituted into the admin prompt at the {recruitment_approval} placeholder.",
    rows: 8,
  },
  {
    key: "prompt_recruitment_start",
    label: "Recruitment Start Routing",
    description:
      "Routing rule injected into the Admin SMS Prompt that recognizes start-planning intent ('plan for X', 'recruit for X', 'fill X', etc.) and force-calls start_recruitment_campaign. Backstopped by a server-side regex router + Haiku classifier (decisions #20 and #22) so this prompt rule is a complementary first line — the system stays reliable even when admins reword the trigger. Substituted into the admin prompt at the {recruitment_start} placeholder.",
    rows: 8,
  },
  {
    key: "prompt_recruitment_delete",
    label: "Recruitment Delete Routing",
    description:
      "Routing rule injected into the Admin SMS Prompt that recognizes explicit DELETE intent on a recruitment campaign and force-calls delete_recruitment_campaign. Includes a verb-disambiguation rule so 'cancel' / 'pause' / 'remove' do NOT trigger a destructive delete (decision #21). Substituted into the admin prompt at the {recruitment_delete} placeholder.",
    rows: 8,
  },
  {
    key: "prompt_customer_service_presentation",
    label: "Service Presentation (Volunteer SMS)",
    description:
      "Tells the volunteer assistant how to present services from list_services — include the next upcoming event (date, time, location) alongside each service so volunteers don't have to ask a follow-up question. Substituted into the Volunteer SMS Prompt at the {service_presentation} placeholder. Edit to adjust how aggressively to surface event details or what to say when a service has no upcoming opportunities.",
    rows: 6,
  },
  {
    key: "prompt_customer_roster_saved",
    label: "Roster Visibility — Saved Default (Volunteer SMS)",
    description:
      "Injected into the volunteer's per-turn context when they HAVE already chosen a roster-visibility preference on a prior booking. Tells the AI to OMIT share_on_roster on book_appointment (the saved value is used automatically) and not to re-ask. Placeholder {saved_display} is filled at runtime with the volunteer's saved choice (e.g. 'full name (Barbara Nguyen)').",
    rows: 8,
  },
  {
    key: "prompt_customer_roster_unset",
    label: "Roster Visibility — Ask First Time (Volunteer SMS)",
    description:
      "Injected when a volunteer has NO saved roster-visibility default — drives the one-time ask and contains the 'INTERPRETING THE ANSWER' rule that prevents the AI from re-asking 'I see you mentioned full name — were you answering my earlier question?'. Placeholders {first_name_choice} and {full_name_choice} are filled at runtime with the volunteer's actual name in parens.",
    rows: 10,
  },
  {
    key: "prompt_customer_booking_roster_hint",
    label: "Booking Confirmation Roster Hint (Volunteer SMS)",
    description:
      "Short hint appended to every booking confirmation telling the volunteer how they appear on the roster and how to change it. Placeholder {roster_display} is filled at runtime with the actual saved choice (e.g. 'first name only (Barbara)'). Edit the wording or trigger phrases for changing the preference.",
    rows: 4,
  },
  {
    key: "prompt_screener_system",
    label: "Message Screener Prompt",
    description:
      "Classifies inbound messages as RELEVANT, IRRELEVANT, or ABUSIVE before reaching the chatbot.",
    rows: 8,
  },
  {
    key: "prompt_fallback_message",
    label: "Fallback Message",
    description: "Sent to customers when the AI cannot understand their message.",
    rows: 4,
  },
  {
    key: "prompt_error_message",
    label: "Error Message",
    description: "Sent to customers when a technical error occurs.",
    rows: 4,
  },
];

const TEMPLATE_ENTRIES: PromptEntry[] = [
  {
    key: "prompt_announcement_header",
    label: "Announcement Header (event-tied)",
    description:
      "Prepended to every announcement that is tied to a specific event. Variables: {event_label}, {event_date}, {event_start_time}, {event_end_time}, {event_location}, {service_name}, {event_location_part} (a pre-formatted ' · {location}' or empty). Missing variables render as empty strings.",
    rows: 4,
  },
  {
    key: "prompt_reminder_format",
    label: "Reminder Format (sign-up)",
    description:
      "Sent to volunteers who have NOT yet signed up when an admin clicks 'Send reminder' on an event. Variables: {service_name}, {date}. Missing variables render as empty strings.",
    rows: 4,
  },
  {
    key: "prompt_recruitment_message",
    label: "Recruitment Agent Message",
    description:
      "Default SMS the Recruitment Agent sends to volunteers when a campaign's per-wave message_templates don't override it. Variables: {first_name}, {name_part} (' Alice' or empty), {event_label}, {event_date}, {event_start_time}, {event_end_time}, {hours} (computed duration, e.g. '2' or '1.5'), {event_location}, {service_name}. Keep under ~160 characters where possible.",
    rows: 4,
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

  // If the entries list ever changes (e.g., switching between AI / Templates
  // tabs), reset the selected key to the first valid one.
  useEffect(() => {
    if (entries.length > 0 && !entries.some((e) => e.key === selectedKey)) {
      setSelectedKey(entries[0].key);
    }
  }, [entries, selectedKey]);

  const selectedEntry = useMemo(
    () => entries.find((e) => e.key === selectedKey) ?? entries[0],
    [entries, selectedKey]
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
        <div className="space-y-2">
          <Label className="text-sm font-medium">Prompt</Label>
          <Select value={selectedEntry.key} onValueChange={setSelectedKey}>
            <SelectTrigger className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {entries.map((e) => {
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
