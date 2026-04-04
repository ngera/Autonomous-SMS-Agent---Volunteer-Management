import { useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { DataTable, type Column } from "@/components/shared/data-table";
import { StatusBadge } from "@/components/shared/status-badge";
import { formatPhone, formatDate } from "@/lib/utils";
import { ContactSex } from "@/types/enums";
import type { CustomerResponse, CustomerWithTenant } from "@/types/api";

const SEX_LABELS: Record<string, string> = {
  [ContactSex.MALE]: "Male",
  [ContactSex.FEMALE]: "Female",
  [ContactSex.NON_BINARY]: "Non-binary",
  [ContactSex.PREFER_NOT_TO_SAY]: "Prefer not to say",
};

interface CustomersTableProps {
  data: CustomerResponse[] | CustomerWithTenant[];
  isLoading: boolean;
  showTenantColumn?: boolean;
}

const baseColumns: Column<CustomerResponse>[] = [
  {
    key: "phone",
    header: "Phone",
    render: (c) => formatPhone(c.phone),
  },
  {
    key: "name",
    header: "Name",
    render: (c) => c.name || "—",
  },
  {
    key: "email",
    header: "Email",
    render: (c) => c.email || "—",
  },
  {
    key: "sex",
    header: "Sex",
    render: (c) => (c.sex ? SEX_LABELS[c.sex] || c.sex : "—"),
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
];

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

  const columns = useMemo(
    () => (showTenantColumn ? [tenantColumn, ...baseColumns] : baseColumns),
    [showTenantColumn]
  );

  return (
    <DataTable
      columns={columns}
      data={data}
      isLoading={isLoading}
      emptyMessage="No customers found."
      onRowClick={(c) =>
        navigate(`/customers/${encodeURIComponent(c.phone)}`)
      }
    />
  );
}
