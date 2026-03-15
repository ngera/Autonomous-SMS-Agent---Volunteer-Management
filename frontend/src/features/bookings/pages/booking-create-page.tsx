import { useState, useRef, useEffect } from "react";
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
import { formatCurrency, formatPhone } from "@/lib/utils";
import { useCreateBooking, useAvailableSlots } from "../hooks/use-bookings";
import { useAppointmentTypes } from "@/features/appointment-types/hooks/use-appointment-types";
import { useCustomers } from "@/features/customers/hooks/use-customers";

export function BookingCreatePage() {
  const navigate = useNavigate();
  const createBooking = useCreateBooking();
  const appointmentTypes = useAppointmentTypes();

  const [customerSearch, setCustomerSearch] = useState("");
  const [phone, setPhone] = useState("");
  const [selectedCustomerLabel, setSelectedCustomerLabel] = useState("");
  const [showDropdown, setShowDropdown] = useState(false);
  const [typeId, setTypeId] = useState("");
  const [date, setDate] = useState("");
  const [selectedSlot, setSelectedSlot] = useState("");
  const dropdownRef = useRef<HTMLDivElement>(null);

  const customers = useCustomers({
    search: customerSearch || undefined,
    page: 1,
    page_size: 10,
  });

  const slots = useAvailableSlots(date, typeId);
  const selectedType = appointmentTypes.data?.find((t) => t.id === typeId);

  // Close dropdown on outside click
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setShowDropdown(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

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
          <div className="space-y-2 relative" ref={dropdownRef}>
            <Label>Customer</Label>
            <Input
              value={selectedCustomerLabel || customerSearch}
              onChange={(e) => {
                setCustomerSearch(e.target.value);
                setSelectedCustomerLabel("");
                setPhone("");
                setShowDropdown(true);
              }}
              onFocus={() => {
                if (customerSearch && !selectedCustomerLabel) setShowDropdown(true);
              }}
              placeholder="Search by name or phone..."
            />
            {showDropdown && customerSearch && !selectedCustomerLabel && (
              <div className="absolute z-10 mt-1 w-full rounded-md border bg-popover shadow-lg max-h-48 overflow-y-auto">
                {customers.isLoading ? (
                  <div className="p-3 text-sm text-muted-foreground">Searching...</div>
                ) : !customers.data?.items.length ? (
                  <div className="p-3 text-sm text-muted-foreground">No customers found</div>
                ) : (
                  customers.data.items.map((c) => (
                    <button
                      key={c.phone}
                      type="button"
                      className="w-full text-left px-3 py-2 hover:bg-accent text-sm flex justify-between items-center"
                      onClick={() => {
                        setPhone(c.phone);
                        setSelectedCustomerLabel(
                          c.name ? `${c.name} (${formatPhone(c.phone)})` : formatPhone(c.phone)
                        );
                        setCustomerSearch("");
                        setShowDropdown(false);
                      }}
                    >
                      <span className="font-medium">{c.name || "—"}</span>
                      <span className="text-muted-foreground">{formatPhone(c.phone)}</span>
                    </button>
                  ))
                )}
              </div>
            )}
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
                    const time = new Date(slot.start).toLocaleTimeString("en-US", {
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
