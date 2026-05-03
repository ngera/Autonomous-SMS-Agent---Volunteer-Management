import type { WeeklySlotStatus } from "@/types/api";

export interface AggregatedEvent {
  key: string;
  date: string;
  day_name: string;
  window_time: string;
  display_name: string;
  location: string | null;
  source: "recurring" | "one_time";
  booked: number;
  max_allowed: number;
  min_required: number;
  any_needs_more: boolean;
  last_reminder_sent: string | null;
  last_announcement_sent: string | null;
}

function pickLatest(a: string | null, b: string | null): string | null {
  if (!a) return b;
  if (!b) return a;
  return a > b ? a : b;
}

/**
 * Group per-(window, service) rows into per-event rows by aggregating across services
 * within the same window. Falls back to the first service name when window_label is null.
 */
export function aggregateBySchedule(
  rows: WeeklySlotStatus[]
): AggregatedEvent[] {
  const groups = new Map<string, AggregatedEvent>();

  for (const r of rows) {
    const labelKey = r.window_label ?? `__svc:${r.service_name}`;
    const key = `${r.date}|${r.window_time}|${labelKey}|${r.source}`;
    const existing = groups.get(key);
    if (existing) {
      existing.booked += r.booked;
      existing.max_allowed += r.max_allowed;
      existing.min_required += r.min_required;
      existing.any_needs_more = existing.any_needs_more || r.status === "needs_more";
      existing.last_reminder_sent = pickLatest(
        existing.last_reminder_sent,
        r.last_reminder_sent
      );
      existing.last_announcement_sent = pickLatest(
        existing.last_announcement_sent,
        r.last_announcement_sent
      );
    } else {
      groups.set(key, {
        key,
        date: r.date,
        day_name: r.day_name,
        window_time: r.window_time,
        display_name: r.window_label ?? r.service_name,
        location: r.location,
        source: r.source,
        booked: r.booked,
        max_allowed: r.max_allowed,
        min_required: r.min_required,
        any_needs_more: r.status === "needs_more",
        last_reminder_sent: r.last_reminder_sent,
        last_announcement_sent: r.last_announcement_sent,
      });
    }
  }

  return Array.from(groups.values()).sort((a, b) => {
    if (a.date !== b.date) return a.date.localeCompare(b.date);
    return a.window_time.localeCompare(b.window_time);
  });
}

export function fillPercent(booked: number, max_allowed: number): number {
  if (max_allowed <= 0) return 0;
  return Math.min(100, Math.round((booked / max_allowed) * 100));
}

export function fillTone(percent: number): "green" | "amber" | "red" {
  if (percent >= 90) return "green";
  if (percent >= 50) return "amber";
  return "red";
}
