import { useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { DataTable, type Column } from "@/components/shared/data-table";
import { StatusBadge } from "@/components/shared/status-badge";
import { Badge } from "@/components/ui/badge";
import { formatTimeAgo } from "@/lib/utils";
import { ContactStatus, AVAILABILITY_OPTIONS } from "@/types/enums";
import {
  useAppointmentTypes,
  useMultiTenantAppointmentTypes,
} from "@/features/appointment-types/hooks/use-appointment-types";
import type { CustomerResponse, CustomerWithTenant } from "@/types/api";
import { VolunteerAvatar } from "./volunteer-avatar";

function formatHoursShort(minutes: number): string {
  if (!minutes || minutes <= 0) return "0h";
  const h = Math.round(minutes / 60);
  return `${h.toLocaleString()}h`;
}

const SLOT_SHORT = Object.fromEntries(
  AVAILABILITY_OPTIONS.map((o) => [o.value, o.short])
) as Record<string, string>;

interface CustomersTableProps {
  data: CustomerResponse[] | CustomerWithTenant[];
  isLoading: boolean;
  showTenantColumn?: boolean;
}

const tenantColumn: Column<CustomerResponse> = {
  key: "tenant",
  header: "tenant",
  render: (c) => (
    <span className="text-sm">
      {(c as CustomerWithTenant).tenant_name || "—"}
    </span>
  ),
};

export function CustomersTable({
  data,
  isLoading,
  showTenantColumn,
}: CustomersTableProps) {
  const navigate = useNavigate();
  const { data: singleTenantTypes } = useAppointmentTypes();

  // In multi-tenant mode the active-tenant single fetch is disabled, so derive the
  // tenants visible in `data` and fetch types for each so service names resolve
  // across tenants. In single-tenant mode `multiTenantIds` is empty and no extra
  // requests fire.
  const multiTenantIds = useMemo(() => {
    const set = new Set<string>();
    for (const c of data) {
      const t = (c as CustomerWithTenant).tenant_id;
      if (t) set.add(t);
    }
    return Array.from(set);
  }, [data]);
  const { data: multiTenantTypes } = useMultiTenantAppointmentTypes(multiTenantIds);

  const typeMap = useMemo(() => {
    const map: Record<string, string> = {};
    for (const t of singleTenantTypes ?? []) map[t.id] = t.name;
    for (const t of multiTenantTypes ?? []) map[t.id] = t.name;
    return map;
  }, [singleTenantTypes, multiTenantTypes]);

  const baseColumns: Column<CustomerResponse>[] = [
    {
      key: "name",
      header: "name",
      render: (c) => (
        <div className="flex min-w-0 items-center gap-3">
          <VolunteerAvatar name={c.name} phone={c.phone} />
          <div className="min-w-0">
            <div className="flex items-center gap-2 truncate font-medium">
              <span className="truncate">{c.name || c.phone}</span>
              {c.background_check_required && (
                <Badge variant="destructive" className="h-5 text-[10px]">
                  bg check
                </Badge>
              )}
            </div>
            {c.email && (
              <p className="truncate text-xs text-muted-foreground">{c.email}</p>
            )}
          </div>
        </div>
      ),
    },
    {
      key: "services",
      header: "services",
      render: (c) => {
        if (c.all_services_enabled) {
          return (
            <Badge variant="default" className="text-xs">
              All services
            </Badge>
          );
        }
        const ids = c.preferred_appointment_type_ids ?? [];
        if (ids.length === 0) {
          return (
            <span className="text-xs italic text-amber-600">None assigned</span>
          );
        }
        return (
          <div className="flex flex-wrap gap-1">
            {ids.map((id) => (
              <Badge key={id} variant="secondary" className="text-xs">
                {typeMap[id] ?? "Unknown"}
              </Badge>
            ))}
          </div>
        );
      },
    },
    {
      key: "availability",
      header: "availability",
      render: (c) => {
        const slots = c.availability ?? [];
        if (slots.length === 0) {
          return <span className="text-xs text-muted-foreground">—</span>;
        }
        return (
          <div className="flex flex-wrap gap-1">
            {slots.map((s) => (
              <span
                key={s}
                className="rounded bg-muted px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground"
              >
                {SLOT_SHORT[s] ?? s}
              </span>
            ))}
          </div>
        );
      },
    },
    {
      key: "hours",
      header: "hours",
      className: "text-right",
      render: (c) => (
        <span className="tabular-nums text-sm font-medium">
          {formatHoursShort(c.total_minutes ?? 0)}
        </span>
      ),
    },
    {
      key: "consent",
      header: "consent",
      render: (c) =>
        c.consent_status ? (
          <StatusBadge type="consent" value={c.consent_status} />
        ) : (
          <span className="text-muted-foreground">—</span>
        ),
    },
    {
      key: "added",
      header: "added",
      render: (c) => (
        <span className="text-sm text-muted-foreground">
          {formatTimeAgo(c.created_at)}
        </span>
      ),
    },
    {
      key: "status",
      header: "status",
      render: (c) => {
        const status = c.status;
        const cls =
          status === ContactStatus.ACTIVE
            ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300"
            : status === ContactStatus.SUSPENDED
              ? "bg-amber-100 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300"
              : "bg-rose-100 text-rose-800 dark:bg-rose-950/60 dark:text-rose-300";
        return (
          <span
            className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${cls}`}
          >
            {status === ContactStatus.ACTIVE
              ? "Active"
              : status === ContactStatus.SUSPENDED
                ? "Suspended"
                : "Banned"}
          </span>
        );
      },
    },
  ];

  const columns = showTenantColumn
    ? [tenantColumn, ...baseColumns]
    : baseColumns;

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
