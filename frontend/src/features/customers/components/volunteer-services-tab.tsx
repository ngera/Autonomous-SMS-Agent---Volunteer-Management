import { useState, useEffect, useMemo, useRef } from "react";
import type { KeyboardEvent } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { AlertTriangle, X, Plus } from "lucide-react";
import { listAppointmentTypes } from "@/features/appointment-types/api";
import { ComboboxPopup } from "@/components/shared/combobox-popup";
import { updateCustomer } from "../api";
import type { AppointmentTypeResponse, CustomerResponse } from "@/types/api";

interface VolunteerServicesTabProps {
  customer: CustomerResponse;
  canEdit: boolean;
  onUpdated: () => void;
}

const CATEGORY_LIST_ID = "volunteer-add-service-cat-listbox";
const TYPE_LIST_ID = "volunteer-add-service-type-listbox";
const categoryOptionId = (i: number) => `volunteer-add-service-cat-opt-${i}`;
const typeOptionId = (i: number) => `volunteer-add-service-type-opt-${i}`;

interface ComboKeyArgs<T> {
  open: boolean;
  setOpen: (v: boolean) => void;
  items: T[];
  activeIndex: number;
  setActiveIndex: (updater: (prev: number) => number) => void;
  onPick: (item: T) => void;
}

