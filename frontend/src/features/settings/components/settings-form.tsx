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

const AI_MODEL_OPTIONS = [
  { value: "claude-haiku-4-5-20241022", label: "Claude Haiku 4.5 (default)" },
  { value: "claude-sonnet-4-5-20250514", label: "Claude Sonnet 4.5" },
  { value: "claude-sonnet-4-6", label: "Claude Sonnet 4.6" },
];

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
              setValues((prev) => ({ ...prev, ai_model: v }))
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
        {settings && settings.filter((s) => s.key !== "ai_model").length === 0 && (
          <p className="text-sm text-muted-foreground">
            No additional settings configured.
          </p>
        )}
        {settings?.filter((s) => s.key !== "ai_model").map((s) => (
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
  );
}
