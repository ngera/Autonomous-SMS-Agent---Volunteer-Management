import { useState, useEffect } from "react";
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
import type { ReminderResponse } from "@/types/api";

interface EditReminderDialogProps {
  reminder: ReminderResponse | null;
  onClose: () => void;
  onConfirm: (id: string, scheduledFor: string) => void;
  isPending: boolean;
}

export function EditReminderDialog({
  reminder,
  onClose,
  onConfirm,
  isPending,
}: EditReminderDialogProps) {
  const [scheduledFor, setScheduledFor] = useState("");

  useEffect(() => {
    if (reminder) {
      setScheduledFor(reminder.scheduled_for);
    }
  }, [reminder]);

  function handleSubmit() {
    if (!reminder || !scheduledFor) return;
    onConfirm(reminder.id, scheduledFor);
  }

  return (
    <Dialog
      open={!!reminder}
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Edit Reminder</DialogTitle>
        </DialogHeader>
        <div className="space-y-3">
          <p className="text-sm text-muted-foreground">
            Change scheduled date for {reminder?.contact_phone}.
          </p>
          <div className="space-y-1">
            <Label className="text-xs">Scheduled For</Label>
            <Input
              type="date"
              value={scheduledFor}
              onChange={(e) => setScheduledFor(e.target.value)}
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={!scheduledFor || isPending}
          >
            {isPending ? "Saving..." : "Save"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
