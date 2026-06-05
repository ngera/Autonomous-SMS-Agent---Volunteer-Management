import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Pencil, Plus, Trash2, X } from "lucide-react";
import { DataTable, type Column } from "@/components/shared/data-table";
import { MapsLink } from "@/components/shared/maps-link";
import { ServiceCategoryPicker } from "@/components/shared/service-category-picker";
import { useAppointmentTypes } from "@/features/appointment-types/hooks/use-appointment-types";
import {
  useSpecificDateSlots,
  useCreateSpecificDateSlot,
  useUpdateSpecificDateSlot,
  useDeleteSpecificDateSlot,
} from "../hooks/use-availability";
import type { SpecificDateSlotResponse, ServiceSlotConfig } from "@/types/api";

interface Props {
  canEdit: boolean;
  /** When set, find this slot once it's loaded and open it in edit mode. */
  editSlotId?: string | null;
  /** Called once the editSlotId has been consumed so the URL can be cleared. */
  onConsumeEditSlot?: () => void;
}

const EMPTY_FORM = {
  date: "",
  label: "",
  location: "",
  description: "",
  start: "09:00",
  end: "17:00",
  buffer: 0,
  config: [] as ServiceSlotConfig[],
  allowRosterSharing: true,
};

function trimTime(t: string | null | undefined): string {
  if (!t) return "";
  return t.length >= 5 ? t.slice(0, 5) : t;
}

