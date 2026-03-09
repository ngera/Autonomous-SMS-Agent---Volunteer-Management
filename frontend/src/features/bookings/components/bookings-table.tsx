import { useNavigate } from "react-router-dom";
import { DataTable, type Column } from "@/components/shared/data-table";
import { StatusBadge } from "@/components/shared/status-badge";
import { formatDateTime, formatPhone, formatCurrency } from "@/lib/utils";
import type { BookingResponse } from "@/types/api";

interface BookingsTableProps {
  data: BookingResponse[];
  isLoading: boolean;
}

const columns: Column<BookingResponse>[] = [
  {
    key: "scheduled_at",
    header: "Date / Time",
    render: (b) => formatDateTime(b.scheduled_at),
  },
  {
    key: "contact_phone",
    header: "Customer",
    render: (b) => formatPhone(b.contact_phone),
  },
  {
    key: "status",
    header: "Status",
    render: (b) => <StatusBadge type="booking" value={b.status} />,
  },
  {
    key: "price",
    header: "Price",
    render: (b) => formatCurrency(b.price_at_booking),
    className: "text-right",
  },
];

export function BookingsTable({ data, isLoading }: BookingsTableProps) {
  const navigate = useNavigate();

  return (
    <DataTable
      columns={columns}
      data={data}
      isLoading={isLoading}
      emptyMessage="No bookings found."
      onRowClick={(b) => navigate(`/bookings/${b.id}`)}
    />
  );
}
