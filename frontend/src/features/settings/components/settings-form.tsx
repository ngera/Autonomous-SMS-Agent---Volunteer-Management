import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useSettings, useUpdateSettings } from "../hooks/use-settings";
import { formatDateTime } from "@/lib/utils";

import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";

const AI_MODEL_OPTIONS = [
  { value: "claude-haiku-4-5-20251001", label: "Claude Haiku 4.5 (default)" },
  { value: "claude-sonnet-4-5-20250514", label: "Claude Sonnet 4.5" },
  { value: "claude-sonnet-4-6", label: "Claude Sonnet 4.6" },
];

const SUSPENSION_DEFAULTS: Record<string, string> = {
  suspension_max_strikes: "4",
  suspension_strike_decay_days: "30",
  suspension_auto_suspend_abusive: "true",
  suspension_strike_message_1: "I can only help with booking appointments. Would you like to schedule one?",
  suspension_strike_message_2: "Please keep messages relevant to booking. Further off-topic messages may suspend your access.",
  suspension_strike_message_3: "This is your final warning. Further off-topic messages will suspend your access.",
  suspension_suspension_message: "Your access has been temporarily suspended. Contact us directly if you believe this is an error.",
};

const SUSPENSION_KEYS = Object.keys(SUSPENSION_DEFAULTS);

export function SettingsForm() {
  const { data: settings, isLoading } = useSettings();
  const update = useUpdateSettings();
  const [values, setValues] = useState<Record<string, string>>({});

  useEffect(() => {
    if (settings) {
      const map: Record<string, string> = {};
      for (const s of settings) {
        map[s.key] = s.value;
      }
      setValues(map);
    }
  }, [settings]);

  function getSuspensionValue(key: string): string {
    return values[key] ?? SUSPENSION_DEFAULTS[key] ?? "";
  }

  function setSuspensionValue(key: string, val: string) {
    setValues((prev) => ({ ...prev, [key]: val }));
  }

  function handleSave() {
    update.mutate({ settings: values });
  }

  if (isLoading) {
    return (
      <Card>
        <CardContent className="py-8 text-center text-sm text-muted-foreground">
          Loading settings...
        </CardContent>
      </Card>
    );
  }

  return (
    <>
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle className="text-base">System Settings</CardTitle>
        <Button size="sm" onClick={handleSave} disabled={update.isPending}>
          {update.isPending ? "Saving..." : "Save"}
        </Button>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-1">
          <Label className="text-sm font-medium">AI Model</Label>
          <p className="text-xs text-muted-foreground">
            Claude model used for SMS conversations. Haiku is cheapest; Sonnet is more capable.
          </p>
          <Select
            value={values["ai_model"] ?? "claude-haiku-4-5-20241022"}
            onValueChange={(v) =>
              setValues((prev) => ({ ...prev, ai_model: v ?? "" }))
            }
          >
            <SelectTrigger className="w-72">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {AI_MODEL_OPTIONS.map((opt) => (
                <SelectItem key={opt.value} value={opt.value}>
                  {opt.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        {settings && settings.filter((s) => s.key !== "ai_model" && !SUSPENSION_KEYS.includes(s.key)).length === 0 && (
          <p className="text-sm text-muted-foreground">
            No additional settings configured.
          </p>
        )}
        {settings?.filter((s) => s.key !== "ai_model" && !SUSPENSION_KEYS.includes(s.key)).map((s) => (
          <div key={s.key} className="space-y-1">
            <div className="flex items-center justify-between">
              <Label className="text-sm font-medium">{s.key}</Label>
              <span className="text-xs text-muted-foreground">
                Updated {formatDateTime(s.updated_at)}
              </span>
            </div>
            <Input
              value={values[s.key] ?? ""}
              onChange={(e) =>
                setValues((prev) => ({ ...prev, [s.key]: e.target.value }))
              }
            />
          </div>
        ))}
      </CardContent>
    </Card>

    <Card>
      <CardHeader>
        <CardTitle className="text-base">Suspension & Strike Settings</CardTitle>
      </CardHeader>
      <CardContent className="space-y-5">
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-1">
            <Label className="text-sm font-medium">Max Strikes Before Suspension</Label>
            <p className="text-xs text-muted-foreground">
              Number of irrelevant messages before the customer is suspended.
            </p>
            <Input
              type="number"
              min={1}
              max={20}
              value={getSuspensionValue("suspension_max_strikes")}
              onChange={(e) => setSuspensionValue("suspension_max_strikes", e.target.value)}
              className="w-24"
            />
          </div>
          <div className="space-y-1">
            <Label className="text-sm font-medium">Strike Decay (Days)</Label>
            <p className="text-xs text-muted-foreground">
              Strikes older than this are ignored when counting.
            </p>
            <Input
              type="number"
              min={1}
              max={365}
              value={getSuspensionValue("suspension_strike_decay_days")}
              onChange={(e) => setSuspensionValue("suspension_strike_decay_days", e.target.value)}
              className="w-24"
            />
          </div>
        </div>

        <div className="flex items-center gap-3">
          <Switch
            checked={getSuspensionValue("suspension_auto_suspend_abusive") === "true"}
            onCheckedChange={(checked) =>
              setSuspensionValue("suspension_auto_suspend_abusive", checked ? "true" : "false")
            }
          />
          <div>
            <Label className="text-sm font-medium">Auto-Suspend on Abusive Messages</Label>
            <p className="text-xs text-muted-foreground">
              Immediately suspend the customer on the first abusive message.
            </p>
          </div>
        </div>

        <div className="space-y-3">
          <Label className="text-sm font-medium">Strike Warning Messages</Label>
          <p className="text-xs text-muted-foreground">
            Messages sent to the customer at each strike level. Leave blank to skip that warning.
          </p>
          <div className="space-y-2">
            <div className="space-y-1">
              <Label className="text-xs text-muted-foreground">Strike 1</Label>
              <Textarea
                rows={2}
                value={getSuspensionValue("suspension_strike_message_1")}
                onChange={(e) => setSuspensionValue("suspension_strike_message_1", e.target.value)}
              />
            </div>
            <div className="space-y-1">
              <Label className="text-xs text-muted-foreground">Strike 2</Label>
              <Textarea
                rows={2}
                value={getSuspensionValue("suspension_strike_message_2")}
                onChange={(e) => setSuspensionValue("suspension_strike_message_2", e.target.value)}
              />
            </div>
            <div className="space-y-1">
              <Label className="text-xs text-muted-foreground">Strike 3</Label>
              <Textarea
                rows={2}
                value={getSuspensionValue("suspension_strike_message_3")}
                onChange={(e) => setSuspensionValue("suspension_strike_message_3", e.target.value)}
              />
            </div>
          </div>
        </div>

        <div className="space-y-1">
          <Label className="text-sm font-medium">Suspension Message</Label>
          <p className="text-xs text-muted-foreground">
            Sent to the customer when they are suspended.
          </p>
          <Textarea
            rows={2}
            value={getSuspensionValue("suspension_suspension_message")}
            onChange={(e) => setSuspensionValue("suspension_suspension_message", e.target.value)}
          />
        </div>
      </CardContent>
    </Card>
    </>
  );
}
