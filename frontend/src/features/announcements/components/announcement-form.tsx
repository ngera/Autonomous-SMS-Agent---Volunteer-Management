import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { X } from "lucide-react";
import { useAppointmentTypes } from "@/features/appointment-types/hooks/use-appointment-types";
import type { AnnouncementCreate } from "@/types/api";

interface AnnouncementFormProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (data: AnnouncementCreate) => void;
  isLoading: boolean;
}

export function AnnouncementForm({
  open,
  onOpenChange,
  onSubmit,
  isLoading,
}: AnnouncementFormProps) {
  const [message, setMessage] = useState("");
  const [filterTypeIds, setFilterTypeIds] = useState<string[]>([]);
  const [scheduledAt, setScheduledAt] = useState("");

  const { data: appointmentTypes } = useAppointmentTypes();

  function toggleType(id: string) {
    setFilterTypeIds((prev) =>
      prev.includes(id) ? prev.filter((t) => t !== id) : [...prev, id]
    );
  }

  function handleSubmit() {
    onSubmit({
      message,
      filter_appointment_type_ids:
        filterTypeIds.length > 0 ? filterTypeIds : undefined,
      scheduled_at: scheduledAt || undefined,
    });
    setMessage("");
    setFilterTypeIds([]);
    setScheduledAt("");
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>New Announcement</DialogTitle>
        </DialogHeader>
        <div className="space-y-4 py-2">
          <div className="space-y-2">
            <Label>Message *</Label>
            <Textarea
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              placeholder="Type your announcement message..."
              rows={4}
            />
            <p className="text-xs text-muted-foreground">
              {message.length} characters
            </p>
          </div>

          <div className="space-y-2">
            <Label>Filter by Appointment Type</Label>
            <p className="text-xs text-muted-foreground">
              Leave empty to send to all opted-in customers
            </p>
            <div className="flex flex-wrap gap-2">
              {(appointmentTypes ?? [])
                .filter((t) => t.is_active)
                .map((type) => {
                  const selected = filterTypeIds.includes(type.id);
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
          </div>

          <div className="space-y-2">
            <Label>Schedule (optional)</Label>
            <Input
              type="datetime-local"
              value={scheduledAt}
              onChange={(e) => setScheduledAt(e.target.value)}
            />
            <p className="text-xs text-muted-foreground">
              Leave empty to send immediately
            </p>
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
            onClick={handleSubmit}
            disabled={!message.trim() || isLoading}
          >
            {isLoading
              ? "Sending..."
              : scheduledAt
                ? "Schedule"
                : "Send Now"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
