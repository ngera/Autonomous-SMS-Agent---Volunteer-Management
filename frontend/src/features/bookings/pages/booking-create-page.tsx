import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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
import { PageHeader } from "@/components/shared/page-header";
import { formatCurrency } from "@/lib/utils";
import { useCreateBooking, useAvailableSlots } from "../hooks/use-bookings";
import { useAppointmentTypes } from "@/features/appointment-types/hooks/use-appointment-types";

export function BookingCreatePage() {
  const navigate = useNavigate();
  const createBooking = useCreateBooking();
  const appointmentTypes = useAppointmentTypes();

  const [phone, setPhone] = useState("");
  const [typeId, setTypeId] = useState("");
  const [date, setDate] = useState("");
  const [selectedSlot, setSelectedSlot] = useState("");

  const slots = useAvailableSlots(date, typeId);

  const selectedType = appointmentTypes.data?.find((t) => t.id === typeId);

  function handleSubmit() {
    if (!phone || !typeId || !selectedSlot || !selectedType) return;
    createBooking.mutate(
      {
        contact_phone: phone,
        appointment_type_id: typeId,
        scheduled_at: selectedSlot,
        price_at_booking: selectedType.price,
      },
      { onSuccess: () => navigate("/bookings") }
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Create Booking"
        actions={
          <Button variant="ghost" onClick={() => navigate("/bookings")}>
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back
          </Button>
        }
      />

      <Card className="max-w-lg">
        <CardHeader>
          <CardTitle>New Booking</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label>Customer Phone</Label>
            <Input
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              placeholder="+447700000000"
            />
          </div>

          <div className="space-y-2">
            <Label>Appointment Type</Label>
            <Select
              value={typeId}
              onValueChange={(v) => {
                setTypeId(v ?? "");
                setSelectedSlot("");
              }}
            >
              <SelectTrigger>
                <SelectValue placeholder="Select type" />
              </SelectTrigger>
              <SelectContent>
                {appointmentTypes.data
                  ?.filter((t) => t.is_active)
                  .map((t) => (
                    <SelectItem key={t.id} value={t.id}>
                      {t.name} — {formatCurrency(t.price)} ({t.duration_minutes}min)
                    </SelectItem>
                  ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label>Date</Label>
            <Input
              type="date"
              value={date}
              onChange={(e) => {
                setDate(e.target.value);
                setSelectedSlot("");
              }}
            />
          </div>

          {date && typeId && (
            <div className="space-y-2">
              <Label>Available Slots</Label>
              {slots.isLoading ? (
                <p className="text-sm text-muted-foreground">Loading...</p>
              ) : !slots.data || slots.data.length === 0 ? (
                <p className="text-sm text-muted-foreground">No slots available.</p>
              ) : (
                <div className="grid grid-cols-3 gap-2 max-h-48 overflow-y-auto">
                  {slots.data.map((slot) => {
                    const time = new Date(slot.start).toLocaleTimeString("en-GB", {
                      hour: "2-digit",
                      minute: "2-digit",
                    });
                    return (
                      <Button
                        key={slot.start}
                        variant={selectedSlot === slot.start ? "default" : "outline"}
                        size="sm"
                        onClick={() => setSelectedSlot(slot.start)}
                      >
                        {time}
                      </Button>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          <Button
            className="w-full"
            onClick={handleSubmit}
            disabled={!phone || !typeId || !selectedSlot || createBooking.isPending}
          >
            {createBooking.isPending ? "Creating..." : "Create Booking"}
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
