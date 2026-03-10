import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { useSettings, useUpdateSettings } from "../hooks/use-settings";
import { formatDateTime } from "@/lib/utils";

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
        {settings && settings.length === 0 && (
          <p className="text-sm text-muted-foreground">
            No settings configured yet.
          </p>
        )}
        {settings?.map((s) => (
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