function handleComboKey<T>(
  e: KeyboardEvent<HTMLInputElement>,
  { open, setOpen, items, activeIndex, setActiveIndex, onPick }: ComboKeyArgs<T>
) {
  switch (e.key) {
    case "ArrowDown":
      e.preventDefault();
      if (!open) { setOpen(true); return; }
      if (items.length === 0) return;
      setActiveIndex((prev) => (prev + 1) % items.length);
      return;
    case "ArrowUp":
      e.preventDefault();
      if (!open) { setOpen(true); return; }
      if (items.length === 0) return;
      setActiveIndex((prev) => (prev - 1 + items.length) % items.length);
      return;
    case "Home":
      if (!open || items.length === 0) return;
      e.preventDefault();
      setActiveIndex(() => 0);
      return;
    case "End":
      if (!open || items.length === 0) return;
      e.preventDefault();
      setActiveIndex(() => items.length - 1);
      return;
    case "Enter":
      if (!open) return;
      if (activeIndex < 0 || activeIndex >= items.length) return;
      e.preventDefault();
      onPick(items[activeIndex]);
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

export function VolunteerServicesTab({ customer, canEdit, onUpdated }: VolunteerServicesTabProps) {
  const qc = useQueryClient();
  const { data: appointmentTypes, isLoading } = useQuery({
    queryKey: ["appointment-types-volunteer-tab"],
    queryFn: listAppointmentTypes,
  });

  const activeTypes = useMemo(
    () => (appointmentTypes ?? []).filter((t) => t.is_active),
    [appointmentTypes]
  );

  const [selectedIds, setSelectedIds] = useState<string[]>(customer.preferred_appointment_type_ids ?? []);
  const [allServicesEnabled, setAllServicesEnabled] = useState(customer.all_services_enabled ?? false);
  const [dirty, setDirty] = useState(false);

  const [categoryQuery, setCategoryQuery] = useState("");
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [showCategoryDropdown, setShowCategoryDropdown] = useState(false);
  const [categoryActiveIndex, setCategoryActiveIndex] = useState(0);

  const [typeQuery, setTypeQuery] = useState("");
  const [showTypeDropdown, setShowTypeDropdown] = useState(false);
  const [typeActiveIndex, setTypeActiveIndex] = useState(0);

  const categoryRef = useRef<HTMLDivElement>(null);
  const typeRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setSelectedIds(customer.preferred_appointment_type_ids ?? []);
    setAllServicesEnabled(customer.all_services_enabled ?? false);
    setDirty(false);
    setSelectedCategory(null);
    setCategoryQuery("");
    setTypeQuery("");
  }, [customer]);

  const selectedSet = useMemo(() => new Set(selectedIds), [selectedIds]);

  const selectedTypes = useMemo(
    () =>
      activeTypes
        .filter((t) => selectedSet.has(t.id))
        .sort((a, b) => a.name.localeCompare(b.name)),
    [activeTypes, selectedSet]
  );

  const availableTypes = useMemo(
    () =>
      activeTypes
        .filter((t) => !selectedSet.has(t.id))
        .sort((a, b) => a.name.localeCompare(b.name)),
    [activeTypes, selectedSet]
  );

  // Categories derived from the *unassigned* pool, so empty categories
  // don't show up.
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
  useEffect(() => setCategoryActiveIndex(0), [
    categoryQuery,
    showCategoryDropdown,
    availableCategories.length,
  ]);
  useEffect(() => setTypeActiveIndex(0), [
    typeQuery,
    showTypeDropdown,
    selectedCategory,
    typesInCategory.length,
  ]);

  // Keep the highlighted option scrolled into view.
  useEffect(() => {
    if (showCategoryDropdown) {
      document
        .getElementById(categoryOptionId(categoryActiveIndex))
        ?.scrollIntoView({ block: "nearest" });
    }
  }, [categoryActiveIndex, showCategoryDropdown]);
  useEffect(() => {
    if (showTypeDropdown) {
      document
        .getElementById(typeOptionId(typeActiveIndex))
        ?.scrollIntoView({ block: "nearest" });
    }
  }, [typeActiveIndex, showTypeDropdown]);

  // Outside-click handling now lives inside <ComboboxPopup>, which can see
  // its own portaled DOM node.

  // If the currently picked category is no longer available (e.g. last type
  // in it was just added), drop the selection so the input clears.
  useEffect(() => {
    if (selectedCategory !== null && !availableCategories.includes(selectedCategory)) {
      setSelectedCategory(null);
      setCategoryQuery("");
    }
  }, [availableCategories, selectedCategory]);

  function addService(type: AppointmentTypeResponse) {
    setSelectedIds((prev) => (prev.includes(type.id) ? prev : [...prev, type.id]));
    setDirty(true);
    setTypeQuery("");
    setShowTypeDropdown(false);
  }

  function pickCategory(c: string) {
    setSelectedCategory(c);
    setCategoryQuery("");
    setShowCategoryDropdown(false);
    setTypeQuery("");
  }

  function clearCategory() {
    setSelectedCategory(null);
    setCategoryQuery("");
    setTypeQuery("");
  }

  function remove(id: string) {
    setSelectedIds((prev) => prev.filter((x) => x !== id));
    setDirty(true);
  }

  function handleAllServicesToggle(checked: boolean) {
    setAllServicesEnabled(checked);
    setDirty(true);
  }

  const addBlockEnabled = canEdit && !allServicesEnabled;
  const categoryListOpen =
    addBlockEnabled &&
    showCategoryDropdown &&
    selectedCategory === null &&
    availableCategories.length > 0;
  const typeListOpen =
    addBlockEnabled &&
    showTypeDropdown &&
    selectedCategory !== null &&
    typesInCategory.length > 0;

  const saveMutation = useMutation({
    mutationFn: () =>
      updateCustomer(customer.phone, {
        all_services_enabled: allServicesEnabled,
        preferred_appointment_type_ids: selectedIds,
      }),
    onSuccess: () => {
      setDirty(false);
      onUpdated();
      void qc.invalidateQueries({ queryKey: ["customers"] });
    },
  });

  const hasNoAccess = !allServicesEnabled && selectedIds.length === 0;

  if (isLoading) {
    return <p className="text-sm text-muted-foreground p-4">Loading services...</p>;
  }

  if (activeTypes.length === 0) {
    return <p className="text-sm text-muted-foreground p-4">No appointment types configured.</p>;
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle className="text-base">Services this volunteer participates in</CardTitle>
        {canEdit && dirty && (
          <Button size="sm" onClick={() => saveMutation.mutate()} disabled={saveMutation.isPending}>
            {saveMutation.isPending ? "Saving..." : "Save"}
          </Button>
        )}
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex items-center justify-between rounded-lg border p-3">
          <div>
            <Label className="text-sm font-medium">All Services</Label>
            <p className="text-xs text-muted-foreground">
              Allow this volunteer to book any active service
            </p>
          </div>
          <Switch
            checked={allServicesEnabled}
            onCheckedChange={handleAllServicesToggle}
            disabled={!canEdit}
          />
        </div>

        {hasNoAccess && (
          <div className="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 p-3 dark:border-amber-900 dark:bg-amber-950">
            <AlertTriangle className="h-4 w-4 text-amber-600 mt-0.5 shrink-0" />
            <p className="text-sm text-amber-800 dark:text-amber-200">
              This volunteer cannot book any services. Enable "All Services" above or assign specific services below.
            </p>
          </div>
        )}

        {allServicesEnabled ? (
          <p className="text-xs text-muted-foreground">
            Individual assignments are ignored when All Services is enabled.
          </p>
        ) : (
          <div className="space-y-3">
            {selectedTypes.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No services assigned yet. Use the search boxes below to add some.
              </p>
            ) : (
              <div className="space-y-2">
                {selectedTypes.map((type) => (
                  <ServiceRow
                    key={type.id}
                    type={type}
                    canEdit={canEdit}
                    onRemove={() => remove(type.id)}
                  />
                ))}
              </div>
            )}

            {canEdit && (
              <div className="space-y-2">
                <Label className="text-xs text-muted-foreground">Add a service</Label>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  {/* Category combobox */}
                  <div className="relative" ref={categoryRef}>
                    <div className="relative">
                      <Input
                        id="volunteer-add-cat-input"
                        role="combobox"
                        aria-autocomplete="list"
                        aria-expanded={categoryListOpen}
                        aria-controls={CATEGORY_LIST_ID}
                        aria-activedescendant={
                          categoryListOpen && filteredCategories.length > 0
                            ? categoryOptionId(categoryActiveIndex)
                            : undefined
                        }
                        value={selectedCategory ?? categoryQuery}
                        onChange={(e) => {
                          setSelectedCategory(null);
                          setCategoryQuery(e.target.value);
                          setShowCategoryDropdown(true);
                        }}
                        onFocus={() => setShowCategoryDropdown(true)}
                        onKeyDown={(e) =>
                          handleComboKey(e, {
                            open: categoryListOpen,
                            setOpen: setShowCategoryDropdown,
                            items: filteredCategories,
                            activeIndex: categoryActiveIndex,
                            setActiveIndex: setCategoryActiveIndex,
                            onPick: pickCategory,
                          })
                        }
                        placeholder={
                          availableCategories.length === 0
                            ? "All services already assigned"
                            : "Search categories..."
                        }
                        className={selectedCategory !== null ? "pr-8" : ""}
                        disabled={availableCategories.length === 0}
                      />
                      {selectedCategory !== null && (
                        <button
                          type="button"
                          onClick={clearCategory}
                          aria-label="Clear category"
                          className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                        >
                          <X className="h-4 w-4" />
                        </button>
                      )}
                    </div>
                    <ComboboxPopup
                      triggerRef={categoryRef}
                      open={categoryListOpen}
                      onRequestClose={() => setShowCategoryDropdown(false)}
                      id={CATEGORY_LIST_ID}
                      className="rounded-md border bg-popover shadow-lg max-h-60 overflow-y-auto"
                    >
                      {filteredCategories.length === 0 ? (
                        <div className="p-3 text-sm text-muted-foreground">No matches</div>
                      ) : (
                        filteredCategories.map((c, i) => (
                          <button
                            key={c}
                            id={categoryOptionId(i)}
                            role="option"
                            aria-selected={i === categoryActiveIndex}
                            type="button"
                            tabIndex={-1}
                            onMouseEnter={() => setCategoryActiveIndex(i)}
                            onClick={() => pickCategory(c)}
                            className={`w-full text-left px-3 py-2 text-sm ${
                              i === categoryActiveIndex ? "bg-accent" : "hover:bg-accent"
                            }`}
                          >
                            {c}
                          </button>
                        ))
                      )}
                    </ComboboxPopup>
                  </div>

                  {/* Service combobox */}
                  <div className="relative" ref={typeRef}>
                    <Input
                      id="volunteer-add-type-input"
                      role="combobox"
                      aria-autocomplete="list"
                      aria-expanded={typeListOpen}
                      aria-controls={TYPE_LIST_ID}
                      aria-activedescendant={
                        typeListOpen && filteredTypes.length > 0
                          ? typeOptionId(typeActiveIndex)
                          : undefined
                      }
                      value={typeQuery}
                      onChange={(e) => {
                        setTypeQuery(e.target.value);
                        setShowTypeDropdown(true);
                      }}
                      onFocus={() => setShowTypeDropdown(true)}
                      onKeyDown={(e) =>
                        handleComboKey(e, {
                          open: typeListOpen,
                          setOpen: setShowTypeDropdown,
                          items: filteredTypes,
                          activeIndex: typeActiveIndex,
                          setActiveIndex: setTypeActiveIndex,
                          onPick: addService,
                        })
                      }
                      placeholder={
                        selectedCategory === null
                          ? "Choose a category first"
                          : typesInCategory.length === 0
                            ? "No services in this category"
                            : "Search services..."
                      }
                      disabled={selectedCategory === null || typesInCategory.length === 0}
                    />
                    <ComboboxPopup
                      triggerRef={typeRef}
                      open={typeListOpen}
                      onRequestClose={() => setShowTypeDropdown(false)}
                      id={TYPE_LIST_ID}
                      className="rounded-md border bg-popover shadow-lg max-h-60 overflow-y-auto"
                    >
                      {filteredTypes.length === 0 ? (
                        <div className="p-3 text-sm text-muted-foreground">No matches</div>
                      ) : (
                        filteredTypes.map((t, i) => (
                          <button
                            key={t.id}
                            id={typeOptionId(i)}
                            role="option"
                            aria-selected={i === typeActiveIndex}
                            type="button"
                            tabIndex={-1}
                            onMouseEnter={() => setTypeActiveIndex(i)}
                            onClick={() => addService(t)}
                            className={`w-full text-left px-3 py-2 text-sm flex items-center justify-between gap-3 ${
                              i === typeActiveIndex ? "bg-accent" : "hover:bg-accent"
                            }`}
                          >
                            <span className="flex flex-col">
                              <span className="font-medium">{t.name}</span>
                              <span className="text-xs text-muted-foreground">
                                {t.duration_minutes} min
                              </span>
                            </span>
                            <Plus className="h-4 w-4 shrink-0 text-muted-foreground" />
                          </button>
                        ))
                      )}
                    </ComboboxPopup>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

interface ServiceRowProps {
  type: AppointmentTypeResponse;
  canEdit: boolean;
  onRemove: () => void;
}

function ServiceRow({ type, canEdit, onRemove }: ServiceRowProps) {
  return (
    <div className="flex items-center justify-between rounded-lg border border-primary bg-primary/5 p-3">
      <div>
        <p className="text-sm font-medium">{type.name}</p>
        <p className="text-xs text-muted-foreground">
          {type.category} · {type.duration_minutes} min
        </p>
      </div>
      {canEdit && (
        <Button
          variant="ghost"
          size="sm"
          onClick={onRemove}
          aria-label={`Remove ${type.name}`}
          className="h-8 w-8 p-0 text-muted-foreground hover:text-destructive"
        >
          <X className="h-4 w-4" />
        </Button>
      )}
    </div>
  );
}
