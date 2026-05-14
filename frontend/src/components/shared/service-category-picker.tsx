import { useEffect, useId, useMemo, useRef, useState } from "react";
import type { KeyboardEvent } from "react";
import { Input } from "@/components/ui/input";
import { X } from "lucide-react";
import { ComboboxPopup } from "@/components/shared/combobox-popup";
import type { AppointmentTypeResponse } from "@/types/api";

interface ServiceCategoryPickerProps {
  activeTypes: AppointmentTypeResponse[];
  /** IDs already chosen — hidden from the picker so the admin can't double-add. */
  excludeIds: string[];
  onAdd: (typeId: string) => void;
  disabled?: boolean;
  /** Optional placeholder override for tighter contexts. */
  size?: "sm" | "md";
}

/**
 * Two cascading searchable inputs for picking an active service type:
 * Category, then a service in that category. Calls `onAdd(typeId)` when the
 * second input picks a service. Stays in place — does not own the chosen
 * services list, just the add UX.
 */
export function ServiceCategoryPicker({
  activeTypes,
  excludeIds,
  onAdd,
  disabled = false,
  size = "md",
}: ServiceCategoryPickerProps) {
  const baseId = useId();
  const catListId = `${baseId}-cat`;
  const typeListId = `${baseId}-type`;
  const catOptId = (i: number) => `${baseId}-cat-opt-${i}`;
  const typeOptId = (i: number) => `${baseId}-type-opt-${i}`;

  const [categoryQuery, setCategoryQuery] = useState("");
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [showCategory, setShowCategory] = useState(false);
  const [categoryActive, setCategoryActive] = useState(0);

  const [typeQuery, setTypeQuery] = useState("");
  const [showType, setShowType] = useState(false);
  const [typeActive, setTypeActive] = useState(0);

  const categoryRef = useRef<HTMLDivElement>(null);
  const typeRef = useRef<HTMLDivElement>(null);

  const excluded = useMemo(() => new Set(excludeIds), [excludeIds]);

  const availableTypes = useMemo(
    () =>
      activeTypes
        .filter((t) => !excluded.has(t.id))
        .sort((a, b) => a.name.localeCompare(b.name)),
    [activeTypes, excluded]
  );

  const availableCategories = useMemo(() => {
    const set = new Set<string>();
    for (const t of availableTypes) set.add(t.category);
    return Array.from(set).sort((a, b) => a.localeCompare(b));
  }, [availableTypes]);

  const filteredCategories = useMemo(() => {
    const q = categoryQuery.trim().toLowerCase();
    if (!q) return availableCategories;
    return availableCategories.filter((c) => c.toLowerCase().includes(q));
  }, [availableCategories, categoryQuery]);

  const typesInCategory = useMemo(() => {
    if (selectedCategory === null) return [];
    return availableTypes.filter((t) => t.category === selectedCategory);
  }, [availableTypes, selectedCategory]);

  const filteredTypes = useMemo(() => {
    const q = typeQuery.trim().toLowerCase();
    if (!q) return typesInCategory;
    return typesInCategory.filter((t) => t.name.toLowerCase().includes(q));
  }, [typesInCategory, typeQuery]);

  // Reset highlight when the visible list shifts.
  useEffect(() => setCategoryActive(0), [
    categoryQuery,
    showCategory,
    availableCategories.length,
  ]);
  useEffect(() => setTypeActive(0), [
    typeQuery,
    showType,
    selectedCategory,
    typesInCategory.length,
  ]);

  // Auto-clear the picked category if the last service in it just got added.
  useEffect(() => {
    if (selectedCategory !== null && !availableCategories.includes(selectedCategory)) {
      setSelectedCategory(null);
      setCategoryQuery("");
      setTypeQuery("");
    }
  }, [availableCategories, selectedCategory]);

  // Scroll active option into view.
  useEffect(() => {
    if (showCategory) {
      document
        .getElementById(catOptId(categoryActive))
        ?.scrollIntoView({ block: "nearest" });
    }
  }, [categoryActive, showCategory]);
  useEffect(() => {
    if (showType) {
      document
        .getElementById(typeOptId(typeActive))
        ?.scrollIntoView({ block: "nearest" });
    }
  }, [typeActive, showType]);

  const categoryOpen =
    !disabled && showCategory && selectedCategory === null && availableCategories.length > 0;
  const typeOpen =
    !disabled && showType && selectedCategory !== null && typesInCategory.length > 0;

  function pickCategory(c: string) {
    setSelectedCategory(c);
    setCategoryQuery("");
    setShowCategory(false);
    setTypeQuery("");
  }

  function clearCategory() {
    setSelectedCategory(null);
    setCategoryQuery("");
    setTypeQuery("");
  }

  function pickType(t: AppointmentTypeResponse) {
    onAdd(t.id);
    setTypeQuery("");
    setShowType(false);
  }

  function handleCategoryKey(e: KeyboardEvent<HTMLInputElement>) {
    handleComboKey(e, {
      open: categoryOpen,
      setOpen: setShowCategory,
      itemsLen: filteredCategories.length,
      activeIndex: categoryActive,
      setActiveIndex: setCategoryActive,
      onPick: () => pickCategory(filteredCategories[categoryActive]),
    });
  }
  function handleTypeKey(e: KeyboardEvent<HTMLInputElement>) {
    handleComboKey(e, {
      open: typeOpen,
      setOpen: setShowType,
      itemsLen: filteredTypes.length,
      activeIndex: typeActive,
      setActiveIndex: setTypeActive,
      onPick: () => pickType(filteredTypes[typeActive]),
    });
  }

  const inputClass = size === "sm" ? "h-8 text-xs" : "";

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 w-full">
      <div className="relative" ref={categoryRef}>
        <Input
          role="combobox"
          aria-autocomplete="list"
          aria-expanded={categoryOpen}
          aria-controls={catListId}
          aria-activedescendant={
            categoryOpen && filteredCategories.length > 0
              ? catOptId(categoryActive)
              : undefined
          }
          value={selectedCategory ?? categoryQuery}
          onChange={(e) => {
            setSelectedCategory(null);
            setCategoryQuery(e.target.value);
            setShowCategory(true);
          }}
          onFocus={() => setShowCategory(true)}
          onKeyDown={handleCategoryKey}
          placeholder={
            availableCategories.length === 0
              ? "All services already added"
              : "Category…"
          }
          className={`${inputClass} ${selectedCategory !== null ? "pr-8" : ""}`}
          disabled={disabled || availableCategories.length === 0}
        />
        {selectedCategory !== null && !disabled && (
          <button
            type="button"
            onClick={clearCategory}
            aria-label="Clear category"
            className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
          >
            <X className="h-4 w-4" />
          </button>
        )}
        <ComboboxPopup
          triggerRef={categoryRef}
          open={categoryOpen}
          onRequestClose={() => setShowCategory(false)}
          id={catListId}
          className="rounded-md border bg-popover shadow-lg max-h-60 overflow-y-auto"
        >
          {filteredCategories.length === 0 ? (
            <div className="p-3 text-sm text-muted-foreground">No matches</div>
          ) : (
            filteredCategories.map((c, i) => (
              <button
                key={c}
                id={catOptId(i)}
                role="option"
                aria-selected={i === categoryActive}
                type="button"
                tabIndex={-1}
                onMouseEnter={() => setCategoryActive(i)}
                onClick={() => pickCategory(c)}
                className={`w-full text-left px-3 py-2 text-sm ${
                  i === categoryActive ? "bg-accent" : "hover:bg-accent"
                }`}
              >
                {c}
              </button>
            ))
          )}
        </ComboboxPopup>
      </div>

      <div className="relative" ref={typeRef}>
        <Input
          role="combobox"
          aria-autocomplete="list"
          aria-expanded={typeOpen}
          aria-controls={typeListId}
          aria-activedescendant={
            typeOpen && filteredTypes.length > 0
              ? typeOptId(typeActive)
              : undefined
          }
          value={typeQuery}
          onChange={(e) => {
            setTypeQuery(e.target.value);
            setShowType(true);
          }}
          onFocus={() => setShowType(true)}
          onKeyDown={handleTypeKey}
          placeholder={
            selectedCategory === null
              ? "Pick a category first"
              : typesInCategory.length === 0
                ? "No services in this category"
                : "Service…"
          }
          className={inputClass}
          disabled={disabled || selectedCategory === null || typesInCategory.length === 0}
        />
        <ComboboxPopup
          triggerRef={typeRef}
          open={typeOpen}
          onRequestClose={() => setShowType(false)}
          id={typeListId}
          className="rounded-md border bg-popover shadow-lg max-h-60 overflow-y-auto"
        >
          {filteredTypes.length === 0 ? (
            <div className="p-3 text-sm text-muted-foreground">No matches</div>
          ) : (
            filteredTypes.map((t, i) => (
              <button
                key={t.id}
                id={typeOptId(i)}
                role="option"
                aria-selected={i === typeActive}
                type="button"
                tabIndex={-1}
                onMouseEnter={() => setTypeActive(i)}
                onClick={() => pickType(t)}
                className={`w-full text-left px-3 py-2 text-sm flex items-center justify-between gap-3 ${
                  i === typeActive ? "bg-accent" : "hover:bg-accent"
                }`}
              >
                <span className="flex flex-col">
                  <span className="font-medium">{t.name}</span>
                  <span className="text-xs text-muted-foreground">
                    {t.duration_minutes} min
                  </span>
                </span>
              </button>
            ))
          )}
        </ComboboxPopup>
      </div>
    </div>
  );
}

