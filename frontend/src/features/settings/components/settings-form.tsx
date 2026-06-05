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
import { useAuth } from "@/hooks/use-auth";
import { AdminRole } from "@/types/enums";

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

// Daily KPI digest SMS — sent to OWNER + MANAGER admins on configured
// days at the configured tenant-local time. Default off so new tenants
// don't get unexpected messages until an admin opts in.
const KPI_SUMMARY_DEFAULTS: Record<string, string> = {
  kpi_summary_sms_enabled: "false",
  kpi_summary_sms_time: "08:00",
  kpi_summary_sms_days_of_week: "0,1,2,3,4", // Mon-Fri
};
const KPI_SUMMARY_KEYS = Object.keys(KPI_SUMMARY_DEFAULTS);
const DOW_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

// Per-tenant LLM rate limit (calls per rolling 60-second window). See
// design_decisions.md #15. Backend enforces bounds [10, 1000]; out-of-
// range values silently fall back to the default.
const LLM_RATE_LIMIT_KEY = "llm_rate_limit_rpm";
const LLM_RATE_LIMIT_DEFAULT = "60";
const LLM_RATE_LIMIT_MIN = 10;
const LLM_RATE_LIMIT_MAX = 1000;

// Special-cased keys we render with their own typed input.
const SPECIAL_KEYS = new Set([LLM_RATE_LIMIT_KEY]);

// Setting keys that are internal state markers (written by background jobs)
// rather than configuration. They're stored in system_settings for
// per-tenant scoping but shouldn't appear in the admin UI.
const HIDDEN_KEY_PREFIXES = ["last_reminder_", "last_kpi_summary_sent_"];

function isHiddenSettingKey(key: string): boolean {
  return HIDDEN_KEY_PREFIXES.some((p) => key.startsWith(p));
}

export function SettingsForm() {
  const { hasRole } = useAuth();
  const isSuperAdmin = hasRole(AdminRole.SUPER_ADMIN);
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

  function getKpiValue(key: string): string {
    return values[key] ?? KPI_SUMMARY_DEFAULTS[key] ?? "";
  }

  function setKpiValue(key: string, val: string) {
    setValues((prev) => ({ ...prev, [key]: val }));
  }

  // CSV of "0,1,2..." (0=Mon..6=Sun) <-> Set<number>.
  const kpiDaysCsv = getKpiValue("kpi_summary_sms_days_of_week");
  const kpiDays = new Set(
    kpiDaysCsv
      .split(",")
      .map((x) => Number(x.trim()))
      .filter((x) => Number.isInteger(x) && x >= 0 && x <= 6),
  );
  function toggleKpiDay(d: number) {
    const next = new Set(kpiDays);
    if (next.has(d)) next.delete(d);
    else next.add(d);
    setKpiValue(
      "kpi_summary_sms_days_of_week",
      [...next].sort((a, b) => a - b).join(","),
    );
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
        {/* LLM rate limit — super-admin only. Read-only display for
            non-super-admins so owners understand what's enforced but
            can't change it. */}
        <div className="space-y-1">
          <Label className="text-sm font-medium">
            LLM rate limit (calls per minute, per tenant)
          </Label>
          <p className="text-xs text-muted-foreground">
            Maximum Anthropic API calls this tenant may make in a rolling
            60-second window. Catches runaway loops without affecting
            normal use. Default {LLM_RATE_LIMIT_DEFAULT}; bounds{" "}
            {LLM_RATE_LIMIT_MIN}–{LLM_RATE_LIMIT_MAX}. Super-admin only.
          </p>
          <Input
            type="number"
            min={LLM_RATE_LIMIT_MIN}
            max={LLM_RATE_LIMIT_MAX}
            value={values[LLM_RATE_LIMIT_KEY] ?? LLM_RATE_LIMIT_DEFAULT}
            onChange={(e) =>
              setValues((prev) => ({
                ...prev,
                [LLM_RATE_LIMIT_KEY]: e.target.value,
              }))
            }
            disabled={!isSuperAdmin}
            className="w-32"
            title={
              isSuperAdmin
                ? undefined
                : "Only super-admins can change this limit."
            }
          />
        </div>
        {settings && settings.filter((s) => s.key !== "ai_model" && !SUSPENSION_KEYS.includes(s.key) && !KPI_SUMMARY_KEYS.includes(s.key) && !SPECIAL_KEYS.has(s.key) && !isHiddenSettingKey(s.key)).length === 0 && (
          <p className="text-sm text-muted-foreground">
            No additional settings configured.
          </p>
        )}
        {settings?.filter((s) => s.key !== "ai_model" && !SUSPENSION_KEYS.includes(s.key) && !KPI_SUMMARY_KEYS.includes(s.key) && !SPECIAL_KEYS.has(s.key) && !isHiddenSettingKey(s.key)).map((s) => (
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

    <Card>
      <CardHeader>
        <CardTitle className="text-base">Daily Status SMS</CardTitle>
      </CardHeader>
      <CardContent className="space-y-5">
        <div className="flex items-center gap-3">
          <Switch
            checked={getKpiValue("kpi_summary_sms_enabled") === "true"}
            onCheckedChange={(checked) =>
              setKpiValue("kpi_summary_sms_enabled", checked ? "true" : "false")
            }
          />
          <div>
            <Label className="text-sm font-medium">
              Send daily KPI digest to OWNER + MANAGER admins
            </Label>
            <p className="text-xs text-muted-foreground">
              SMS with the same dashboard numbers (events, open slots,
              at-risk, campaigns) for the next 2 weeks and the planning
              horizon. Admins can also text “summary” or “how are things
              going?” for the same digest on demand.
            </p>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-1">
            <Label className="text-sm font-medium">Time (tenant local)</Label>
            <p className="text-xs text-muted-foreground">
              The digest goes out at or just after this time on each
              configured day.
            </p>
            <Input
              type="time"
              className="w-40"
              value={getKpiValue("kpi_summary_sms_time")}
              onChange={(e) =>
                setKpiValue("kpi_summary_sms_time", e.target.value)
              }
            />
          </div>
        </div>

        <div className="space-y-2">
          <Label className="text-sm font-medium">Days of week</Label>
          <p className="text-xs text-muted-foreground">
            Pick the days you want the digest. Defaults to Mon–Fri.
          </p>
          <div className="flex flex-wrap gap-1.5">
            {DOW_LABELS.map((label, idx) => {
              const active = kpiDays.has(idx);
              return (
                <button
                  key={label}
                  type="button"
                  onClick={() => toggleKpiDay(idx)}
                  className={
                    "rounded-md border px-3 py-1 text-xs font-medium transition-colors " +
                    (active
                      ? "border-primary bg-primary text-primary-foreground"
                      : "border-input bg-background text-foreground hover:bg-accent")
                  }
                >
                  {label}
                </button>
              );
            })}
          </div>
        </div>
      </CardContent>
    </Card>
    </>
  );
}
