import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Plus, Trash2, X } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { DataTable, type Column } from "@/components/shared/data-table";
import { useAppointmentTypes } from "@/features/appointment-types/hooks/use-appointment-types";
import {
  useSpecificDateSlots,
  useCreateSpecificDateSlot,
  useDeleteSpecificDateSlot,
} from "../hooks/use-availability";
import type { SpecificDateSlotResponse, ServiceSlotConfig } from "@/types/api";

interface Props {
  canEdit: boolean;
}

export function SpecificDateSlotsPanel({ canEdit }: Props) {
  const { data: slots, isLoading } = useSpecificDateSlots();
  const createSlot = useCreateSpecificDateSlot();
  const deleteSlot = useDeleteSpecificDateSlot();
  const { data: appointmentTypes } = useAppointmentTypes();
  const activeTypes = (appointmentTypes ?? []).filter((t) => t.is_active);

  const [showForm, setShowForm] = useState(false);
  const [formDate, setFormDate] = useState("");
  const [formLabel, setFormLabel] = useState("");
  const [formStart, setFormStart] = useState("09:00");
  const [formEnd, setFormEnd] = useState("17:00");
  const [formBuffer, setFormBuffer] = useState(0);
  const [formConfig, setFormConfig] = useState<ServiceSlotConfig[]>([]);

  function toggleType(typeId: string) {
    const existing = formConfig.find((c) => c.appointment_type_id === typeId);
    if (existing) {
      setFormConfig(formConfig.filter((c) => c.appointment_type_id !== typeId));
    } else {
      setFormConfig([...formConfig, { appointment_type_id: typeId, min_required: 1, max_allowed: 1 }]);
    }
  }

  function updateField(typeId: string, field: "min_required" | "max_allowed", value: number) {
    setFormConfig(formConfig.map((c) => {
      if (c.appointment_type_id !== typeId) return c;
      const next = { ...c, [field]: value };
      if (next.max_allowed < next.min_required) {
        next.max_allowed = next.min_required;
      }
      return next;
    }));
  }

  function getTypeName(id: string) {
    return activeTypes.find((t) => t.id === id)?.name ?? id.slice(0, 8);
  }

  function handleCreate() {
    if (!formDate || !formStart || !formEnd) return;
    createSlot.mutate(
      {
        date: formDate,
        label: formLabel || undefined,
        start_time: formStart,
        end_time: formEnd,
        buffer_minutes: formBuffer,
        service_config: formConfig.length > 0 ? formConfig : undefined,
      },
      {
        onSuccess: () => {
          setShowForm(false);
          setFormDate("");
          setFormLabel("");
          setFormStart("09:00");
          setFormEnd("17:00");
          setFormBuffer(0);
          setFormConfig([]);
        },
      }
    );
  }

  const columns: Column<SpecificDateSlotResponse>[] = [
    { key: "date", header: "Date", render: (s) => s.date },
    { key: "label", header: "Label", render: (s) => s.label || "—" },
    { key: "time", header: "Time", render: (s) => `${s.start_time} – ${s.end_time}` },
    {
      key: "services",
      header: "Services",
      render: (s) => {
        if (!s.service_config?.length) return <span className="text-xs text-muted-foreground">All services</span>;
        return (
          <div className="flex flex-wrap gap-1">
            {s.service_config.map((c) => (
              <Badge key={c.appointment_type_id} variant="secondary" className="text-xs">
                {getTypeName(c.appointment_type_id)} ({c.min_required}-{c.max_allowed})
              </Badge>
            ))}
          </div>
        );
      },
    },
    ...(canEdit
      ? [{
          key: "actions" as const,
          header: "",
          render: (s: SpecificDateSlotResponse) => (
            <Button variant="ghost" size="icon" className="h-7 w-7 text-destructive" onClick={(e) => { e.stopPropagation(); deleteSlot.mutate(s.id); }}>
              <Trash2 className="h-3.5 w-3.5" />
            </Button>
          ),
        }]
      : []),
  ];

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>Events & Special Dates</CardTitle>
        {canEdit && (
          <Button size="sm" onClick={() => setShowForm(!showForm)}>
            <Plus className="h-4 w-4 mr-1" /> Add Event
          </Button>
        )}
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-xs text-muted-foreground">
          One-off events or special availability. Configure which services are needed with min/max participants.
        </p>

        {showForm && (
          <div className="rounded-md border p-4 space-y-3">
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <div className="space-y-1">
                <Label className="text-xs">Date *</Label>
                <Input type="date" value={formDate} onChange={(e) => setFormDate(e.target.value)} className="h-8" />
              </div>
              <div className="space-y-1">
                <Label className="text-xs">Label</Label>
                <Input value={formLabel} onChange={(e) => setFormLabel(e.target.value)} placeholder="e.g. Food Drive" className="h-8" />
              </div>
              <div className="space-y-1">
                <Label className="text-xs">Start</Label>
                <Input type="time" value={formStart} onChange={(e) => setFormStart(e.target.value)} className="h-8" />
              </div>
              <div className="space-y-1">
                <Label className="text-xs">End</Label>
                <Input type="time" value={formEnd} onChange={(e) => setFormEnd(e.target.value)} className="h-8" />
              </div>
              <div className="space-y-1">
                <Label className="text-xs">Buffer (min)</Label>
                <Input type="number" value={formBuffer} onChange={(e) => setFormBuffer(Number(e.target.value))} className="h-8" min={0} />
              </div>
            </div>

            {/* Services config */}
            <div className="space-y-1.5">
              <div className="flex items-center gap-2">
                <Label className="text-xs text-muted-foreground">Services needed:</Label>
                {formConfig.length === 0 && <span className="text-xs text-muted-foreground italic">All services (min 1, max 1)</span>}
                {activeTypes.length > 0 && (
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="outline" size="sm" className="h-6 text-xs px-2">
                        <Plus className="h-3 w-3 mr-1" /> {formConfig.length === 0 ? "Configure..." : "Add"}
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="start" className="w-56">
                      {activeTypes.map((type) => (
                        <DropdownMenuCheckboxItem key={type.id} checked={formConfig.some((c) => c.appointment_type_id === type.id)} onCheckedChange={() => toggleType(type.id)}>
                          {type.name} ({type.duration_minutes}min)
                        </DropdownMenuCheckboxItem>
                      ))}
                    </DropdownMenuContent>
                  </DropdownMenu>
                )}
              </div>
              {formConfig.length > 0 && (
                <div className="flex flex-wrap gap-2">
                  {formConfig.map((cfg) => (
                    <div key={cfg.appointment_type_id} className="flex items-center gap-1.5 rounded-md border bg-background px-2 py-1">
                      <span className="text-xs font-medium">{getTypeName(cfg.appointment_type_id)}</span>
                      <span className="text-xs text-muted-foreground">min</span>
                      <Input type="number" value={cfg.min_required} onChange={(e) => updateField(cfg.appointment_type_id, "min_required", Math.max(1, Number(e.target.value)))} className="w-12 h-6 text-xs text-center p-0" min={1} />
                      <span className="text-xs text-muted-foreground">max</span>
                      <Input type="number" value={cfg.max_allowed} onChange={(e) => updateField(cfg.appointment_type_id, "max_allowed", Math.max(cfg.min_required, Number(e.target.value)))} className="w-12 h-6 text-xs text-center p-0" min={cfg.min_required} />
                      <X className="h-3 w-3 cursor-pointer text-muted-foreground hover:text-foreground" onClick={() => toggleType(cfg.appointment_type_id)} />
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="flex gap-2">
              <Button size="sm" onClick={handleCreate} disabled={!formDate || createSlot.isPending}>
                {createSlot.isPending ? "Creating..." : "Create"}
              </Button>
              <Button size="sm" variant="outline" onClick={() => setShowForm(false)}>Cancel</Button>
            </div>
          </div>
        )}

        <DataTable columns={columns} data={slots ?? []} isLoading={isLoading} emptyMessage="No events or special dates configured." />
      </CardContent>
    </Card>
  );
}
