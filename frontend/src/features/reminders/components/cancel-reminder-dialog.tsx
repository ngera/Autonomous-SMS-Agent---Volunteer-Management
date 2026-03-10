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
import type { ReminderResponse } from "@/types/api";

interface CancelReminderDialogProps {
  reminder: ReminderResponse | null;
  onClose: () => void;
  onConfirm: (id: string, reason: string) => void;
  isPending: boolean;
}

export function CancelReminderDialog({
  reminder,
  onClose,
  onConfirm,
  isPending,
}: CancelReminderDialogProps) {
  const [reason, setReason] = useState("");

  function handleSubmit() {
    if (!reminder || !reason.trim()) return;
    onConfirm(reminder.id, reason.trim());
  }

  return (
    <Dialog
      open={!!reminder}
      onOpenChange={(open) => {
        if (!open) {
          setReason("");
          onClose();
        }
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Cancel Reminder</DialogTitle>
        </DialogHeader>
        <div className="space-y-3">
          <p className="text-sm text-muted-foreground">
            Cancel reminder for {reminder?.contact_phone}?
          </p>
          <div className="space-y-1">
            <Label className="text-xs">Reason</Label>
            <Input
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="e.g. Customer called directly"
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Back
          </Button>
          <Button
            variant="destructive"
            onClick={handleSubmit}
            disabled={!reason.trim() || isPending}
          >
            {isPending ? "Cancelling..." : "Cancel Reminder"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
