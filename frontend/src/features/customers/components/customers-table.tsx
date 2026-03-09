import { useNavigate } from "react-router-dom";
import { DataTable, type Column } from "@/components/shared/data-table";
import { StatusBadge } from "@/components/shared/status-badge";
import { formatPhone, formatDate } from "@/lib/utils";
import type { CustomerResponse } from "@/types/api";

interface CustomersTableProps {
  data: CustomerResponse[];
  isLoading: boolean;
}

const columns: Column<CustomerResponse>[] = [
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

export function CustomersTable({ data, isLoading }: CustomersTableProps) {
  const navigate = useNavigate();

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
