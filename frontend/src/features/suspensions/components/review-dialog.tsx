import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";

type ReviewAction = "lift" | "confirm" | "ban";

interface ReviewDialogProps {
  open: boolean;
  action: ReviewAction;
  phone: string;
  onClose: () => void;
  onSubmit: (notes: string) => void;
  isPending: boolean;
}

const actionConfig: Record<ReviewAction, { title: string; button: string; variant: "default" | "destructive" }> = {
  lift: { title: "Lift Suspension", button: "Lift", variant: "default" },
  confirm: { title: "Confirm Suspension", button: "Confirm", variant: "destructive" },
  ban: { title: "Ban User", button: "Ban Permanently", variant: "destructive" },
};

export function ReviewDialog({
  open,
  action,
  phone,
  onClose,
  onSubmit,
  isPending,
}: ReviewDialogProps) {
  const [notes, setNotes] = useState("");
  const config = actionConfig[action];

  function handleSubmit() {
    if (!notes.trim()) return;
    onSubmit(notes.trim());
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        if (!o) {
          setNotes("");
          onClose();
        }
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{config.title}</DialogTitle>
        </DialogHeader>
        <div className="space-y-3">
          <p className="text-sm text-muted-foreground">
            {action === "lift"
              ? `Lift the suspension for ${phone} and restore their access?`
              : action === "confirm"
                ? `Confirm the suspension for ${phone}?`
                : `Permanently ban ${phone}? This cannot be undone easily.`}
          </p>
          <div className="space-y-1">
            <Label className="text-xs">Notes</Label>
            <Textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Review notes..."
              rows={3}
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button
            variant={config.variant}
            onClick={handleSubmit}
            disabled={!notes.trim() || isPending}
          >
            {isPending ? "Processing..." : config.button}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
