import type {
  AppointmentTypeCreate,
  AppointmentTypeResponse,
} from "@/types/api";

const CSV_HEADERS = [
  "name",
  "category",
  "duration_minutes",
  "price",
  "description",
  "is_active",
] as const;

type CsvHeader = (typeof CSV_HEADERS)[number];

function escapeField(value: unknown): string {
  if (value === null || value === undefined) return "";
  const str = String(value);
  if (/[",\r\n]/.test(str)) {
    return `"${str.replace(/"/g, '""')}"`;
  }
  return str;
}

export function appointmentTypesToCsv(types: AppointmentTypeResponse[]): string {
  const rows = [CSV_HEADERS.join(",")];
  for (const t of types) {
    rows.push(
      [
        escapeField(t.name),
        escapeField(t.category ?? ""),
        escapeField(t.duration_minutes),
        escapeField(t.price),
        escapeField(t.description ?? ""),
        escapeField(t.is_active ? "true" : "false"),
      ].join(",")
    );
  }
  return rows.join("\r\n");
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

function parseCsvLine(line: string): string[] {
  const fields: string[] = [];
  let current = "";
  let inQuotes = false;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (inQuotes) {
      if (ch === '"') {
        if (line[i + 1] === '"') {
          current += '"';
          i++;
        } else {
          inQuotes = false;
        }
      } else {
        current += ch;
      }
    } else if (ch === '"') {
      inQuotes = true;
    } else if (ch === ",") {
      fields.push(current);
      current = "";
    } else {
      current += ch;
    }
  }
  fields.push(current);
  return fields;
}

function splitCsvRecords(text: string): string[] {
  // Split on newlines that are NOT inside quoted fields.
  const records: string[] = [];
  let current = "";
  let inQuotes = false;
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (ch === '"') {
      inQuotes = !inQuotes;
      current += ch;
      continue;
    }
    if (!inQuotes && (ch === "\n" || ch === "\r")) {
      if (ch === "\r" && text[i + 1] === "\n") i++;
      if (current.length > 0) records.push(current);
      current = "";
      continue;
    }
    current += ch;
  }
  if (current.length > 0) records.push(current);
  return records;
}

export interface CsvParseError {
  row: number;
  message: string;
}

export interface CsvParseResult {
  rows: AppointmentTypeCreate[];
  errors: CsvParseError[];
}

function parseBoolean(value: string): boolean {
  const v = value.trim().toLowerCase();
  if (v === "" || v === "true" || v === "yes" || v === "1" || v === "y") {
    return true;
  }
  return false;
}

export function parseAppointmentTypesCsv(text: string): CsvParseResult {
  // Strip BOM
  const cleaned = text.replace(/^﻿/, "");
  const records = splitCsvRecords(cleaned);
  const result: CsvParseResult = { rows: [], errors: [] };
  if (records.length === 0) {
    result.errors.push({ row: 0, message: "File is empty" });
    return result;
  }

  const headerCells = parseCsvLine(records[0]).map((h) =>
    h.trim().toLowerCase()
  );
  const headerIndex: Partial<Record<CsvHeader, number>> = {};
  for (const h of CSV_HEADERS) {
    const idx = headerCells.indexOf(h);
    if (idx >= 0) headerIndex[h] = idx;
  }
  for (const required of ["name", "category", "duration_minutes", "price"] as const) {
    if (headerIndex[required] === undefined) {
      result.errors.push({
        row: 1,
        message: `Missing required column: ${required}`,
      });
    }
  }
  if (result.errors.length > 0) return result;

  for (let i = 1; i < records.length; i++) {
    const cells = parseCsvLine(records[i]);
    if (cells.every((c) => c.trim() === "")) continue;

    const get = (key: CsvHeader): string => {
      const idx = headerIndex[key];
      if (idx === undefined) return "";
      return (cells[idx] ?? "").trim();
    };

    const name = get("name");
    const durationStr = get("duration_minutes");
    const priceStr = get("price");

    if (!name) {
      result.errors.push({ row: i + 1, message: "name is required" });
      continue;
    }
    const duration = Number(durationStr);
    if (!Number.isFinite(duration) || duration <= 0) {
      result.errors.push({
        row: i + 1,
        message: `Invalid duration_minutes: "${durationStr}"`,
      });
      continue;
    }
    const price = Number(priceStr);
    if (!Number.isFinite(price) || price < 0) {
      result.errors.push({
        row: i + 1,
        message: `Invalid price: "${priceStr}"`,
      });
      continue;
    }

    const category = get("category");
    if (!category) {
      result.errors.push({ row: i + 1, message: "category is required" });
      continue;
    }
    const description = get("description");
    const isActiveStr = get("is_active");

    result.rows.push({
      name,
      category,
      duration_minutes: Math.trunc(duration),
      price,
      description: description || undefined,
      is_active: isActiveStr === "" ? true : parseBoolean(isActiveStr),
    });
  }

  return result;
}
