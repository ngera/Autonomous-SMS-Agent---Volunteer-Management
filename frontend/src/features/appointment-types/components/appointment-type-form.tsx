import { useEffect, useId, useMemo, useRef, useState } from "react";
import type { KeyboardEvent } from "react";
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
import { Plus } from "lucide-react";
import { ComboboxPopup } from "@/components/shared/combobox-popup";
import { useAppointmentTypes } from "../hooks/use-appointment-types";
import type { AppointmentTypeResponse } from "@/types/api";

interface AppointmentTypeFormProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  editItem?: AppointmentTypeResponse | null;
  onSubmit: (data: {
    name: string;
    category: string;
    duration_minutes: number;
    price: number;
    description?: string;
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
  const [isActive, setIsActive] = useState(true);

  useEffect(() => {
    if (editItem) {
      setName(editItem.name);
      setCategory(editItem.category ?? "");
      setDuration(editItem.duration_minutes);
      setPrice(editItem.price);
      setDescription(editItem.description ?? "");
      setIsActive(editItem.is_active);
    } else {
      setName("");
      setCategory("");
      setDuration(60);
      setPrice(0);
      setDescription("");
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
            <Label htmlFor="appt-type-category">
              Category <span className="text-destructive">*</span>
            </Label>
            <CategoryCombobox
              id="appt-type-category"
              value={category}
              onChange={setCategory}
            />
          </div>
          <div className="space-y-2">
            <Label>Name</Label>
            <Input value={name} onChange={(e) => setName(e.target.value)} />
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
                name: name.trim(),
                category: category.trim(),
                duration_minutes: duration,
                price,
                description: description || undefined,
                is_active: isActive,
              })
            }
            disabled={!name.trim() || !category.trim() || isLoading}
          >
            {isLoading ? "Saving..." : "Save"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

interface CategoryComboboxProps {
  id: string;
  value: string;
  onChange: (v: string) => void;
}

/**
 * Searchable category input that lets the admin pick an existing category or
 * create a new one. The typed text is the value — if it matches an existing
 * category the dropdown highlights it; otherwise a "Create '<query>'" option
 * appears at the bottom.
 */
function CategoryCombobox({ id, value, onChange }: CategoryComboboxProps) {
  const { data: types } = useAppointmentTypes();
  const inputRef = useRef<HTMLDivElement>(null);
  const baseId = useId();
  const listId = `${baseId}-list`;
  const optId = (i: number) => `${baseId}-opt-${i}`;
  const createOptId = `${baseId}-opt-create`;

  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);

  const allCategories = useMemo(() => {
    const set = new Set<string>();
    for (const t of types ?? []) {
      if (t.category) set.add(t.category);
    }
    return Array.from(set).sort((a, b) => a.localeCompare(b));
  }, [types]);

  const trimmed = value.trim();
  const lowered = trimmed.toLowerCase();

  const matches = useMemo(() => {
    if (!lowered) return allCategories;
    return allCategories.filter((c) => c.toLowerCase().includes(lowered));
  }, [allCategories, lowered]);

  const exactMatch = useMemo(
    () => allCategories.some((c) => c.toLowerCase() === lowered),
    [allCategories, lowered]
  );
  const showCreate = trimmed.length > 0 && !exactMatch;
  // The total selectable rows = matches + (create row if shown).
  const totalRows = matches.length + (showCreate ? 1 : 0);
  const createRowIndex = matches.length; // create row sits at end

  // Reset highlight when the visible list shifts.
  useEffect(() => setActiveIndex(0), [value, open]);

  // Keep the highlighted option in view.
  useEffect(() => {
    if (!open) return;
    const id =
      activeIndex === createRowIndex && showCreate ? createOptId : optId(activeIndex);
    document.getElementById(id)?.scrollIntoView({ block: "nearest" });
  }, [activeIndex, open, showCreate, createRowIndex, createOptId]);

  function pick(text: string) {
    onChange(text);
    setOpen(false);
  }

  function selectActive() {
    if (totalRows === 0) return;
    if (activeIndex === createRowIndex && showCreate) {
      pick(trimmed);
      return;
    }
    pick(matches[activeIndex]);
  }

  function handleKey(e: KeyboardEvent<HTMLInputElement>) {
    switch (e.key) {
      case "ArrowDown":
        e.preventDefault();
        if (!open) { setOpen(true); return; }
        if (totalRows === 0) return;
        setActiveIndex((p) => (p + 1) % totalRows);
        return;
      case "ArrowUp":
        e.preventDefault();
        if (!open) { setOpen(true); return; }
        if (totalRows === 0) return;
        setActiveIndex((p) => (p - 1 + totalRows) % totalRows);
        return;
      case "Home":
        if (!open || totalRows === 0) return;
        e.preventDefault();
        setActiveIndex(0);
        return;
      case "End":
        if (!open || totalRows === 0) return;
        e.preventDefault();
        setActiveIndex(totalRows - 1);
        return;
      case "Enter":
        if (!open) return;
        e.preventDefault();
        selectActive();
        return;
      case "Escape":
        if (!open) return;
        e.preventDefault();
        setOpen(false);
        return;
      case "Tab":
        setOpen(false);
        return;
    }
  }

  const popupOpen = open && (matches.length > 0 || showCreate);

  return (
    <div className="relative" ref={inputRef}>
      <Input
        id={id}
        role="combobox"
        aria-autocomplete="list"
        aria-expanded={popupOpen}
        aria-controls={listId}
        aria-activedescendant={
          popupOpen
            ? activeIndex === createRowIndex && showCreate
              ? createOptId
              : optId(activeIndex)
            : undefined
        }
        value={value}
        onChange={(e) => {
          onChange(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onKeyDown={handleKey}
        placeholder="Type to search or create — e.g. Grooming, Therapy"
      />
      <ComboboxPopup
        triggerRef={inputRef}
        open={popupOpen}
        onRequestClose={() => setOpen(false)}
        id={listId}
        className="rounded-md border bg-popover shadow-lg max-h-60 overflow-y-auto"
      >
        {matches.length === 0 && !showCreate && (
          <div className="p-3 text-sm text-muted-foreground">No categories yet</div>
        )}
        {matches.map((c, i) => (
          <button
            key={c}
            id={optId(i)}
            role="option"
            aria-selected={i === activeIndex}
            type="button"
            tabIndex={-1}
            onMouseEnter={() => setActiveIndex(i)}
            onClick={() => pick(c)}
            className={`w-full text-left px-3 py-2 text-sm ${
              i === activeIndex ? "bg-accent" : "hover:bg-accent"
            }`}
          >
            {c}
          </button>
        ))}
        {showCreate && (
          <button
            id={createOptId}
            role="option"
            aria-selected={activeIndex === createRowIndex}
            type="button"
            tabIndex={-1}
            onMouseEnter={() => setActiveIndex(createRowIndex)}
            onClick={() => pick(trimmed)}
            className={`w-full text-left px-3 py-2 text-sm flex items-center gap-2 border-t ${
              activeIndex === createRowIndex ? "bg-accent" : "hover:bg-accent"
            }`}
          >
            <Plus className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
            <span>
              Create category <span className="font-medium">"{trimmed}"</span>
            </span>
          </button>
        )}
      </ComboboxPopup>
    </div>
  );
}
