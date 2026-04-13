import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { usePrompts, useUpdateSettings } from "../hooks/use-settings";
import { useTenantFilter } from "@/context/tenant-filter-context";

const PROMPT_LABELS: Record<string, string> = {
  prompt_customer_system: "Volunteer SMS Prompt",
  prompt_admin_system: "Admin SMS Prompt",
  prompt_conversation_system: "Legacy Conversation Prompt",
  prompt_screener_system: "Message Screener Prompt",
  prompt_fallback_message: "Fallback Message",
  prompt_error_message: "Error Message",
};

const PROMPT_DESCRIPTIONS: Record<string, string> = {
  prompt_customer_system:
    "System prompt for customer SMS conversations (tool_use mode). Template variables: {business_name}, {custom_instructions}",
  prompt_admin_system:
    "System prompt for admin SMS conversations (tool_use mode). Template variables: {business_name}, {custom_instructions}",
  prompt_conversation_system:
    "Legacy chatbot prompt (kept for reference). Template variables: {business_name}, {types_text}, {related_text}, {slots_text}, {history_text}, {custom_instructions}",
  prompt_screener_system:
    "Classifies inbound messages as RELEVANT, IRRELEVANT, or ABUSIVE before reaching the chatbot.",
  prompt_fallback_message:
    "Sent to customers when the AI cannot understand their message.",
  prompt_error_message:
    "Sent to customers when a technical error occurs.",
};

const PROMPT_ORDER = [
  "prompt_customer_system",
  "prompt_admin_system",
  "prompt_screener_system",
  "prompt_fallback_message",
  "prompt_error_message",
];

export function PromptEditor() {
  const { selectedTenantIds, isSuperAdmin } = useTenantFilter();
  const hasTenant = !isSuperAdmin || selectedTenantIds.length === 1;
  const { data: prompts, isLoading } = usePrompts();
  const update = useUpdateSettings();
  const [values, setValues] = useState<Record<string, string>>({});
  const [defaults, setDefaults] = useState<Record<string, string>>({});

  useEffect(() => {
    if (prompts) {
      const valMap: Record<string, string> = {};
      const defMap: Record<string, string> = {};
      for (const p of prompts) {
        valMap[p.key] = p.value;
        defMap[p.key] = p.value;
      }
      setValues(valMap);
      setDefaults(defMap);
    } else {
      // Clear when no tenant is selected
      setValues({});
      setDefaults({});
    }
  }, [prompts]);

  function handleSave() {
    update.mutate(
      { settings: values },
      {
        onSuccess: () => {
          // Also invalidate prompts query
        },
      }
    );
  }

  function handleReset(key: string) {
    // Remove from values so default is used — save empty to remove DB override
    // Actually, we need to save the default value back
    if (defaults[key]) {
      setValues((prev) => ({ ...prev, [key]: defaults[key] }));
    }
  }

  if (!hasTenant) {
    return (
      <Card>
        <CardContent className="py-8 text-center text-sm text-muted-foreground">
          Select a tenant from the filter above to view and edit AI prompts.
        </CardContent>
      </Card>
    );
  }

  if (isLoading) {
    return (
      <Card>
        <CardContent className="py-8 text-center text-sm text-muted-foreground">
          Loading prompts...
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle className="text-base">AI Prompts</CardTitle>
        <Button size="sm" onClick={handleSave} disabled={update.isPending}>
          {update.isPending ? "Saving..." : "Save All"}
        </Button>
      </CardHeader>
      <CardContent className="space-y-6">
        {PROMPT_ORDER.map((key) => (
          <div key={key} className="space-y-2">
            <div className="flex items-center justify-between">
              <Label className="text-sm font-medium">
                {PROMPT_LABELS[key] ?? key}
              </Label>
              <Button
                variant="outline"
                size="sm"
                onClick={() => handleReset(key)}
              >
                Reset to Default
              </Button>
            </div>
            {PROMPT_DESCRIPTIONS[key] && (
              <p className="text-xs text-muted-foreground">
                {PROMPT_DESCRIPTIONS[key]}
              </p>
            )}
            <Textarea
              className="min-h-[120px] font-mono text-sm"
              value={values[key] ?? ""}
              onChange={(e) =>
                setValues((prev) => ({ ...prev, [key]: e.target.value }))
              }
              rows={key.includes("system") ? 8 : 4}
            />
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
