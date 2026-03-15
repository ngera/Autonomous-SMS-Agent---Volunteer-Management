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
import type { CustomerResponse } from "@/types/api";

interface CustomerFormProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  editItem?: CustomerResponse | null;
  onSubmit: (data: {
    phone: string;
    name: string;
    email?: string;
    reminder_preference_days?: number;
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
  const [reminderDays, setReminderDays] = useState(7);

  useEffect(() => {
    if (editItem) {
      setPhone(editItem.phone);
      setName(editItem.name ?? "");
      setEmail(editItem.email ?? "");
      setReminderDays(editItem.reminder_preference_days);
    } else {
      setPhone("");
      setName("");
      setEmail("");
      setReminderDays(7);
    }
  }, [editItem, open]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
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
            <Label>Reminder Preference (days)</Label>
            <Input
              type="number"
              value={reminderDays}
              onChange={(e) => setReminderDays(Number(e.target.value))}
              min={1}
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
                reminder_preference_days: reminderDays,
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
