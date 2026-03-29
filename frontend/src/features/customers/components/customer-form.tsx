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
import { X } from "lucide-react";
import { ContactSex } from "@/types/enums";
import type { CustomerResponse } from "@/types/api";
import { useAppointmentTypes } from "@/features/appointment-types/hooks/use-appointment-types";

const SEX_LABELS: Record<string, string> = {
  [ContactSex.MALE]: "Male",
  [ContactSex.FEMALE]: "Female",
  [ContactSex.NON_BINARY]: "Non-binary",
  [ContactSex.PREFER_NOT_TO_SAY]: "Prefer not to say",
};

interface CustomerFormProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  editItem?: CustomerResponse | null;
  onSubmit: (data: {
    phone: string;
    name: string;
    email?: string;
    sex?: string | null;
    reminder_preference_days?: number;
    preferred_appointment_type_ids?: string[];
  }) => void;
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
  const [sex, setSex] = useState<string>("");
  const [reminderDays, setReminderDays] = useState(7);
  const [selectedTypeIds, setSelectedTypeIds] = useState<string[]>([]);

  const { data: appointmentTypes } = useAppointmentTypes();

  useEffect(() => {
    if (editItem) {
      setPhone(editItem.phone);
      setName(editItem.name ?? "");
      setEmail(editItem.email ?? "");
      setSex(editItem.sex ?? "");
      setReminderDays(editItem.reminder_preference_days);
      setSelectedTypeIds(editItem.preferred_appointment_type_ids ?? []);
    } else {
      setPhone("");
      setName("");
      setEmail("");
      setSex("");
      setReminderDays(7);
      setSelectedTypeIds([]);
    }
  }, [editItem, open]);

  function toggleType(id: string) {
    setSelectedTypeIds((prev) =>
      prev.includes(id) ? prev.filter((t) => t !== id) : [...prev, id]
    );
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>
            {editItem ? "Edit Customer" : "New Customer"}
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-4 py-2">
          <div className="space-y-2">
            <Label>Phone *</Label>
            <Input
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              placeholder="+1..."
              disabled={!!editItem}
            />
          </div>
          <div className="space-y-2">
            <Label>Name *</Label>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Customer name"
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
            <Select value={sex} onValueChange={setSex}>
              <SelectTrigger className="w-full min-w-0">
                <SelectValue placeholder="Select...">
                  {(val) => {
                    const v = val as string | null | undefined;
                    if (v == null || v === "") return "Select...";
                    return SEX_LABELS[v] ?? v;
                  }}
                </SelectValue>
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
          <div className="space-y-2">
            <Label>Preferred Appointment Types</Label>
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
            {(!appointmentTypes || appointmentTypes.filter((t) => t.is_active).length === 0) && (
              <p className="text-xs text-muted-foreground">No appointment types available</p>
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
                reminder_preference_days: reminderDays,
                preferred_appointment_type_ids: selectedTypeIds,
              })
            }
            disabled={!phone || !name || isLoading}
          >
            {isLoading ? "Saving..." : "Save"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
