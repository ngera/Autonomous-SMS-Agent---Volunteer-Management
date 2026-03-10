import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { useSlotPreview } from "../hooks/use-availability";
import { useAppointmentTypes } from "@/features/appointment-types/hooks/use-appointment-types";

export function SlotPreview() {
  const [date, setDate] = useState("");
  const [typeId, setTypeId] = useState("");
  const types = useAppointmentTypes();
  const slots = useSlotPreview(date, typeId);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Slot Preview</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap gap-3">
          <div className="space-y-1">
            <Label className="text-xs">Date</Label>
            <Input
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              className="w-40"
            />
          </div>
          <div className="space-y-1">
            <Label className="text-xs">Type</Label>
            <Select value={typeId} onValueChange={(v) => setTypeId(v ?? "")}>
              <SelectTrigger className="w-48">
                <SelectValue placeholder="Select type" />
              </SelectTrigger>
              <SelectContent>
                {types.data
                  ?.filter((t) => t.is_active)
                  .map((t) => (
                    <SelectItem key={t.id} value={t.id}>
                      {t.name}
                    </SelectItem>
                  ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        {date && typeId && (
          <div>
            {slots.isLoading ? (
              <p className="text-sm text-muted-foreground">Loading slots...</p>
            ) : !slots.data || slots.data.length === 0 ? (
              <p className="text-sm text-muted-foreground">No available slots.</p>
            ) : (
              <div className="flex flex-wrap gap-2">
                {slots.data.map((slot) => {
                  const time = new Date(slot.start).toLocaleTimeString("en-GB", {
                    hour: "2-digit",
                    minute: "2-digit",
                  });
                  return (
                    <Badge key={slot.start} variant="secondary">
                      {time}
                    </Badge>
                  );
                })}
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
