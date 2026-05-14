import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
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

  useEffect(() => {
    if (prompts) {
      const valMap: Record<string, string> = {};
      const defMap: Record<string, string> = {};
      const overrideMap: Record<string, boolean> = {};
      for (const p of prompts) {
        valMap[p.key] = p.value;
        // Backwards-compatible: older API responses may not yet include
        // default_value, in which case fall back to the saved value.
        defMap[p.key] = p.default_value ?? p.value;
        overrideMap[p.key] = !p.is_default;
      }
      setValues(valMap);
      setDefaults(defMap);
      setSavedOverrides(overrideMap);
    } else {
      setValues({});
      setDefaults({});
      setSavedOverrides({});
    }
  }, [prompts]);

  function handleSave() {
    // Save only the entries this editor manages so the two tabs don't stomp each other
    const subset: Record<string, string> = {};
    for (const e of entries) {
      if (values[e.key] !== undefined) subset[e.key] = values[e.key];
    }
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

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle className="text-base">{title}</CardTitle>
        <Button size="sm" onClick={handleSave} disabled={update.isPending}>
          {update.isPending ? "Saving..." : "Save All"}
        </Button>
      </CardHeader>
      <CardContent className="space-y-6">
        {entries.map((entry) => {
          const current = values[entry.key] ?? "";
          const def = defaults[entry.key] ?? "";
          const isOverride = savedOverrides[entry.key];
          const isDirty = current !== def;
          return (
            <div key={entry.key} className="space-y-2">
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <Label className="text-sm font-medium">{entry.label}</Label>
                  {isOverride && (
                    <Badge variant="secondary" className="text-[10px]">
                      Customized
                    </Badge>
                  )}
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleReset(entry.key)}
                  disabled={!isDirty}
                  title={
                    isDirty
                      ? "Replace with the latest shipped default"
                      : "Already matches the latest default"
                  }
                >
                  Reset to Default
                </Button>
              </div>
              {entry.description && (
                <p className="text-xs text-muted-foreground">{entry.description}</p>
              )}
              <Textarea
                className="min-h-[120px] font-mono text-sm"
                value={current}
                onChange={(e) =>
                  setValues((prev) => ({ ...prev, [entry.key]: e.target.value }))
                }
                rows={entry.rows ?? 4}
              />
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}

export { AI_PROMPT_ENTRIES, TEMPLATE_ENTRIES };
