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
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { useManualSuspend } from "../hooks/use-suspensions";

interface ManualSuspendDialogProps {
  open: boolean;
  onClose: () => void;
}

export function ManualSuspendDialog({ open, onClose }: ManualSuspendDialogProps) {
  const [phone, setPhone] = useState("");
  const [reason, setReason] = useState("");
  const suspend = useManualSuspend();

  function handleSubmit() {
    if (!phone.trim() || !reason.trim()) return;
    suspend.mutate(
      { phone: phone.trim(), body: { reason: reason.trim() } },
      {
        onSuccess: () => {
          setPhone("");
          setReason("");
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
          <DialogTitle>Manual Suspension</DialogTitle>
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
            <Label className="text-xs">Reason</Label>
            <Textarea
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="Reason for suspension..."
              rows={3}
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button
            variant="destructive"
            onClick={handleSubmit}
            disabled={!phone.trim() || !reason.trim() || suspend.isPending}
          >
            {suspend.isPending ? "Suspending..." : "Suspend"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