function errDetail(err: unknown): unknown {
  return (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
}

export function SpecificDateSlotsPanel({
  canEdit,
  editSlotId,
  onConsumeEditSlot,
}: Props) {
  const { data: slots, isLoading } = useSpecificDateSlots();
  const createSlot = useCreateSpecificDateSlot();
  const updateSlot = useUpdateSpecificDateSlot();
  const deleteSlot = useDeleteSpecificDateSlot();
  const { data: appointmentTypes } = useAppointmentTypes();
  const activeTypes = (appointmentTypes ?? []).filter((t) => t.is_active);

  const [editingId, setEditingId] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [formDate, setFormDate] = useState(EMPTY_FORM.date);
  const [formLabel, setFormLabel] = useState(EMPTY_FORM.label);
  const [formLocation, setFormLocation] = useState(EMPTY_FORM.location);
  const [formDescription, setFormDescription] = useState(EMPTY_FORM.description);
  const [formStart, setFormStart] = useState(EMPTY_FORM.start);
  const [formEnd, setFormEnd] = useState(EMPTY_FORM.end);
  const [formBuffer, setFormBuffer] = useState(EMPTY_FORM.buffer);
  const [formConfig, setFormConfig] = useState<ServiceSlotConfig[]>(EMPTY_FORM.config);
  const [formAllowRosterSharing, setFormAllowRosterSharing] = useState(EMPTY_FORM.allowRosterSharing);

  const showForm = creating || editingId !== null;
  const isPending = createSlot.isPending || updateSlot.isPending;

  // First-pass delete asks for a simple confirm. If the backend
  // responds 409 because volunteers are booked, surface the count
  // and ask a second confirm — then retry with force=true which
  // cancels the bookings and deletes the event.
  function handleDelete(s: SpecificDateSlotResponse) {
    if (!confirm(`Delete event "${s.label || s.date}"?`)) return;
    deleteSlot.mutate(
      { id: s.id },
      {
        onError: (err) => {
          const detail = errDetail(err) as
            | {
                code?: string;
                message?: string;
                booking_count?: number;
              }
            | undefined;
          if (detail?.code !== "bookings_attached") {
            alert(detail?.message || "Failed to delete event.");
            return;
          }
          const count = detail.booking_count ?? 0;
          const msg =
            detail.message ||
            `${count} volunteer${count === 1 ? "" : "s"} booked. Cancel them and delete anyway?`;
          if (!confirm(msg)) return;
          deleteSlot.mutate(
            { id: s.id, force: true },
            {
              onError: (err2) => {
                const d2 = errDetail(err2) as
                  | { message?: string }
                  | undefined;
                alert(d2?.message || "Failed to delete event.");
              },
            },
          );
        },
      },
    );
  }

  function resetForm() {
    setFormDate(EMPTY_FORM.date);
    setFormLabel(EMPTY_FORM.label);
    setFormLocation(EMPTY_FORM.location);
    setFormDescription(EMPTY_FORM.description);
    setFormStart(EMPTY_FORM.start);
    setFormEnd(EMPTY_FORM.end);
    setFormBuffer(EMPTY_FORM.buffer);
    setFormConfig(EMPTY_FORM.config);
    setFormAllowRosterSharing(EMPTY_FORM.allowRosterSharing);
  }

  function closeForm() {
    setCreating(false);
    setEditingId(null);
    resetForm();
  }

  function startCreate() {
    resetForm();
    setEditingId(null);
    setCreating(true);
  }

  function startEdit(s: SpecificDateSlotResponse) {
    setCreating(false);
    setEditingId(s.id);
    setFormDate(s.date);
    setFormLabel(s.label ?? "");
    setFormLocation(s.location ?? "");
    setFormDescription(s.description ?? "");
    setFormStart(trimTime(s.start_time));
    setFormEnd(trimTime(s.end_time));
    setFormBuffer(s.buffer_minutes ?? 0);
    setFormConfig(
      (s.service_config ?? []).map((c) => ({
        appointment_type_id: c.appointment_type_id,
        min_required: c.min_required,
        max_allowed: c.max_allowed,
      }))
    );
    setFormAllowRosterSharing(s.allow_roster_sharing ?? true);
  }

  // Honour the ?edit_slot=<id> deep link from the event roster page: once the
  // slot list arrives, find the requested row and open it in edit mode, then
  // tell the parent to clear the URL param so reloads stay idempotent.
  useEffect(() => {
    if (!editSlotId || !slots) return;
    const target = slots.find((s) => s.id === editSlotId);
    if (target) {
      startEdit(target);
    }
    onConsumeEditSlot?.();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [editSlotId, slots]);

  function toggleType(typeId: string) {
    const existing = formConfig.find((c) => c.appointment_type_id === typeId);
    if (existing) {
      setFormConfig(formConfig.filter((c) => c.appointment_type_id !== typeId));
    } else {
      setFormConfig([
        ...formConfig,
        { appointment_type_id: typeId, min_required: 1, max_allowed: 1 },
      ]);
    }
  }

  function updateConfigField(
    typeId: string,
    field: "min_required" | "max_allowed",
    value: number
  ) {
    setFormConfig(
      formConfig.map((c) => {
        if (c.appointment_type_id !== typeId) return c;
        const next = { ...c, [field]: value };
        if (next.max_allowed < next.min_required) {
          next.max_allowed = next.min_required;
        }
        return next;
      })
    );
  }

  function getTypeName(id: string) {
    return activeTypes.find((t) => t.id === id)?.name ?? id.slice(0, 8);
  }

  function handleSave() {
    if (!formDate || !formStart || !formEnd) return;
    const body = {
      date: formDate,
      label: formLabel || undefined,
      location: formLocation.trim() || undefined,
      description: formDescription.trim() || undefined,
      start_time: formStart,
      end_time: formEnd,
      buffer_minutes: formBuffer,
      service_config: formConfig.length > 0 ? formConfig : null,
      allow_roster_sharing: formAllowRosterSharing,
    };
    const onSuccess = () => closeForm();
    const showError = (err: unknown) => {
      const detail = errDetail(err) ?? (err as Error)?.message ?? "Failed to save event";
      alert(`Could not save event: ${typeof detail === "string" ? detail : JSON.stringify(detail)}`);
    };

    function submit(force: boolean) {
      if (editingId) {
        updateSlot.mutate(
          { id: editingId, body, force },
          { onSuccess, onError: handleError }
        );
      } else {
        createSlot.mutate(
          { body, force },
          { onSuccess, onError: handleError }
        );
      }
    }

    function handleError(err: unknown) {
      const detail = errDetail(err);
      if (
        detail &&
        typeof detail === "object" &&
        (detail as { code?: string }).code === "blocked_date_conflict"
      ) {
        const ranges = (
          (detail as { blocked_dates?: Array<{ date_from: string; date_to: string; reason?: string | null }> })
            .blocked_dates ?? []
        )
          .map(
            (b) =>
              `${b.date_from}${b.date_from === b.date_to ? "" : ` – ${b.date_to}`}${
                b.reason ? ` (${b.reason})` : ""
              }`
          )
          .join(", ");
        const ok = window.confirm(
          `${(detail as { message: string }).message}\n\nBlocked range: ${ranges}\n\nSchedule the event anyway?`
        );
        if (ok) submit(true);
        return;
      }
      showError(err);
    }

    submit(false);
  }

  const columns: Column<SpecificDateSlotResponse>[] = [
    { key: "date", header: "Date", render: (s) => s.date },
    { key: "label", header: "Label", render: (s) => s.label || "—" },
    {
      key: "location",
      header: "Address",
      render: (s) =>
        s.location ? (
          <span className="inline-flex items-center gap-1.5">
            <span>{s.location}</span>
            <MapsLink address={s.location} />
          </span>
        ) : (
          "—"
        ),
    },
    {
      key: "time",
      header: "Time",
      render: (s) => `${trimTime(s.start_time)} – ${trimTime(s.end_time)}`,
    },
    {
      key: "services",
      header: "Services",
      render: (s) => {
        if (!s.service_config?.length) {
          return <span className="text-xs text-muted-foreground">All services</span>;
        }
        return (
          <div className="flex flex-wrap gap-1">
            {s.service_config.map((c) => (
              <Badge
                key={c.appointment_type_id}
                variant="secondary"
                className="text-xs"
              >
                {getTypeName(c.appointment_type_id)} ({c.min_required}-{c.max_allowed})
              </Badge>
            ))}
          </div>
        );
      },
    },
    ...(canEdit
      ? [
          {
            key: "actions" as const,
            header: "",
            render: (s: SpecificDateSlotResponse) => (
              <div className="flex gap-1">
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7"
                  onClick={(e) => {
                    e.stopPropagation();
                    startEdit(s);
                  }}
                >
                  <Pencil className="h-3.5 w-3.5" />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7 text-destructive"
                  onClick={(e) => {
                    e.stopPropagation();
                    handleDelete(s);
                  }}
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </Button>
              </div>
            ),
          },
        ]
      : []),
  ];

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>Events & Special Dates</CardTitle>
        {canEdit && !showForm && (
          <Button size="sm" onClick={startCreate}>
            <Plus className="h-4 w-4 mr-1" /> Add Event
          </Button>
        )}
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-xs text-muted-foreground">
          One-off events or special availability. Configure which services are
          needed with min/max participants.
        </p>

        {showForm && (
          <div className="rounded-md border p-4 space-y-3">
            <div className="flex items-center justify-between">
              <p className="text-sm font-medium">
                {editingId ? "Edit event" : "New event"}
              </p>
            </div>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <div className="space-y-1">
                <Label className="text-xs">Date *</Label>
                <Input
                  type="date"
                  value={formDate}
                  onChange={(e) => setFormDate(e.target.value)}
                  className="h-8"
                />
              </div>
              <div className="space-y-1">
                <Label className="text-xs">Label</Label>
                <Input
                  value={formLabel}
                  onChange={(e) => setFormLabel(e.target.value)}
                  placeholder="e.g. Food Drive"
                  className="h-8"
                />
              </div>
              <div className="space-y-1 col-span-2">
                <Label className="text-xs">Address</Label>
                <Input
                  value={formLocation}
                  onChange={(e) => setFormLocation(e.target.value)}
                  placeholder="e.g. 123 Main St, Springfield, IL 62701"
                  className="h-8"
                />
              </div>
              <div className="space-y-1 col-span-2">
                <Label className="text-xs">Description</Label>
                <Textarea
                  rows={3}
                  value={formDescription}
                  onChange={(e) => setFormDescription(e.target.value)}
                  placeholder="What's this event about? Volunteers will see this when they ask the AI for event details."
                />
              </div>
              <div className="space-y-1">
                <Label className="text-xs">Start</Label>
                <Input
                  type="time"
                  value={formStart}
                  onChange={(e) => setFormStart(e.target.value)}
                  className="h-8"
                />
              </div>
              <div className="space-y-1">
                <Label className="text-xs">End</Label>
                <Input
                  type="time"
                  value={formEnd}
                  onChange={(e) => setFormEnd(e.target.value)}
                  className="h-8"
                />
              </div>
              <div className="space-y-1">
                <Label className="text-xs">Buffer (min)</Label>
                <Input
                  type="number"
                  value={formBuffer}
                  onChange={(e) => setFormBuffer(Number(e.target.value))}
                  className="h-8"
                  min={0}
                />
              </div>
            </div>

            <label className="flex items-center gap-2 text-xs text-muted-foreground">
              <input
                type="checkbox"
                checked={formAllowRosterSharing}
                onChange={(e) => setFormAllowRosterSharing(e.target.checked)}
                className="h-3.5 w-3.5"
              />
              Allow volunteers to see who else is signed up for this event
            </label>

            <div className="space-y-1.5">
              <Label className="text-xs text-muted-foreground">
                Services needed:
              </Label>
              {formConfig.length === 0 && (
                <p className="text-xs text-muted-foreground italic">
                  All services (min 1, max 1) — add specific services below to override.
                </p>
              )}
              {formConfig.length > 0 && (
                <div className="flex flex-wrap gap-2">
                  {formConfig.map((cfg) => (
                    <div
                      key={cfg.appointment_type_id}
                      className="flex items-center gap-1.5 rounded-md border bg-background px-2 py-1"
                    >
                      <span className="text-xs font-medium">
                        {getTypeName(cfg.appointment_type_id)}
                      </span>
                      <span className="text-xs text-muted-foreground">min</span>
                      <Input
                        type="number"
                        value={cfg.min_required}
                        onChange={(e) =>
                          updateConfigField(
                            cfg.appointment_type_id,
                            "min_required",
                            Math.max(1, Number(e.target.value))
                          )
                        }
                        className="w-12 h-6 text-xs text-center p-0"
                        min={1}
                      />
                      <span className="text-xs text-muted-foreground">max</span>
                      <Input
                        type="number"
                        value={cfg.max_allowed}
                        onChange={(e) =>
                          updateConfigField(
                            cfg.appointment_type_id,
                            "max_allowed",
                            Math.max(cfg.min_required, Number(e.target.value))
                          )
                        }
                        className="w-12 h-6 text-xs text-center p-0"
                        min={cfg.min_required}
                      />
                      <X
                        className="h-3 w-3 cursor-pointer text-muted-foreground hover:text-foreground"
                        onClick={() => toggleType(cfg.appointment_type_id)}
                      />
                    </div>
                  ))}
                </div>
              )}
              {activeTypes.length > 0 && (
                <ServiceCategoryPicker
                  activeTypes={activeTypes}
                  excludeIds={formConfig.map((c) => c.appointment_type_id)}
                  onAdd={(typeId) => toggleType(typeId)}
                  size="sm"
                />
              )}
            </div>

            <div className="flex gap-2">
              <Button
                size="sm"
                onClick={handleSave}
                disabled={!formDate || isPending}
              >
                {isPending
                  ? editingId
                    ? "Saving..."
                    : "Creating..."
                  : editingId
                    ? "Save"
                    : "Create"}
              </Button>
              <Button size="sm" variant="outline" onClick={closeForm}>
                Cancel
              </Button>
            </div>
          </div>
        )}

        <DataTable
          columns={columns}
          data={slots ?? []}
          isLoading={isLoading}
          emptyMessage="No events or special dates configured."
        />
      </CardContent>
    </Card>
  );
}
