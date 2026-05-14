import { useState, useRef, useEffect, useMemo } from "react";
import type { KeyboardEvent } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowLeft, X } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PageHeader } from "@/components/shared/page-header";
import { ComboboxPopup } from "@/components/shared/combobox-popup";
import { formatPhone } from "@/lib/utils";
import { useCreateBooking, useAvailableSlots } from "../hooks/use-bookings";
import { useAppointmentTypes } from "@/features/appointment-types/hooks/use-appointment-types";
import { useCustomers } from "@/features/customers/hooks/use-customers";

const NULL_CATEGORY = "__none__";

const CUSTOMER_LIST_ID = "booking-customer-listbox";
const CATEGORY_LIST_ID = "booking-category-listbox";
const TYPE_LIST_ID = "booking-type-listbox";

const customerOptionId = (i: number) => `booking-customer-opt-${i}`;
const categoryOptionId = (i: number) => `booking-category-opt-${i}`;
const typeOptionId = (i: number) => `booking-type-opt-${i}`;

interface KeyHandlerArgs<T> {
  open: boolean;
  setOpen: (v: boolean) => void;
  items: T[];
  activeIndex: number;
  setActiveIndex: (updater: (prev: number) => number) => void;
  onPick: (item: T) => void;
}

function handleComboKey<T>(
  e: KeyboardEvent<HTMLInputElement>,
  { open, setOpen, items, activeIndex, setActiveIndex, onPick }: KeyHandlerArgs<T>
) {
  switch (e.key) {
    case "ArrowDown":
      e.preventDefault();
      if (!open) {
        setOpen(true);
        return;
      }
      if (items.length === 0) return;
      setActiveIndex((prev) => (prev + 1) % items.length);
      return;
    case "ArrowUp":
      e.preventDefault();
      if (!open) {
        setOpen(true);
        return;
      }
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
      // Let focus move naturally; just collapse the popup.
      setOpen(false);
      return;
  }
}

function scrollOptionIntoView(id: string) {
  const el = document.getElementById(id);
  el?.scrollIntoView({ block: "nearest" });
}

