import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Button } from "@/components/ui/button";
import { Plus, Trash2 } from "lucide-react";
import { DAYS_OF_WEEK } from "@/lib/constants";
import type { AvailabilityRuleResponse, AvailabilityRuleUpdate } from "@/types/api";

interface SlotRule {
  label: string;
  start_time: string;
  end_time: string;
  slot_duration_minutes: number;
  buffer_minutes: number;
  is_active: boolean;
}

const DEFAULT_SLOT: SlotRule = {
  label: "",
  start_time: "09:00",
  end_time: "17:00",
  slot_duration_minutes: 60,
  buffer_minutes: 0,
  is_active: true,
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
  // State: map of day_of_week -> array of slot rules
  const [schedule, setSchedule] = useState<Record<number, SlotRule[]>>({});

  useEffect(() => {
    const grouped: Record<number, SlotRule[]> = {};
    for (let i = 0; i < 7; i++) {
      grouped[i] = [];
    }
    for (const rule of rules) {
      grouped[rule.day_of_week].push({
        label: rule.label || "",
        start_time: rule.start_time,
        end_time: rule.end_time,
        slot_duration_minutes: rule.slot_duration_minutes,
        buffer_minutes: rule.buffer_minutes,
        is_active: rule.is_active,
      });
    }
    setSchedule(grouped);
  }, [rules]);

  function addSlot(day: number) {
    setSchedule((prev) => ({
      ...prev,
      [day]: [...(prev[day] || []), { ...DEFAULT_SLOT }],
    }));
  }

  function removeSlot(day: number, slotIndex: number) {
    setSchedule((prev) => ({
      ...prev,
      [day]: prev[day].filter((_, i) => i !== slotIndex),
    }));
  }

  function updateSlot(day: number, slotIndex: number, updates: Partial<SlotRule>) {
    setSchedule((prev) => ({
      ...prev,
      [day]: prev[day].map((slot, i) =>
        i === slotIndex ? { ...slot, ...updates } : slot
      ),
    }));
  }

  function handleSave() {
    const allRules: AvailabilityRuleUpdate[] = [];
    for (let day = 0; day < 7; day++) {
      for (const slot of schedule[day] || []) {
        allRules.push({
          day_of_week: day,
          label: slot.label || undefined,
          start_time: slot.start_time,
          end_time: slot.end_time,
          slot_duration_minutes: slot.slot_duration_minutes,
          buffer_minutes: slot.buffer_minutes,
          is_active: slot.is_active,
        });
      }
    }
    onSave(allRules);
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>Weekly Schedule</CardTitle>
        {canEdit && (
          <Button size="sm" onClick={handleSave} disabled={isSaving}>
            {isSaving ? "Saving..." : "Save Schedule"}
          </Button>
        )}
      </CardHeader>
      <CardContent className="space-y-4">
        {DAYS_OF_WEEK.map((dayName, dayIndex) => {
          const slots = schedule[dayIndex] || [];
          return (
            <div key={dayIndex} className="rounded-md border p-3 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-sm font-semibold">{dayName}</span>
                {canEdit && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => addSlot(dayIndex)}
                    className="h-7 text-xs"
                  >
                    <Plus className="h-3 w-3 mr-1" />
                    Add Slot
                  </Button>
                )}
              </div>

              {slots.length === 0 && (
                <p className="text-xs text-muted-foreground py-1">
                  No slots — day off
                </p>
              )}

              {slots.map((slot, slotIdx) => (
                <div
                  key={slotIdx}
                  className="flex flex-wrap items-end gap-3 rounded bg-muted/50 p-2"
                >
                  <div className="flex items-center gap-2">
                    <Switch
                      checked={slot.is_active}
                      onCheckedChange={(v) =>
                        updateSlot(dayIndex, slotIdx, { is_active: v })
                      }
                      disabled={!canEdit}
                    />
                  </div>
                  <div className="space-y-1 flex-1 min-w-[140px]">
                    <Label className="text-xs">Label</Label>
                    <Input
                      value={slot.label}
                      onChange={(e) =>
                        updateSlot(dayIndex, slotIdx, { label: e.target.value })
                      }
                      placeholder="e.g. Morning Consultations"
                      className="h-8"
                      disabled={!canEdit}
                    />
                  </div>
                  <div className="space-y-1">
                    <Label className="text-xs">Start</Label>
                    <Input
                      type="time"
                      value={slot.start_time}
                      onChange={(e) =>
                        updateSlot(dayIndex, slotIdx, { start_time: e.target.value })
                      }
                      className="w-28 h-8"
                      disabled={!canEdit}
                    />
                  </div>
                  <div className="space-y-1">
                    <Label className="text-xs">End</Label>
                    <Input
                      type="time"
                      value={slot.end_time}
                      onChange={(e) =>
                        updateSlot(dayIndex, slotIdx, { end_time: e.target.value })
                      }
                      className="w-28 h-8"
                      disabled={!canEdit}
                    />
                  </div>
                  <div className="space-y-1">
                    <Label className="text-xs">Slot (min)</Label>
                    <Input
                      type="number"
                      value={slot.slot_duration_minutes}
                      onChange={(e) =>
                        updateSlot(dayIndex, slotIdx, {
                          slot_duration_minutes: Number(e.target.value),
                        })
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
                      value={slot.buffer_minutes}
                      onChange={(e) =>
                        updateSlot(dayIndex, slotIdx, {
                          buffer_minutes: Number(e.target.value),
                        })
                      }
                      className="w-20 h-8"
                      min={0}
                      disabled={!canEdit}
                    />
                  </div>
                  {canEdit && (
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8 text-destructive hover:text-destructive"
                      onClick={() => removeSlot(dayIndex, slotIdx)}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  )}
                </div>
              ))}
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}
