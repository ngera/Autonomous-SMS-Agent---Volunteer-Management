import { useState, useEffect } from "react";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { X } from "lucide-react";
import { ContactSex } from "@/types/enums";
import type { CustomerResponse } from "@/types/api";
import { useQuery } from "@tanstack/react-query";
import { listAppointmentTypes } from "@/features/appointment-types/api";

const SEX_LABELS: Record<string, string> = {
  [ContactSex.MALE]: "Male",
  [ContactSex.FEMALE]: "Female",
  [ContactSex.NON_BINARY]: "Non-binary",
  [ContactSex.PREFER_NOT_TO_SAY]: "Prefer not to say",
};

export interface CustomerFormData {
  phone: string;
  name: string;
  email?: string;
  sex?: string | null;
  all_services_enabled?: boolean;
  reminder_preference_days?: number;
  preferred_appointment_type_ids?: string[];
}

interface CustomerFormProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  editItem?: CustomerResponse | null;
  onSubmit: (data: CustomerFormData) => void;
  isLoading: boolean;
}

export function CustomerForm({
  open,
  onOpenChange,
  editItem,
  onSubmit,
  isLoading,
}: CustomerFormProps) {
  const [phone, setPhone] = useState("");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [sex, setSex] = useState<string | undefined>(undefined);
  const [reminderDays, setReminderDays] = useState(7);
  const [allServicesEnabled, setAllServicesEnabled] = useState(false);
  const [selectedTypeIds, setSelectedTypeIds] = useState<string[]>([]);

  const { data: appointmentTypes } = useQuery({
    queryKey: ["appointment-types-for-form"],
    queryFn: listAppointmentTypes,
  });

  useEffect(() => {
    if (editItem) {
      setPhone(editItem.phone);
      setName(editItem.name ?? "");
      setEmail(editItem.email ?? "");
      setSex(editItem.sex ?? undefined);
      setAllServicesEnabled(editItem.all_services_enabled ?? false);
      setReminderDays(editItem.reminder_preference_days);
      setSelectedTypeIds(editItem.preferred_appointment_type_ids ?? []);
    } else {
      setPhone("");
      setName("");
      setEmail("");
      setSex(undefined);
      setAllServicesEnabled(false);
      setReminderDays(7);
      setSelectedTypeIds([]);
    }
  }, [editItem, open]);

  function toggleType(id: string) {
    setSelectedTypeIds((prev) =>
      prev.includes(id) ? prev.filter((t) => t !== id) : [...prev, id]
    );
  }

  const canSave = !!phone && !!name && !isLoading;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>
            {editItem ? "Edit Volunteer" : "New Volunteer"}
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-4 py-2">
          <div className="space-y-2">
            <Label>Phone *</Label>
            <Input
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              placeholder="+1..."
            />
          </div>
          <div className="space-y-2">
            <Label>Name *</Label>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Volunteer name"
            />
          </div>
          <div className="space-y-2">
            <Label>Email</Label>
            <Input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="customer@example.com"
            />
          </div>
          <div className="space-y-2">
            <Label>Sex</Label>
            <Select
              value={sex ?? ""}
              onValueChange={(v) => setSex(v || undefined)}
            >
              <SelectTrigger>
                <SelectValue placeholder="Select..." />
              </SelectTrigger>
              <SelectContent>
                {Object.entries(SEX_LABELS).map(([value, label]) => (
                  <SelectItem key={value} value={value}>
                    {label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label>Reminder Preference (days)</Label>
            <Input
              type="number"
              value={reminderDays}
              onChange={(e) => setReminderDays(Number(e.target.value))}
              min={1}
            />
          </div>
          <div className="flex items-center justify-between rounded-lg border p-3">
            <div>
              <Label className="text-sm font-medium">All Services</Label>
              <p className="text-xs text-muted-foreground">
                Allow this volunteer to book any active service
              </p>
            </div>
            <Switch
              checked={allServicesEnabled}
              onCheckedChange={setAllServicesEnabled}
            />
          </div>
          <div className={`space-y-2 ${allServicesEnabled ? "opacity-50 pointer-events-none" : ""}`}>
            <Label>Services this volunteer participates in</Label>
            <div className="flex flex-wrap gap-2">
              {(appointmentTypes ?? [])
                .filter((t) => t.is_active)
                .map((type) => {
                  const selected = selectedTypeIds.includes(type.id);
                  return (
                    <Badge
                      key={type.id}
                      variant={selected ? "default" : "outline"}
                      className="cursor-pointer select-none"
                      onClick={() => toggleType(type.id)}
                    >
                      {type.name}
                      {selected && <X className="ml-1 h-3 w-3" />}
                    </Badge>
                  );
                })}
            </div>
            {(!appointmentTypes ||
              appointmentTypes.filter((t) => t.is_active).length === 0) && (
              <p className="text-xs text-muted-foreground">
                No appointment types available
              </p>
            )}
          </div>
        </div>
        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={isLoading}
          >
            Cancel
          </Button>
          <Button
            onClick={() =>
              onSubmit({
                phone,
                name,
                email: email || undefined,
                sex: sex || undefined,
                all_services_enabled: allServicesEnabled,
                reminder_preference_days: reminderDays,
                preferred_appointment_type_ids: selectedTypeIds,
              })
            }
            disabled={!canSave}
          >
            {isLoading ? "Saving..." : "Save"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
