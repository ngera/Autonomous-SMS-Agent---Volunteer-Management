import { useNavigate } from "react-router-dom";
import { DataTable, type Column } from "@/components/shared/data-table";
import { StatusBadge } from "@/components/shared/status-badge";
import { formatDateTime, formatPhone } from "@/lib/utils";
import type { TodaysBooking } from "@/types/api";
import type { BookingStatus } from "@/types/enums";

interface TodaysBookingsTableProps {
  data?: TodaysBooking[];
  isLoading: boolean;
}

const columns: Column<TodaysBooking>[] = [
  {
    key: "time",
    header: "Time",
    render: (b) => formatDateTime(b.scheduled_at),
  },
  {
    key: "customer",
    header: "Volunteer",
    render: (b) => b.contact_name || formatPhone(b.contact_phone),
  },
  {
    key: "type",
    header: "Type",
    render: (b) => b.appointment_type_name,
  },
  {
    key: "status",
    header: "Status",
    render: (b) => (
      <StatusBadge type="booking" value={b.status as BookingStatus} />
    ),
  },
];

export function TodaysBookingsTable({
  data,
  isLoading,
}: TodaysBookingsTableProps) {
  const navigate = useNavigate();

  return (
    <DataTable
      columns={columns}
      data={data ?? []}
      isLoading={isLoading}
      skeletonRows={3}
      emptyMessage="No bookings scheduled for today."
      onRowClick={(b) => navigate(`/bookings/${b.id}`)}
    />
  );
}
