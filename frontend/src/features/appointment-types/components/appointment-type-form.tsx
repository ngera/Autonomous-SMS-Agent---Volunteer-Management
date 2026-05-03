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
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { Button } from "@/components/ui/button";
import type { AppointmentTypeResponse } from "@/types/api";

interface AppointmentTypeFormProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  editItem?: AppointmentTypeResponse | null;
  onSubmit: (data: {
    name: string;
    category?: string;
    duration_minutes: number;
    price: number;
    description?: string;
    recurrence_weeks_default?: number;
    is_active: boolean;
  }) => void;
  isLoading: boolean;
}

export function AppointmentTypeForm({
  open,
  onOpenChange,
  editItem,
  onSubmit,
  isLoading,
}: AppointmentTypeFormProps) {
  const [name, setName] = useState("");
  const [category, setCategory] = useState("");
  const [duration, setDuration] = useState(60);
  const [price, setPrice] = useState(0);
  const [description, setDescription] = useState("");
  const [recurrenceWeeks, setRecurrenceWeeks] = useState<number | "">("");
  const [isActive, setIsActive] = useState(true);

  useEffect(() => {
    if (editItem) {
      setName(editItem.name);
      setCategory(editItem.category ?? "");
      setDuration(editItem.duration_minutes);
      setPrice(editItem.price);
      setDescription(editItem.description ?? "");
      setRecurrenceWeeks(editItem.recurrence_weeks_default ?? "");
      setIsActive(editItem.is_active);
    } else {
      setName("");
      setCategory("");
      setDuration(60);
      setPrice(0);
      setDescription("");
      setRecurrenceWeeks("");
      setIsActive(true);
    }
  }, [editItem, open]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>
            {editItem ? "Edit Service Type" : "New Service Type"}
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-4 py-2">
          <div className="space-y-2">
            <Label>Name</Label>
            <Input value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          <div className="space-y-2">
            <Label>Category (optional)</Label>
            <Input
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              placeholder="e.g. Grooming, Therapy, Consultation"
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>Duration (minutes)</Label>
              <Input
                type="number"
                value={duration}
                onChange={(e) => setDuration(Number(e.target.value))}
                min={5}
              />
            </div>
            <div className="space-y-2">
              <Label>Price</Label>
              <Input
                type="number"
                value={price}
                onChange={(e) => setPrice(Number(e.target.value))}
                min={0}
                step={0.01}
              />
            </div>
          </div>
          <div className="space-y-2">
            <Label>Description (optional)</Label>
            <Textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label>Default Recurrence (weeks, optional)</Label>
            <Input
              type="number"
              value={recurrenceWeeks}
              onChange={(e) =>
                setRecurrenceWeeks(e.target.value ? Number(e.target.value) : "")
              }
              min={1}
              placeholder="e.g. 4"
            />
          </div>
          <div className="flex items-center gap-2">
            <Switch checked={isActive} onCheckedChange={setIsActive} />
            <Label>Active</Label>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={isLoading}>
            Cancel
          </Button>
          <Button
            onClick={() =>
              onSubmit({
                name,
                category: category.trim() || undefined,
                duration_minutes: duration,
                price,
                description: description || undefined,
                recurrence_weeks_default: recurrenceWeeks ? Number(recurrenceWeeks) : undefined,
                is_active: isActive,
              })
            }
            disabled={!name || isLoading}
          >
            {isLoading ? "Saving..." : "Save"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
