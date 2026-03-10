import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Button } from "@/components/ui/button";
import { DAYS_OF_WEEK } from "@/lib/constants";
import type { AvailabilityRuleResponse, AvailabilityRuleUpdate } from "@/types/api";

interface DayRule {
  day_of_week: number;
  start_time: string;
  end_time: string;
  slot_duration_minutes: number;
  buffer_minutes: number;
  is_active: boolean;
}

const DEFAULT_RULE: Omit<DayRule, "day_of_week"> = {
  start_time: "09:00",
  end_time: "17:00",
  slot_duration_minutes: 60,
  buffer_minutes: 0,
  is_active: false,
};

interface WeeklyScheduleBuilderProps {
  rules: AvailabilityRuleResponse[];
  onSave: (rules: AvailabilityRuleUpdate[]) => void;
  isSaving: boolean;
  canEdit: boolean;
}

export function WeeklyScheduleBuilder({
  rules,
  onSave,
  isSaving,
  canEdit,
}: WeeklyScheduleBuilderProps) {
  const [weekRules, setWeekRules] = useState<DayRule[]>([]);

  useEffect(() => {
    const merged = DAYS_OF_WEEK.map((_, i) => {
      const existing = rules.find((r) => r.day_of_week === i);
      return existing
        ? {
            day_of_week: i,
            start_time: existing.start_time,
            end_time: existing.end_time,
            slot_duration_minutes: existing.slot_duration_minutes,
            buffer_minutes: existing.buffer_minutes,
            is_active: existing.is_active,
          }
        : { ...DEFAULT_RULE, day_of_week: i };
    });
    setWeekRules(merged);
  }, [rules]);

  function updateDay(index: number, updates: Partial<DayRule>) {
    setWeekRules((prev) =>
      prev.map((r, i) => (i === index ? { ...r, ...updates } : r))
    );
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>Weekly Schedule</CardTitle>
        {canEdit && (
          <Button
            size="sm"
            onClick={() => onSave(weekRules)}
            disabled={isSaving}
          >
            {isSaving ? "Saving..." : "Save Schedule"}
          </Button>
        )}
      </CardHeader>
      <CardContent className="space-y-3">
        {weekRules.map((rule, i) => (
          <div
            key={i}
            className="flex flex-wrap items-center gap-3 rounded-md border p-3"
          >
            <div className="w-24 flex items-center gap-2">
              <Switch
                checked={rule.is_active}
                onCheckedChange={(v) => updateDay(i, { is_active: v })}
                disabled={!canEdit}
              />
              <span className="text-sm font-medium">{DAYS_OF_WEEK[i].slice(0, 3)}</span>
            </div>
            {rule.is_active && (
              <>
                <div className="space-y-1">
                  <Label className="text-xs">Start</Label>
                  <Input
                    type="time"
                    value={rule.start_time}
                    onChange={(e) => updateDay(i, { start_time: e.target.value })}
                    className="w-28 h-8"
                    disabled={!canEdit}
                  />
                </div>
                <div className="space-y-1">
                  <Label className="text-xs">End</Label>
                  <Input
                    type="time"
                    value={rule.end_time}
                    onChange={(e) => updateDay(i, { end_time: e.target.value })}
                    className="w-28 h-8"
                    disabled={!canEdit}
                  />
                </div>
                <div className="space-y-1">
                  <Label className="text-xs">Slot (min)</Label>
                  <Input
                    type="number"
                    value={rule.slot_duration_minutes}
                    onChange={(e) =>
                      updateDay(i, { slot_duration_minutes: Number(e.target.value) })
                    }
                    className="w-20 h-8"
                    min={5}
                    disabled={!canEdit}
                  />
                </div>
                <div className="space-y-1">
                  <Label className="text-xs">Buffer (min)</Label>
                  <Input
                    type="number"
                    value={rule.buffer_minutes}
                    onChange={(e) =>
                      updateDay(i, { buffer_minutes: Number(e.target.value) })
                    }
                    className="w-20 h-8"
                    min={0}
                    disabled={!canEdit}
                  />
                </div>
              </>
            )}
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
