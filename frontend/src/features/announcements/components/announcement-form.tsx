import { useEffect, useMemo, useState } from "react";
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { X } from "lucide-react";
import { useAppointmentTypes } from "@/features/appointment-types/hooks/use-appointment-types";
import { useWeeklySlotStatuses } from "@/features/dashboard/hooks/use-dashboard";
import { aggregateBySchedule, type AggregatedEvent } from "@/features/dashboard/lib/aggregate";
import type { AnnouncementCreate, EventContext, RecipientScope } from "@/types/api";

interface AnnouncementFormProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (data: AnnouncementCreate) => void;
  isLoading: boolean;
  initialEventContext?: EventContext | null;
}

function eventKey(ev: AggregatedEvent): string {
  return ev.key;
}

function eventLabel(ev: AggregatedEvent): string {
  const date = ev.date;
  const time = ev.window_time.split(" ")[0];
  return `${date} ${time} — ${ev.display_name}`;
}

function eventToContext(ev: AggregatedEvent): EventContext {
  const [start, end] = ev.window_time.split(" – ");
  return {
    event_label: ev.display_name,
    event_date: ev.date,
    event_start_time: start || null,
    event_end_time: end || null,
    event_location: ev.location,
    service_name: ev.services[0]?.service_name ?? null,
    appointment_type_id: ev.services[0]?.appointment_type_id ?? null,
  };
}

export function AnnouncementForm({
  open,
  onOpenChange,
  onSubmit,
  isLoading,
  initialEventContext = null,
}: AnnouncementFormProps) {
  const [message, setMessage] = useState("");
  const [filterTypeIds, setFilterTypeIds] = useState<string[]>([]);
  const [scheduledAt, setScheduledAt] = useState("");
  const [tieToEvent, setTieToEvent] = useState(false);
  const [selectedEventKey, setSelectedEventKey] = useState<string>("");
  const [eventContext, setEventContext] = useState<EventContext | null>(null);
  const [recipientScope, setRecipientScope] = useState<RecipientScope>("all");

  const { data: appointmentTypes } = useAppointmentTypes();
  const week0 = useWeeklySlotStatuses(0);
  const week1 = useWeeklySlotStatuses(7);

  const events = useMemo(() => {
    const rows = [...(week0.data ?? []), ...(week1.data ?? [])];
    return aggregateBySchedule(rows);
  }, [week0.data, week1.data]);

  // Initialize from a caller-provided event context (e.g. from Dashboard "Send announcement")
  useEffect(() => {
    if (open && initialEventContext) {
      setTieToEvent(true);
      setEventContext(initialEventContext);
      // Default to event signups when launched from an event entry point
      setRecipientScope("event_signups");
      // Pre-fill the type filter when the event was for a single service
      if (initialEventContext.appointment_type_id) {
        setFilterTypeIds([initialEventContext.appointment_type_id]);
      }
      // Try to match against fetched events for the dropdown selection
      const match = events.find(
        (ev) =>
          ev.date === initialEventContext.event_date &&
          ev.display_name === initialEventContext.event_label
      );
      setSelectedEventKey(match?.key ?? "");
    } else if (!open) {
      // Reset on close
      setMessage("");
      setFilterTypeIds([]);
      setScheduledAt("");
      setTieToEvent(false);
      setSelectedEventKey("");
      setEventContext(null);
      setRecipientScope("all");
    }
  }, [open, initialEventContext, events]);

  function toggleType(id: string) {
    setFilterTypeIds((prev) =>
      prev.includes(id) ? prev.filter((t) => t !== id) : [...prev, id]
    );
  }

  function handleEventSelect(key: string | null) {
    const k = key ?? "";
    setSelectedEventKey(k);
    const ev = events.find((e) => eventKey(e) === k);
    if (ev) {
      const ctx = eventToContext(ev);
      setEventContext(ctx);
      // Auto-set type filter to event's services so only relevant volunteers get it
      const ids = ev.services.map((s) => s.appointment_type_id);
      setFilterTypeIds(ids);
    }
  }

  function handleTieToggle(next: boolean) {
    setTieToEvent(next);
    if (!next) {
      setSelectedEventKey("");
      setEventContext(null);
      setRecipientScope("all");
    } else {
      // Default to event signups when admin opts into event-tied mode
      setRecipientScope("event_signups");
    }
  }

  function handleSubmit() {
    onSubmit({
      message,
      filter_appointment_type_ids:
        filterTypeIds.length > 0 ? filterTypeIds : undefined,
      scheduled_at: scheduledAt || undefined,
      event_context: tieToEvent && eventContext ? eventContext : undefined,
      recipient_scope: tieToEvent ? recipientScope : "all",
    });
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="w-[95vw] sm:w-auto sm:min-w-[640px] sm:max-w-[900px] max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>New Announcement</DialogTitle>
        </DialogHeader>
        <div className="space-y-4 py-2">
          <div className="rounded-md border p-3 space-y-2">
            <label className="flex cursor-pointer items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={tieToEvent}
                onChange={(e) => handleTieToggle(e.target.checked)}
                className="h-4 w-4"
              />
              For a specific event
            </label>
            {tieToEvent && (
              <div className="space-y-1">
                <Label className="text-xs">Pick an event (next 14 days)</Label>
                <Select value={selectedEventKey} onValueChange={handleEventSelect}>
                  <SelectTrigger className="h-9">
                    <SelectValue placeholder={events.length === 0 ? "No upcoming events" : "Select an event..."} />
                  </SelectTrigger>
                  <SelectContent>
                    {events.map((ev) => (
                      <SelectItem key={ev.key} value={ev.key}>
                        {eventLabel(ev)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {eventContext && (
                  <p className="text-xs text-muted-foreground">
                    Header preview: <span className="font-mono">[{eventContext.event_label} on {eventContext.event_date} at {eventContext.event_start_time}{eventContext.event_location ? ` · ${eventContext.event_location}` : ""}]</span>
                  </p>
                )}
                <div className="space-y-1.5 pt-2">
                  <Label className="text-xs">Send to</Label>
                  <div className="space-y-1">
                    <label className="flex cursor-pointer items-start gap-2 rounded-md border p-2 text-xs">
                      <input
                        type="radio"
                        name="recipient-scope"
                        value="event_signups"
                        checked={recipientScope === "event_signups"}
                        onChange={() => setRecipientScope("event_signups")}
                        className="mt-0.5"
                      />
                      <span>
                        <span className="font-medium">Volunteers signed up for this event</span>
                        <span className="block text-muted-foreground">Only contacts with a confirmed booking on this date for the selected service(s).</span>
                      </span>
                    </label>
                    <label className="flex cursor-pointer items-start gap-2 rounded-md border p-2 text-xs">
                      <input
                        type="radio"
                        name="recipient-scope"
                        value="all"
                        checked={recipientScope === "all"}
                        onChange={() => setRecipientScope("all")}
                        className="mt-0.5"
                      />
                      <span>
                        <span className="font-medium">All opted-in volunteers</span>
                        <span className="block text-muted-foreground">Honors the appointment-type filter below if any chips are selected.</span>
                      </span>
                    </label>
                  </div>
                </div>
              </div>
            )}
          </div>

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
            disabled={
              !message.trim() ||
              isLoading ||
              (tieToEvent && !eventContext)
            }
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