interface ComboKeyArgs {
  open: boolean;
  setOpen: (v: boolean) => void;
  itemsLen: number;
  activeIndex: number;
  setActiveIndex: (updater: (prev: number) => number) => void;
  onPick: () => void;
}

function handleComboKey(
  e: KeyboardEvent<HTMLInputElement>,
  { open, setOpen, itemsLen, activeIndex, setActiveIndex, onPick }: ComboKeyArgs
) {
  switch (e.key) {
    case "ArrowDown":
      e.preventDefault();
      if (!open) { setOpen(true); return; }
      if (itemsLen === 0) return;
      setActiveIndex((p) => (p + 1) % itemsLen);
      return;
    case "ArrowUp":
      e.preventDefault();
      if (!open) { setOpen(true); return; }
      if (itemsLen === 0) return;
      setActiveIndex((p) => (p - 1 + itemsLen) % itemsLen);
      return;
    case "Home":
      if (!open || itemsLen === 0) return;
      e.preventDefault();
      setActiveIndex(() => 0);
      return;
    case "End":
      if (!open || itemsLen === 0) return;
      e.preventDefault();
      setActiveIndex(() => itemsLen - 1);
      return;
    case "Enter":
      if (!open) return;
      if (activeIndex < 0 || activeIndex >= itemsLen) return;
      e.preventDefault();
      onPick();
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
