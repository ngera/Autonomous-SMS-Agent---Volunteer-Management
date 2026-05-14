import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Button } from "@/components/ui/button";
import { Plus, Trash2, X } from "lucide-react";
import { ServiceCategoryPicker } from "@/components/shared/service-category-picker";
import { DAYS_OF_WEEK } from "@/lib/constants";
import { useAppointmentTypes } from "@/features/appointment-types/hooks/use-appointment-types";
import type { AvailabilityRuleResponse, AvailabilityRuleUpdate, ServiceSlotConfig } from "@/types/api";

interface SlotRule {
  label: string;
  location: string;
  start_time: string;
  end_time: string;
  buffer_minutes: number;
  service_config: ServiceSlotConfig[];
  is_active: boolean;
  allow_roster_sharing: boolean;
}

const DEFAULT_SLOT: SlotRule = {
  label: "",
  location: "",
  start_time: "09:00",
  end_time: "17:00",
  buffer_minutes: 0,
  service_config: [],
  is_active: true,
  allow_roster_sharing: true,
};

interface WeeklyScheduleBuilderProps {
  rules: AvailabilityRuleResponse[];
  onSave: (rules: AvailabilityRuleUpdate[]) => void;
  isSaving: boolean;
  canEdit: boolean;
}

export function WeeklyScheduleBuilder({ rules, onSave, isSaving, canEdit }: WeeklyScheduleBuilderProps) {
  const [schedule, setSchedule] = useState<Record<number, SlotRule[]>>({});
  const { data: appointmentTypes } = useAppointmentTypes();
  const activeTypes = (appointmentTypes ?? []).filter((t) => t.is_active);

  useEffect(() => {
    const grouped: Record<number, SlotRule[]> = {};
    for (let i = 0; i < 7; i++) grouped[i] = [];
    for (const rule of rules) {
      grouped[rule.day_of_week].push({
        label: rule.label || "",
        location: rule.location || "",
        start_time: rule.start_time,
        end_time: rule.end_time,
        buffer_minutes: rule.buffer_minutes,
        service_config: rule.service_config ?? [],
        is_active: rule.is_active,
        allow_roster_sharing: rule.allow_roster_sharing ?? true,
      });
    }
    setSchedule(grouped);
  }, [rules]);

  function addSlot(day: number) {
    setSchedule((prev) => ({ ...prev, [day]: [...(prev[day] || []), { ...DEFAULT_SLOT, service_config: [] }] }));
  }
  function removeSlot(day: number, idx: number) {
    setSchedule((prev) => ({ ...prev, [day]: prev[day].filter((_, i) => i !== idx) }));
  }
  function updateSlot(day: number, idx: number, updates: Partial<SlotRule>) {
    setSchedule((prev) => ({ ...prev, [day]: prev[day].map((s, i) => (i === idx ? { ...s, ...updates } : s)) }));
  }

  function toggleService(day: number, idx: number, typeId: string) {
    const slot = schedule[day][idx];
    const existing = slot.service_config.find((c) => c.appointment_type_id === typeId);
    const updated = existing
      ? slot.service_config.filter((c) => c.appointment_type_id !== typeId)
      : [...slot.service_config, { appointment_type_id: typeId, min_required: 1, max_allowed: 1 }];
    updateSlot(day, idx, { service_config: updated });
  }

  function updateServiceField(day: number, idx: number, typeId: string, field: "min_required" | "max_allowed", value: number) {
    const slot = schedule[day][idx];
    const updated = slot.service_config.map((c) => {
      if (c.appointment_type_id !== typeId) return c;
      const next = { ...c, [field]: value };
      // Auto-correct: max must be >= min
      if (next.max_allowed < next.min_required) {
        next.max_allowed = next.min_required;
      }
      return next;
    });
    updateSlot(day, idx, { service_config: updated });
  }

  function handleSave() {
    const allRules: AvailabilityRuleUpdate[] = [];
    for (let day = 0; day < 7; day++) {
      for (const slot of schedule[day] || []) {
        allRules.push({
          day_of_week: day,
          label: slot.label || undefined,
          location: slot.location.trim() || undefined,
          start_time: slot.start_time,
          end_time: slot.end_time,
          buffer_minutes: slot.buffer_minutes,
          service_config: slot.service_config.length > 0 ? slot.service_config : null,
          is_active: slot.is_active,
          allow_roster_sharing: slot.allow_roster_sharing,
        });
      }
    }
    onSave(allRules);
  }

  function getTypeName(id: string) {
    return activeTypes.find((t) => t.id === id)?.name ?? id.slice(0, 8);
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
        <p className="text-xs text-muted-foreground">
          Define when the organization is open and which services are needed with min/max participants.
        </p>
        {DAYS_OF_WEEK.map((dayName, dayIndex) => {
          const slots = schedule[dayIndex] || [];
          return (
            <div key={dayIndex} className="rounded-md border p-3 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-sm font-semibold">{dayName}</span>
                {canEdit && (
                  <Button variant="outline" size="sm" onClick={() => addSlot(dayIndex)} className="h-7 text-xs">
                    <Plus className="h-3 w-3 mr-1" /> Add Window
                  </Button>
                )}
              </div>
              {slots.length === 0 && <p className="text-xs text-muted-foreground py-1">No windows — day off</p>}
              {slots.map((slot, slotIdx) => (
                <div key={slotIdx} className="rounded bg-muted/50 p-2 space-y-2">
                  <div className="flex flex-wrap items-end gap-3">
                    <Switch checked={slot.is_active} onCheckedChange={(v) => updateSlot(dayIndex, slotIdx, { is_active: v })} disabled={!canEdit} />
                    <div className="space-y-1 flex-1 min-w-[140px]">
                      <Label className="text-xs">Label</Label>
                      <Input value={slot.label} onChange={(e) => updateSlot(dayIndex, slotIdx, { label: e.target.value })} placeholder="e.g. Morning Shift" className="h-8" disabled={!canEdit} />
                    </div>
                    <div className="space-y-1 flex-1 min-w-[200px]">
                      <Label className="text-xs">Address</Label>
                      <Input
                        value={slot.location}
                        onChange={(e) => updateSlot(dayIndex, slotIdx, { location: e.target.value })}
                        placeholder="e.g. 123 Main St, Springfield, IL 62701"
                        className="h-8"
                        disabled={!canEdit}
                      />
                    </div>
                    <div className="space-y-1">
                      <Label className="text-xs">Start</Label>
                      <Input type="time" value={slot.start_time} onChange={(e) => updateSlot(dayIndex, slotIdx, { start_time: e.target.value })} className="w-28 h-8" disabled={!canEdit} />
                    </div>
                    <div className="space-y-1">
                      <Label className="text-xs">End</Label>
                      <Input type="time" value={slot.end_time} onChange={(e) => updateSlot(dayIndex, slotIdx, { end_time: e.target.value })} className="w-28 h-8" disabled={!canEdit} />
                    </div>
                    <div className="space-y-1">
                      <Label className="text-xs">Buffer (min)</Label>
                      <Input type="number" value={slot.buffer_minutes} onChange={(e) => updateSlot(dayIndex, slotIdx, { buffer_minutes: Number(e.target.value) })} className="w-20 h-8" min={0} disabled={!canEdit} />
                    </div>
                    {canEdit && (
                      <Button variant="ghost" size="icon" className="h-8 w-8 text-destructive" onClick={() => removeSlot(dayIndex, slotIdx)}>
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    )}
                  </div>

                  {/* Services config */}
                  <div className="pl-10 space-y-1.5">
                    <Label className="text-xs text-muted-foreground">Services needed:</Label>
                    {slot.service_config.length === 0 && (
                      <p className="text-xs text-muted-foreground italic">
                        All services (min 1, max 1) — add specific services below to override.
                      </p>
                    )}
                    {slot.service_config.length > 0 && (
                      <div className="flex flex-wrap gap-2">
                        {slot.service_config.map((cfg) => (
                          <div key={cfg.appointment_type_id} className="flex items-center gap-1.5 rounded-md border bg-background px-2 py-1">
                            <span className="text-xs font-medium">{getTypeName(cfg.appointment_type_id)}</span>
                            <span className="text-xs text-muted-foreground">min</span>
                            <Input type="number" value={cfg.min_required} onChange={(e) => updateServiceField(dayIndex, slotIdx, cfg.appointment_type_id, "min_required", Math.max(1, Number(e.target.value)))} className="w-12 h-6 text-xs text-center p-0" min={1} disabled={!canEdit} />
                            <span className="text-xs text-muted-foreground">max</span>
                            <Input type="number" value={cfg.max_allowed} onChange={(e) => updateServiceField(dayIndex, slotIdx, cfg.appointment_type_id, "max_allowed", Math.max(cfg.min_required, Number(e.target.value)))} className="w-12 h-6 text-xs text-center p-0" min={cfg.min_required} disabled={!canEdit} />
                            {canEdit && <X className="h-3 w-3 cursor-pointer text-muted-foreground hover:text-foreground" onClick={() => toggleService(dayIndex, slotIdx, cfg.appointment_type_id)} />}
                          </div>
                        ))}
                      </div>
                    )}
                    {canEdit && activeTypes.length > 0 && (
                      <ServiceCategoryPicker
                        activeTypes={activeTypes}
                        excludeIds={slot.service_config.map((c) => c.appointment_type_id)}
                        onAdd={(typeId) => toggleService(dayIndex, slotIdx, typeId)}
                        size="sm"
                      />
                    )}
                    <label className="flex items-center gap-2 pt-1 text-xs text-muted-foreground">
                      <input
                        type="checkbox"
                        checked={slot.allow_roster_sharing}
                        onChange={(e) => updateSlot(dayIndex, slotIdx, { allow_roster_sharing: e.target.checked })}
                        disabled={!canEdit}
                        className="h-3.5 w-3.5"
                      />
                      Allow volunteers to see who else is signed up
                    </label>
                  </div>
                </div>
              ))}
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}
