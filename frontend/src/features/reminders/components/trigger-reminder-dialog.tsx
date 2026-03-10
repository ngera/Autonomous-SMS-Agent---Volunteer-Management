import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
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
import { useTriggerReminder } from "../hooks/use-reminders";
import { useAppointmentTypes } from "@/features/appointment-types/hooks/use-appointment-types";

interface TriggerReminderDialogProps {
  open: boolean;
  onClose: () => void;
}

export function TriggerReminderDialog({
  open,
  onClose,
}: TriggerReminderDialogProps) {
  const [phone, setPhone] = useState("");
  const [typeId, setTypeId] = useState("");
  const trigger = useTriggerReminder();
  const types = useAppointmentTypes();

  function handleSubmit() {
    if (!phone || !typeId) return;
    trigger.mutate(
      { contact_phone: phone, appointment_type_id: typeId },
      {
        onSuccess: () => {
          setPhone("");
          setTypeId("");
          onClose();
        },
      }
    );
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        if (!o) onClose();
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Trigger Manual Reminder</DialogTitle>
        </DialogHeader>
        <div className="space-y-3">
          <div className="space-y-1">
            <Label className="text-xs">Customer Phone</Label>
            <Input
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              placeholder="+447..."
            />
          </div>
          <div className="space-y-1">
            <Label className="text-xs">Appointment Type</Label>
            <Select value={typeId} onValueChange={(v) => setTypeId(v ?? "")}>
              <SelectTrigger>
                <SelectValue placeholder="Select type" />
              </SelectTrigger>
              <SelectContent>
                {types.data
                  ?.filter((t) => t.is_active)
                  .map((t) => (
                    <SelectItem key={t.id} value={t.id}>
                      {t.name}
                    </SelectItem>
                  ))}
              </SelectContent>
            </Select>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={!phone || !typeId || trigger.isPending}
          >
            {trigger.isPending ? "Triggering..." : "Trigger"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
