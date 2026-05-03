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
import { Switch } from "@/components/ui/switch";
import { ContactSex } from "@/types/enums";
import type { CustomerResponse } from "@/types/api";

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
  sex?: ContactSex;
  background_check_required?: boolean;
  reminder_preference_days?: number;
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
  const [sex, setSex] = useState<ContactSex | undefined>(undefined);
  const [reminderDays, setReminderDays] = useState(7);
  const [backgroundCheckRequired, setBackgroundCheckRequired] = useState(false);

  useEffect(() => {
    if (editItem) {
      setPhone(editItem.phone);
      setName(editItem.name ?? "");
      setEmail(editItem.email ?? "");
      setSex(editItem.sex ?? undefined);
      setBackgroundCheckRequired(editItem.background_check_required ?? false);
      setReminderDays(editItem.reminder_preference_days);
    } else {
      setPhone("");
      setName("");
      setEmail("");
      setSex(undefined);
      setBackgroundCheckRequired(false);
      setReminderDays(7);
    }
  }, [editItem, open]);

  const canSave = !!phone && !!name && !isLoading;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="w-[95vw] sm:w-[50vw] max-w-none max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>
            {editItem ? "Edit Volunteer" : "New Volunteer"}
          </DialogTitle>
          {!editItem && (
            <p className="text-xs text-muted-foreground">
              Set up basic info here. Services, availability, weekly hours, and
              unavailable dates can be configured on the volunteer's detail page.
            </p>
          )}
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
              onValueChange={(v) => setSex((v || undefined) as ContactSex | undefined)}
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
              <Label className="text-sm font-medium">Background Check Required</Label>
              <p className="text-xs text-muted-foreground">
                When enabled, this volunteer cannot book any appointments until cleared.
              </p>
            </div>
            <Switch
              checked={backgroundCheckRequired}
              onCheckedChange={setBackgroundCheckRequired}
            />
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
                background_check_required: backgroundCheckRequired,
                reminder_preference_days: reminderDays,
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
