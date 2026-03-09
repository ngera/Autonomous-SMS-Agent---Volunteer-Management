import { useState } from "react";
import { Plus } from "lucide-react";
import { PageHeader } from "@/components/shared/page-header";
import { DataTable, type Column } from "@/components/shared/data-table";
import { Button } from "@/components/ui/button";
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

export function AppointmentTypesPage() {
  const { hasRole } = useAuth();
  const canEdit = hasRole(AdminRole.MANAGER);
  const types = useAppointmentTypes();
  const createType = useCreateAppointmentType();
  const updateType = useUpdateAppointmentType();
  const deleteType = useDeleteAppointmentType();

  const [showForm, setShowForm] = useState(false);
  const [editItem, setEditItem] = useState<AppointmentTypeResponse | null>(null);
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const [selectedTypeId, setSelectedTypeId] = useState<string | null>(null);

  const columns: Column<AppointmentTypeResponse>[] = [
    { key: "name", header: "Name", render: (t) => t.name },
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
      key: "recurrence",
      header: "Recurrence",
      render: (t) =>
        t.recurrence_weeks_default
          ? `${t.recurrence_weeks_default} weeks`
          : "—",
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
        title="Appointment Types"
        description="Manage services offered to customers."
        actions={
          canEdit ? (
            <Button
              onClick={() => {
                setEditItem(null);
                setShowForm(true);
              }}
            >
              <Plus className="mr-2 h-4 w-4" />
              Add Type
            </Button>
          ) : undefined
        }
      />

      <DataTable
        columns={columns}
        data={types.data ?? []}
        isLoading={types.isLoading}
        emptyMessage="No appointment types configured."
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

      <ConfirmDialog
        open={!!deleteId}
        onOpenChange={(open) => !open && setDeleteId(null)}
        title="Archive Appointment Type"
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
