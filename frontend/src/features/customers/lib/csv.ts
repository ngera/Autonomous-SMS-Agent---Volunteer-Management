import type { CustomerResponse, CustomerWithTenant } from "@/types/api";

const CSV_HEADERS = [
  "phone",
  "name",
  "email",
  "sex",
  "status",
  "consent",
  "background_check_required",
  "all_services_enabled",
  "services",
  "availability",
  "weekly_hours",
  "unavailable_dates",
  "hours",
  "reminder_preference_days",
  "created_at",
] as const;

const DOW_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function escapeField(value: unknown): string {
  if (value === null || value === undefined) return "";
  const str = String(value);
  if (/[",\r\n]/.test(str)) {
    return `"${str.replace(/"/g, '""')}"`;
  }
  return str;
}

function trimTime(t: string | null | undefined): string {
  if (!t) return "";
  return t.length >= 5 ? t.slice(0, 5) : t;
}

function formatHours(minutes: number | undefined): string {
  if (!minutes || minutes <= 0) return "0";
  return Math.round(minutes / 60).toString();
}

interface ToCsvOptions {
  typeMap: Record<string, string>;
  includeTenant?: boolean;
}

export function customersToCsv(
  rows: (CustomerResponse | CustomerWithTenant)[],
  { typeMap, includeTenant = false }: ToCsvOptions
): string {
  const headers = includeTenant
    ? ["tenant", ...CSV_HEADERS]
    : [...CSV_HEADERS];

  const lines = [headers.join(",")];

  for (const c of rows) {
    const services = c.all_services_enabled
      ? "ALL"
      : (c.preferred_appointment_type_ids ?? [])
          .map((id) => typeMap[id] ?? id)
          .join("; ");

    const availability = (c.availability ?? []).join("; ");

    const weeklyHours = (c.weekly_hours ?? [])
      .map(
        (b) =>
          `${DOW_NAMES[b.day_of_week] ?? `D${b.day_of_week}`} ${trimTime(
            b.start_time
          )}-${trimTime(b.end_time)}`
      )
      .join("; ");

    const unavailable = (c.unavailable_dates ?? []).join("; ");

    const fields: string[] = [];
    if (includeTenant) {
      fields.push(escapeField((c as CustomerWithTenant).tenant_name ?? ""));
    }
    fields.push(
      escapeField(c.phone),
      escapeField(c.name ?? ""),
      escapeField(c.email ?? ""),
      escapeField(c.sex ?? ""),
      escapeField(c.status ?? ""),
      escapeField(c.consent_status ?? ""),
      escapeField(c.background_check_required ? "yes" : "no"),
      escapeField(c.all_services_enabled ? "yes" : "no"),
      escapeField(services),
      escapeField(availability),
      escapeField(weeklyHours),
      escapeField(unavailable),
      escapeField(formatHours(c.total_minutes)),
      escapeField(c.reminder_preference_days),
      escapeField(c.created_at)
    );
    lines.push(fields.join(","));
  }

  return lines.join("\r\n");
}

export function downloadCsv(filename: string, csv: string): void {
  const bom = "﻿";
  const blob = new Blob([bom + csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}
