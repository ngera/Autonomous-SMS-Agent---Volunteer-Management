import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { useAvailableSlots } from "../hooks/use-bookings";
import { formatDateTime } from "@/lib/utils";

interface RescheduleDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  appointmentTypeId: string;
  onConfirm: (newScheduledAt: string) => void;
  isLoading: boolean;
}

export function RescheduleDialog({
  open,
  onOpenChange,
  appointmentTypeId,
  onConfirm,
  isLoading,
}: RescheduleDialogProps) {
  const [date, setDate] = useState("");
  const [selectedSlot, setSelectedSlot] = useState("");

  const slots = useAvailableSlots(date, appointmentTypeId);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Reschedule Booking</DialogTitle>
        </DialogHeader>
        <div className="space-y-4 py-2">
          <div className="space-y-2">
            <Label>Select Date</Label>
            <Input
              type="date"
              value={date}
              onChange={(e) => {
                setDate(e.target.value);
                setSelectedSlot("");
              }}
            />
          </div>
          {date && (
            <div className="space-y-2">
              <Label>Available Slots</Label>
              {slots.isLoading ? (
                <p className="text-sm text-muted-foreground">Loading slots...</p>
              ) : !slots.data || slots.data.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  No available slots for this date.
                </p>
              ) : (
                <div className="grid grid-cols-3 gap-2 max-h-48 overflow-y-auto">
                  {slots.data.map((slot) => (
                    <Button
                      key={slot.start}
                      variant={selectedSlot === slot.start ? "default" : "outline"}
                      size="sm"
                      onClick={() => setSelectedSlot(slot.start)}
                    >
                      {formatDateTime(slot.start).split(", ")[1]}
                    </Button>
                  ))}
                </div>
              )}
            </div>
          )}
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
            onClick={() => onConfirm(selectedSlot)}
            disabled={!selectedSlot || isLoading}
          >
            {isLoading ? "Rescheduling..." : "Confirm Reschedule"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
