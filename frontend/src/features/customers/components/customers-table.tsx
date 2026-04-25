import { useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { DataTable, type Column } from "@/components/shared/data-table";
import { StatusBadge } from "@/components/shared/status-badge";
import { Badge } from "@/components/ui/badge";
import { formatPhone, formatDate } from "@/lib/utils";
import { ContactStatus } from "@/types/enums";
import { useAppointmentTypes } from "@/features/appointment-types/hooks/use-appointment-types";
import type { CustomerResponse, CustomerWithTenant } from "@/types/api";

interface CustomersTableProps {
  data: CustomerResponse[] | CustomerWithTenant[];
  isLoading: boolean;
  showTenantColumn?: boolean;
}

const tenantColumn: Column<CustomerResponse> = {
  key: "tenant",
  header: "Tenant",
  render: (c) => (c as CustomerWithTenant).tenant_name || "—",
};

export function CustomersTable({
  data,
  isLoading,
  showTenantColumn,
}: CustomersTableProps) {
  const navigate = useNavigate();
  const { data: appointmentTypes } = useAppointmentTypes();
  const typeMap = useMemo(() => {
    const map: Record<string, string> = {};
    for (const t of appointmentTypes ?? []) map[t.id] = t.name;
    return map;
  }, [appointmentTypes]);

  const baseColumns: Column<CustomerResponse>[] = useMemo(() => [
    {
      key: "phone",
      header: "Phone",
      render: (c) => formatPhone(c.phone),
    },
    {
      key: "name",
      header: "Name",
      render: (c) => (
        <span className="flex items-center gap-1.5">
          {c.name || "—"}
          {c.status === ContactStatus.SUSPENDED && (
            <span className="inline-flex items-center rounded-full bg-red-100 px-1.5 py-0.5 text-[10px] font-medium text-red-700">Suspended</span>
          )}
          {c.status === ContactStatus.BANNED && (
            <span className="inline-flex items-center rounded-full bg-red-200 px-1.5 py-0.5 text-[10px] font-medium text-red-900">Banned</span>
          )}
        </span>
      ),
    },
    {
      key: "services",
      header: "Services",
      render: (c) => {
        if (c.all_services_enabled) {
          return <Badge variant="default" className="text-xs">All Services</Badge>;
        }
        const ids = c.preferred_appointment_type_ids;
        if (!ids || ids.length === 0) {
          return <span className="text-xs text-amber-600 italic">None assigned</span>;
        }
        return (
          <div className="flex flex-wrap gap-1">
            {ids.map((id) => (
              <Badge key={id} variant="secondary" className="text-xs">
                {typeMap[id] || id.slice(0, 8)}
              </Badge>
            ))}
          </div>
        );
      },
    },
    {
      key: "consent",
      header: "Consent",
      render: (c) =>
        c.consent_status ? (
          <StatusBadge type="consent" value={c.consent_status} />
        ) : (
          <span className="text-muted-foreground">—</span>
        ),
    },
    {
      key: "created",
      header: "Created",
      render: (c) => formatDate(c.created_at),
    },
  ], [typeMap]);

  const columns = useMemo(
    () => (showTenantColumn ? [tenantColumn, ...baseColumns] : baseColumns),
    [showTenantColumn, baseColumns]
  );

  return (
    <DataTable
      columns={columns}
      data={data}
      isLoading={isLoading}
      emptyMessage="No volunteers found."
      onRowClick={(c) =>
        navigate(`/customers/${encodeURIComponent(c.phone)}`)
      }
    />
  );
}