export function BookingCreatePage() {
  const navigate = useNavigate();
  const createBooking = useCreateBooking();
  const appointmentTypes = useAppointmentTypes();

  const [customerSearch, setCustomerSearch] = useState("");
  const [phone, setPhone] = useState("");
  const [selectedCustomerLabel, setSelectedCustomerLabel] = useState("");
  const [showCustomerDropdown, setShowCustomerDropdown] = useState(false);
  const [customerActiveIndex, setCustomerActiveIndex] = useState(0);

  const [categoryQuery, setCategoryQuery] = useState("");
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [showCategoryDropdown, setShowCategoryDropdown] = useState(false);
  const [categoryActiveIndex, setCategoryActiveIndex] = useState(0);

  const [typeId, setTypeId] = useState("");
  const [typeQuery, setTypeQuery] = useState("");
  const [showTypeDropdown, setShowTypeDropdown] = useState(false);
  const [typeActiveIndex, setTypeActiveIndex] = useState(0);

  const [date, setDate] = useState("");
  const [selectedSlot, setSelectedSlot] = useState("");

  const customerRef = useRef<HTMLDivElement>(null);
  const categoryRef = useRef<HTMLDivElement>(null);
  const typeRef = useRef<HTMLDivElement>(null);

  const customers = useCustomers({
    search: customerSearch || undefined,
    page: 1,
    page_size: 10,
  });

  const slots = useAvailableSlots(date, typeId);
  const selectedType = appointmentTypes.data?.find((t) => t.id === typeId);

  const activeTypes = useMemo(
    () => (appointmentTypes.data ?? []).filter((t) => t.is_active),
    [appointmentTypes.data]
  );

  const categories = useMemo(() => {
    const set = new Set<string>();
    let hasUncat = false;
    for (const t of activeTypes) {
      if (t.category) set.add(t.category);
      else hasUncat = true;
    }
    const sorted = Array.from(set).sort((a, b) => a.localeCompare(b));
    if (hasUncat) sorted.push(NULL_CATEGORY);
    return sorted;
  }, [activeTypes]);

  const filteredCategories = useMemo(() => {
    const q = categoryQuery.trim().toLowerCase();
    if (!q) return categories;
    return categories.filter((c) =>
      (c === NULL_CATEGORY ? "uncategorized" : c.toLowerCase()).includes(q)
    );
  }, [categories, categoryQuery]);

  const typesInCategory = useMemo(() => {
    if (selectedCategory === null) return [];
    return activeTypes.filter((t) =>
      selectedCategory === NULL_CATEGORY ? !t.category : t.category === selectedCategory
    );
  }, [activeTypes, selectedCategory]);

  const filteredTypes = useMemo(() => {
    const q = typeQuery.trim().toLowerCase();
    if (!q) return typesInCategory;
    return typesInCategory.filter((t) => t.name.toLowerCase().includes(q));
  }, [typesInCategory, typeQuery]);

  const customerItems = customers.data?.items ?? [];

  // Reset highlight to the top whenever the visible list changes.
  useEffect(() => setCustomerActiveIndex(0), [customerSearch, showCustomerDropdown]);
  useEffect(() => setCategoryActiveIndex(0), [categoryQuery, showCategoryDropdown]);
  useEffect(
    () => setTypeActiveIndex(0),
    [typeQuery, showTypeDropdown, selectedCategory]
  );

  // Keep the highlighted option in view as the user arrows through the list.
  useEffect(() => {
    if (showCustomerDropdown) scrollOptionIntoView(customerOptionId(customerActiveIndex));
  }, [customerActiveIndex, showCustomerDropdown]);
  useEffect(() => {
    if (showCategoryDropdown) scrollOptionIntoView(categoryOptionId(categoryActiveIndex));
  }, [categoryActiveIndex, showCategoryDropdown]);
  useEffect(() => {
    if (showTypeDropdown) scrollOptionIntoView(typeOptionId(typeActiveIndex));
  }, [typeActiveIndex, showTypeDropdown]);

  // Outside-click handling lives inside <ComboboxPopup>.

  function categoryLabel(key: string): string {
    return key === NULL_CATEGORY ? "Uncategorized" : key;
  }

  function pickCustomer(c: { phone: string; name: string | null }) {
    setPhone(c.phone);
    setSelectedCustomerLabel(
      c.name ? `${c.name} (${formatPhone(c.phone)})` : formatPhone(c.phone)
    );
    setCustomerSearch("");
    setShowCustomerDropdown(false);
  }

  function pickCategory(key: string) {
    setSelectedCategory(key);
    setCategoryQuery("");
    setShowCategoryDropdown(false);
    setTypeId("");
    setTypeQuery("");
    setSelectedSlot("");
  }

  function clearCategory() {
    setSelectedCategory(null);
    setCategoryQuery("");
    setTypeId("");
    setTypeQuery("");
    setSelectedSlot("");
  }

  function pickType(id: string) {
    setTypeId(id);
    setTypeQuery("");
    setShowTypeDropdown(false);
    setSelectedSlot("");
  }

  function clearType() {
    setTypeId("");
    setTypeQuery("");
    setSelectedSlot("");
  }

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

  const customerListOpen =
    showCustomerDropdown && !!customerSearch && !selectedCustomerLabel;
  const categoryListOpen =
    showCategoryDropdown && selectedCategory === null && categories.length > 0;
  const typeListOpen =
    showTypeDropdown && !selectedType && selectedCategory !== null && typesInCategory.length > 0;

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

      <Card className="max-w-xl">
        <CardHeader>
          <CardTitle>New Booking</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2 relative" ref={customerRef}>
            <Label htmlFor="booking-customer-input">Customer</Label>
            <Input
              id="booking-customer-input"
              role="combobox"
              aria-autocomplete="list"
              aria-expanded={customerListOpen}
              aria-controls={CUSTOMER_LIST_ID}
              aria-activedescendant={
                customerListOpen && customerItems.length > 0
                  ? customerOptionId(customerActiveIndex)
                  : undefined
              }
              value={selectedCustomerLabel || customerSearch}
              onChange={(e) => {
                setCustomerSearch(e.target.value);
                setSelectedCustomerLabel("");
                setPhone("");
                setShowCustomerDropdown(true);
              }}
              onFocus={() => {
                if (customerSearch && !selectedCustomerLabel) setShowCustomerDropdown(true);
              }}
              onKeyDown={(e) =>
                handleComboKey(e, {
                  open: customerListOpen,
                  setOpen: setShowCustomerDropdown,
                  items: customerItems,
                  activeIndex: customerActiveIndex,
                  setActiveIndex: setCustomerActiveIndex,
                  onPick: pickCustomer,
                })
              }
              placeholder="Search by name or phone..."
            />
            <ComboboxPopup
              triggerRef={customerRef}
              open={customerListOpen}
              onRequestClose={() => setShowCustomerDropdown(false)}
              id={CUSTOMER_LIST_ID}
              className="rounded-md border bg-popover shadow-lg max-h-48 overflow-y-auto"
            >
              {customers.isLoading ? (
                <div className="p-3 text-sm text-muted-foreground">Searching...</div>
              ) : !customerItems.length ? (
                <div className="p-3 text-sm text-muted-foreground">No customers found</div>
              ) : (
                customerItems.map((c, i) => (
                  <button
                    key={c.phone}
                    id={customerOptionId(i)}
                    role="option"
                    aria-selected={i === customerActiveIndex}
                    type="button"
                    tabIndex={-1}
                    className={`w-full text-left px-3 py-2 text-sm flex justify-between items-center ${
                      i === customerActiveIndex ? "bg-accent" : "hover:bg-accent"
                    }`}
                    onMouseEnter={() => setCustomerActiveIndex(i)}
                    onClick={() => pickCustomer(c)}
                  >
                    <span className="font-medium">{c.name || "—"}</span>
                    <span className="text-muted-foreground">{formatPhone(c.phone)}</span>
                  </button>
                ))
              )}
            </ComboboxPopup>
          </div>

          <div className="space-y-2 relative" ref={categoryRef}>
            <Label htmlFor="booking-category-input">Category</Label>
            <div className="relative">
              <Input
                id="booking-category-input"
                role="combobox"
                aria-autocomplete="list"
                aria-expanded={categoryListOpen}
                aria-controls={CATEGORY_LIST_ID}
                aria-activedescendant={
                  categoryListOpen && filteredCategories.length > 0
                    ? categoryOptionId(categoryActiveIndex)
                    : undefined
                }
                value={
                  selectedCategory !== null
                    ? categoryLabel(selectedCategory)
                    : categoryQuery
                }
                onChange={(e) => {
                  setSelectedCategory(null);
                  setCategoryQuery(e.target.value);
                  setTypeId("");
                  setSelectedSlot("");
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
                  categories.length === 0
                    ? "No categories available"
                    : "Search categories..."
                }
                className={selectedCategory !== null ? "pr-8" : ""}
                disabled={categories.length === 0}
              />
              {selectedCategory !== null && (
                <button
                  type="button"
                  onClick={clearCategory}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                  aria-label="Clear category"
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
              className="rounded-md border bg-popover shadow-lg max-h-48 overflow-y-auto"
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
                    className={`w-full text-left px-3 py-2 text-sm ${
                      i === categoryActiveIndex ? "bg-accent" : "hover:bg-accent"
                    }`}
                    onMouseEnter={() => setCategoryActiveIndex(i)}
                    onClick={() => pickCategory(c)}
                  >
                    {categoryLabel(c)}
                  </button>
                ))
              )}
            </ComboboxPopup>
          </div>

          <div className="space-y-2 relative" ref={typeRef}>
            <Label htmlFor="booking-type-input">Service Type</Label>
            <div className="relative">
              <Input
                id="booking-type-input"
                role="combobox"
                aria-autocomplete="list"
                aria-expanded={typeListOpen}
                aria-controls={TYPE_LIST_ID}
                aria-activedescendant={
                  typeListOpen && filteredTypes.length > 0
                    ? typeOptionId(typeActiveIndex)
                    : undefined
                }
                value={
                  selectedType
                    ? `${selectedType.name} (${selectedType.duration_minutes}min)`
                    : typeQuery
                }
                onChange={(e) => {
                  setTypeId("");
                  setTypeQuery(e.target.value);
                  setSelectedSlot("");
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
                    onPick: (t) => pickType(t.id),
                  })
                }
                placeholder={
                  selectedCategory === null
                    ? "Choose a category first"
                    : typesInCategory.length === 0
                      ? "No services in this category"
                      : "Search services..."
                }
                className={selectedType ? "pr-8" : ""}
                disabled={selectedCategory === null || typesInCategory.length === 0}
              />
              {selectedType && (
                <button
                  type="button"
                  onClick={clearType}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                  aria-label="Clear service type"
                >
                  <X className="h-4 w-4" />
                </button>
              )}
            </div>
            <ComboboxPopup
              triggerRef={typeRef}
              open={typeListOpen}
              onRequestClose={() => setShowTypeDropdown(false)}
              id={TYPE_LIST_ID}
              className="rounded-md border bg-popover shadow-lg max-h-48 overflow-y-auto"
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
                    className={`w-full text-left px-3 py-2 text-sm ${
                      i === typeActiveIndex ? "bg-accent" : "hover:bg-accent"
                    }`}
                    onMouseEnter={() => setTypeActiveIndex(i)}
                    onClick={() => pickType(t.id)}
                  >
                    {t.name} ({t.duration_minutes}min)
                  </button>
                ))
              )}
            </ComboboxPopup>
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
