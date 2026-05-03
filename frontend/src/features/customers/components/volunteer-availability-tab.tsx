import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2, X } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";
import {
  AvailabilitySlot,
  AVAILABILITY_OPTIONS,
} from "@/types/enums";
import type { CustomerResponse, WeeklyHourBlock } from "@/types/api";
import { updateCustomer } from "../api";

const DAYS_OF_WEEK = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

interface VolunteerAvailabilityTabProps {
  customer: CustomerResponse;
  canEdit: boolean;
  onUpdated: () => void;
}

function trimTime(t: string): string {
  return t.length >= 5 ? t.slice(0, 5) : t;
}

export function VolunteerAvailabilityTab({
  customer,
  canEdit,
  onUpdated,
}: VolunteerAvailabilityTabProps) {
  const qc = useQueryClient();

  const [availability, setAvailability] = useState<AvailabilitySlot[]>(
    customer.availability ?? []
  );
  const [weeklyHours, setWeeklyHours] = useState<WeeklyHourBlock[]>(
    (customer.weekly_hours ?? []).map((b) => ({
      day_of_week: b.day_of_week,
      start_time: trimTime(b.start_time),
      end_time: trimTime(b.end_time),
    }))
  );
  const [unavailableDates, setUnavailableDates] = useState<string[]>(
    customer.unavailable_dates ?? []
  );
  const [rangeStart, setRangeStart] = useState("");
  const [rangeEnd, setRangeEnd] = useState("");
  const [dirty, setDirty] = useState(false);

  useEffect(() => {
    setAvailability(customer.availability ?? []);
    setWeeklyHours(
      (customer.weekly_hours ?? []).map((b) => ({
        day_of_week: b.day_of_week,
        start_time: trimTime(b.start_time),
        end_time: trimTime(b.end_time),
      }))
    );
    setUnavailableDates(customer.unavailable_dates ?? []);
    setRangeStart("");
    setRangeEnd("");
    setDirty(false);
  }, [customer]);

  function toggleAvailability(slot: AvailabilitySlot) {
    setAvailability((prev) =>
      prev.includes(slot) ? prev.filter((s) => s !== slot) : [...prev, slot]
    );
    setDirty(true);
  }

  function addWeeklyHour() {
    setWeeklyHours((prev) => [
      ...prev,
      { day_of_week: 0, start_time: "09:00", end_time: "17:00" },
    ]);
    setDirty(true);
  }
  function updateWeeklyHour(idx: number, patch: Partial<WeeklyHourBlock>) {
    setWeeklyHours((prev) =>
      prev.map((b, i) => (i === idx ? { ...b, ...patch } : b))
    );
    setDirty(true);
  }
  function removeWeeklyHour(idx: number) {
    setWeeklyHours((prev) => prev.filter((_, i) => i !== idx));
    setDirty(true);
  }

  function expandRange(from: string, to: string): string[] {
    const start = new Date(`${from}T00:00:00Z`);
    const end = new Date(`${to}T00:00:00Z`);
    if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) return [];
    if (end < start) return [];
    const out: string[] = [];
    const cursor = new Date(start);
    while (cursor <= end) {
      out.push(cursor.toISOString().slice(0, 10));
      cursor.setUTCDate(cursor.getUTCDate() + 1);
    }
    return out;
  }
  function addUnavailableRange() {
    if (!rangeStart) return;
    const dates = expandRange(rangeStart, rangeEnd || rangeStart);
    if (dates.length === 0) return;
    setUnavailableDates((prev) => {
      const merged = new Set([...prev, ...dates]);
      return Array.from(merged).sort();
    });
    setRangeStart("");
    setRangeEnd("");
    setDirty(true);
  }
  function removeUnavailableDate(d: string) {
    setUnavailableDates((prev) => prev.filter((x) => x !== d));
    setDirty(true);
  }

  const rangeValid =
    !!rangeStart && (!rangeEnd || rangeEnd >= rangeStart);

  const saveMutation = useMutation({
    mutationFn: () =>
      updateCustomer(customer.phone, {
        availability,
        weekly_hours: weeklyHours,
        unavailable_dates: unavailableDates,
      }),
    onSuccess: () => {
      setDirty(false);
      onUpdated();
      void qc.invalidateQueries({ queryKey: ["customers"] });
    },
    onError: (err: unknown) => {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail || (err as Error)?.message || "Failed to save availability";
      alert(`Could not save availability: ${detail}`);
    },
  });

  return (
    <Card>
      <CardHeader className="flex flex-row items-start justify-between">
        <div>
          <CardTitle className="text-base">Availability</CardTitle>
          <p className="mt-1 text-xs text-muted-foreground">
            When this volunteer can attend events.
          </p>
        </div>
        {canEdit && dirty && (
          <Button
            size="sm"
            onClick={() => saveMutation.mutate()}
            disabled={saveMutation.isPending}
          >
            {saveMutation.isPending ? "Saving..." : "Save"}
          </Button>
        )}
      </CardHeader>
      <CardContent className="space-y-6">
        <section className="space-y-2">
          <Label>General availability</Label>
          <p className="text-xs text-muted-foreground">
            Coarse buckets — when this volunteer is generally available.
          </p>
          <div className="grid grid-cols-2 gap-1.5 sm:grid-cols-3">
            {AVAILABILITY_OPTIONS.map((opt) => {
              const selected = availability.includes(opt.value);
              return (
                <button
                  key={opt.value}
                  type="button"
                  disabled={!canEdit}
                  onClick={() => toggleAvailability(opt.value)}
                  className={cn(
                    "rounded-md border px-2.5 py-1.5 text-xs transition-colors",
                    selected
                      ? "border-emerald-500 bg-emerald-50 text-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-200"
                      : "border-border bg-background hover:bg-muted",
                    !canEdit && "cursor-not-allowed opacity-70"
                  )}
                >
                  {opt.label}
                </button>
              );
            })}
          </div>
        </section>

        <section className="space-y-2">
          <div className="flex items-center justify-between">
            <Label>Weekly hours</Label>
            {canEdit && (
              <Button
                type="button"
                size="sm"
                variant="outline"
                className="h-7 text-xs"
                onClick={addWeeklyHour}
              >
                <Plus className="mr-1 h-3 w-3" /> Add window
              </Button>
            )}
          </div>
          <p className="text-xs text-muted-foreground">
            Specific hours by day of week. Add multiple per day if needed.
          </p>
          {weeklyHours.length === 0 ? (
            <p className="rounded-md border border-dashed py-3 text-center text-xs text-muted-foreground">
              No weekly windows set.
            </p>
          ) : (
            <div className="space-y-1.5">
              {weeklyHours.map((block, i) => (
                <div
                  key={i}
                  className="flex flex-wrap items-center gap-2 rounded-md border p-2"
                >
                  <Select
                    value={String(block.day_of_week)}
                    onValueChange={(v) =>
                      updateWeeklyHour(i, { day_of_week: Number(v) })
                    }
                    disabled={!canEdit}
                  >
                    <SelectTrigger className="h-8 w-24">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {DAYS_OF_WEEK.map((d, idx) => (
                        <SelectItem key={idx} value={String(idx)}>
                          {d}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <Input
                    type="time"
                    value={block.start_time}
                    onChange={(e) =>
                      updateWeeklyHour(i, { start_time: e.target.value })
                    }
                    className="h-8 w-28"
                    disabled={!canEdit}
                  />
                  <span className="text-xs text-muted-foreground">to</span>
                  <Input
                    type="time"
                    value={block.end_time}
                    onChange={(e) =>
                      updateWeeklyHour(i, { end_time: e.target.value })
                    }
                    className="h-8 w-28"
                    disabled={!canEdit}
                  />
                  {canEdit && (
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      className="ml-auto h-7 w-7 text-destructive"
                      onClick={() => removeWeeklyHour(i)}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  )}
                </div>
              ))}
            </div>
          )}
        </section>

        <section className="space-y-2">
          <Label>Unavailable dates</Label>
          <p className="text-xs text-muted-foreground">
            Dates this volunteer cannot attend (vacation, conflicts, etc).
          </p>
          {canEdit && (
            <div className="flex flex-wrap items-end gap-2">
              <div className="space-y-1">
                <Label className="text-xs text-muted-foreground">From</Label>
                <Input
                  type="date"
                  value={rangeStart}
                  onChange={(e) => setRangeStart(e.target.value)}
                  className="h-8 w-40"
                />
              </div>
              <div className="space-y-1">
                <Label className="text-xs text-muted-foreground">
                  To <span className="text-muted-foreground">(optional)</span>
                </Label>
                <Input
                  type="date"
                  value={rangeEnd}
                  min={rangeStart || undefined}
                  onChange={(e) => setRangeEnd(e.target.value)}
                  className="h-8 w-40"
                />
              </div>
              <Button
                type="button"
                size="sm"
                variant="outline"
                disabled={!rangeValid}
                onClick={addUnavailableRange}
              >
                <Plus className="mr-1 h-3 w-3" />
                {rangeEnd && rangeEnd !== rangeStart ? "Add range" : "Add date"}
              </Button>
            </div>
          )}
          {unavailableDates.length > 0 ? (
            <div className="flex flex-wrap gap-1.5 pt-1">
              {unavailableDates.map((d) => (
                <span
                  key={d}
                  className="inline-flex items-center gap-1 rounded-full border bg-background px-2.5 py-1 text-xs"
                >
                  {d}
                  {canEdit && (
                    <button
                      type="button"
                      onClick={() => removeUnavailableDate(d)}
                      className="text-muted-foreground hover:text-foreground"
                    >
                      <X className="h-3 w-3" />
                    </button>
                  )}
                </span>
              ))}
            </div>
          ) : (
            <p className="text-xs text-muted-foreground">No dates blocked.</p>
          )}
        </section>
      </CardContent>
    </Card>
  );
}
