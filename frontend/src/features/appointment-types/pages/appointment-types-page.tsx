import { useEffect, useMemo, useRef, useState } from "react";
import type { KeyboardEvent } from "react";
import { Plus, Download, Upload, X } from "lucide-react";
import { PageHeader } from "@/components/shared/page-header";
import { DataTable, type Column } from "@/components/shared/data-table";
import { ComboboxPopup } from "@/components/shared/combobox-popup";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { formatCurrency } from "@/lib/utils";
import { useAuth } from "@/hooks/use-auth";
import { AdminRole } from "@/types/enums";
import type { AppointmentTypeResponse } from "@/types/api";
import {
  useAppointmentTypes,
  useCreateAppointmentType,
  useUpdateAppointmentType,
  useDeleteAppointmentType,
} from "../hooks/use-appointment-types";
import { AppointmentTypeForm } from "../components/appointment-type-form";
import { RelatedServicesPanel } from "../components/related-services-panel";
import { CsvImportDialog } from "../components/csv-import-dialog";
import { appointmentTypesToCsv, downloadCsv } from "../lib/csv";

const CATEGORY_LIST_ID = "appointment-types-category-listbox";
const categoryOptionId = (i: number) => `appointment-types-category-opt-${i}`;

export function AppointmentTypesPage() {
  const { hasRole } = useAuth();
  const canEdit = hasRole(AdminRole.MANAGER);
  const types = useAppointmentTypes();
  const createType = useCreateAppointmentType();
  const updateType = useUpdateAppointmentType();
  const deleteType = useDeleteAppointmentType();

  const [showForm, setShowForm] = useState(false);
  const [showImport, setShowImport] = useState(false);
  const [editItem, setEditItem] = useState<AppointmentTypeResponse | null>(null);
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const [selectedTypeId, setSelectedTypeId] = useState<string | null>(null);

  const [categoryQuery, setCategoryQuery] = useState("");
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [showCategoryDropdown, setShowCategoryDropdown] = useState(false);
  const [categoryActiveIndex, setCategoryActiveIndex] = useState(0);
  const categoryRef = useRef<HTMLDivElement>(null);

  const allTypes = types.data ?? [];

  const allCategories = useMemo(() => {
    const set = new Set<string>();
    for (const t of allTypes) set.add(t.category);
    return Array.from(set).sort((a, b) => a.localeCompare(b));
  }, [allTypes]);

  const filteredCategories = useMemo(() => {
    const q = categoryQuery.trim().toLowerCase();
    if (!q) return allCategories;
    return allCategories.filter((c) => c.toLowerCase().includes(q));
  }, [allCategories, categoryQuery]);

  const filteredTypes = useMemo(() => {
    const rows =
      selectedCategory === null
        ? allTypes
        : allTypes.filter((t) => t.category === selectedCategory);
    return [...rows].sort(
      (a, b) =>
        a.category.localeCompare(b.category) || a.name.localeCompare(b.name)
    );
  }, [allTypes, selectedCategory]);

  // If the active filter no longer exists (e.g. last type in that category
  // was deleted), drop the selection.
  useEffect(() => {
    if (selectedCategory !== null && !allCategories.includes(selectedCategory)) {
      setSelectedCategory(null);
    }
  }, [allCategories, selectedCategory]);

  useEffect(() => setCategoryActiveIndex(0), [
    categoryQuery,
    showCategoryDropdown,
    allCategories.length,
  ]);

  useEffect(() => {
    if (showCategoryDropdown) {
      document
        .getElementById(categoryOptionId(categoryActiveIndex))
        ?.scrollIntoView({ block: "nearest" });
    }
  }, [categoryActiveIndex, showCategoryDropdown]);

  function pickCategory(c: string) {
    setSelectedCategory(c);
    setCategoryQuery("");
    setShowCategoryDropdown(false);
  }

  function clearCategory() {
    setSelectedCategory(null);
    setCategoryQuery("");
  }

  const categoryListOpen =
    showCategoryDropdown && selectedCategory === null && allCategories.length > 0;

  function handleCategoryKey(e: KeyboardEvent<HTMLInputElement>) {
    switch (e.key) {
      case "ArrowDown":
        e.preventDefault();
        if (!categoryListOpen) {
          setShowCategoryDropdown(true);
          return;
        }
        if (filteredCategories.length === 0) return;
        setCategoryActiveIndex((p) => (p + 1) % filteredCategories.length);
        return;
      case "ArrowUp":
        e.preventDefault();
        if (!categoryListOpen) {
          setShowCategoryDropdown(true);
          return;
        }
        if (filteredCategories.length === 0) return;
        setCategoryActiveIndex(
          (p) => (p - 1 + filteredCategories.length) % filteredCategories.length
        );
        return;
      case "Home":
        if (!categoryListOpen || filteredCategories.length === 0) return;
        e.preventDefault();
        setCategoryActiveIndex(0);
        return;
      case "End":
        if (!categoryListOpen || filteredCategories.length === 0) return;
        e.preventDefault();
        setCategoryActiveIndex(filteredCategories.length - 1);
        return;
      case "Enter":
        if (!categoryListOpen) return;
        if (categoryActiveIndex < 0 || categoryActiveIndex >= filteredCategories.length) return;
        e.preventDefault();
        pickCategory(filteredCategories[categoryActiveIndex]);
        return;
      case "Escape":
        if (!categoryListOpen) return;
        e.preventDefault();
        setShowCategoryDropdown(false);
        return;
      case "Tab":
        setShowCategoryDropdown(false);
        return;
    }
  }

  function handleExport() {
    const rows = filteredTypes;
    const csv = appointmentTypesToCsv(rows);
    const stamp = new Date().toISOString().slice(0, 10);
    const suffix = selectedCategory
      ? `-${selectedCategory.toLowerCase().replace(/\s+/g, "-")}`
      : "";
    downloadCsv(`appointment-types${suffix}-${stamp}.csv`, csv);
  }

  const columns: Column<AppointmentTypeResponse>[] = [
    { key: "name", header: "Name", render: (t) => t.name },
    {
      key: "category",
      header: "Category",
      render: (t) => t.category,
    },
    {
      key: "duration",
      header: "Duration",
      render: (t) => `${t.duration_minutes} min`,
    },
    {
      key: "price",
      header: "Price",
      render: (t) => formatCurrency(t.price),
      className: "text-right",
    },
    {
      key: "active",
      header: "Active",
      render: (t) =>
        canEdit ? (
          <Switch
            checked={t.is_active}
            onCheckedChange={(checked) =>
              updateType.mutate({ id: t.id, body: { is_active: checked } })
            }
          />
        ) : (
          <span>{t.is_active ? "Yes" : "No"}</span>
        ),
    },
    ...(canEdit
      ? [
          {
            key: "actions" as const,
            header: "",
            render: (t: AppointmentTypeResponse) => (
              <div className="flex gap-1">
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={(e) => {
                    e.stopPropagation();
                    setEditItem(t);
                    setShowForm(true);
                  }}
                >
                  Edit
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  className="text-destructive"
                  onClick={(e) => {
                    e.stopPropagation();
                    setDeleteId(t.id);
                  }}
                >
                  Archive
                </Button>
              </div>
            ),
          },
        ]
      : []),
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Service Types"
        description="Manage services offered to customers."
        actions={
          <div className="flex gap-2">
            <Button
              variant="outline"
              onClick={handleExport}
              disabled={!types.data || filteredTypes.length === 0}
            >
              <Download className="mr-2 h-4 w-4" />
              Export CSV
            </Button>
            {canEdit && (
              <>
                <Button variant="outline" onClick={() => setShowImport(true)}>
                  <Upload className="mr-2 h-4 w-4" />
                  Import CSV
                </Button>
                <Button
                  onClick={() => {
                    setEditItem(null);
                    setShowForm(true);
                  }}
                >
                  <Plus className="mr-2 h-4 w-4" />
                  Add Type
                </Button>
              </>
            )}
          </div>
        }
      />

      <div className="flex flex-wrap items-end gap-3">
        <div className="space-y-1 min-w-[16rem] max-w-sm flex-1">
          <Label
            htmlFor="appointment-types-category-input"
            className="text-xs text-muted-foreground"
          >
            Filter by category
          </Label>
          <div className="relative" ref={categoryRef}>
            <Input
              id="appointment-types-category-input"
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
              onKeyDown={handleCategoryKey}
              placeholder={
                allCategories.length === 0
                  ? "No categories"
                  : "Search categories..."
              }
              className={selectedCategory !== null ? "pr-8" : ""}
              disabled={allCategories.length === 0}
            />
            {selectedCategory !== null && (
              <button
                type="button"
                onClick={clearCategory}
                aria-label="Clear category filter"
                className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
              >
                <X className="h-4 w-4" />
              </button>
            )}
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
        </div>
        <p className="text-xs text-muted-foreground pb-1">
          Showing {filteredTypes.length}
          {selectedCategory ? ` of ${allTypes.length}` : ""}
        </p>
      </div>

      <DataTable
        columns={columns}
        data={filteredTypes}
        isLoading={types.isLoading}
        emptyMessage={
          selectedCategory
            ? `No service types in "${selectedCategory}".`
            : "No appointment types configured."
        }
        onRowClick={(t) =>
          setSelectedTypeId(selectedTypeId === t.id ? null : t.id)
        }
      />

      {selectedTypeId && types.data && (
        <RelatedServicesPanel
          typeId={selectedTypeId}
          allTypes={types.data}
        />
      )}

      <AppointmentTypeForm
        open={showForm}
        onOpenChange={setShowForm}
        editItem={editItem}
        isLoading={createType.isPending || updateType.isPending}
        onSubmit={(data) => {
          if (editItem) {
            updateType.mutate(
              { id: editItem.id, body: data },
              { onSuccess: () => setShowForm(false) }
            );
          } else {
            createType.mutate(data, {
              onSuccess: () => setShowForm(false),
            });
          }
        }}
      />

      <CsvImportDialog open={showImport} onOpenChange={setShowImport} />

      <ConfirmDialog
        open={!!deleteId}
        onOpenChange={(open) => !open && setDeleteId(null)}
        title="Archive Service Type"
        description="This will hide the type from the chatbot but preserve historical bookings."
        confirmLabel="Archive"
        variant="destructive"
        isLoading={deleteType.isPending}
        onConfirm={() => {
          if (deleteId) {
            deleteType.mutate(deleteId, {
              onSuccess: () => setDeleteId(null),
            });
          }
        }}
      />
    </div>
  );
}
