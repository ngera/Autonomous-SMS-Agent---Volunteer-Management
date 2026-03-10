import { DataTable, type Column } from "@/components/shared/data-table";
import { StatusBadge } from "@/components/shared/status-badge";
import { formatDateTime } from "@/lib/utils";
import type { SuspensionResponse } from "@/types/api";

interface SuspensionsTableProps {
  suspensions: SuspensionResponse[];
  isLoading: boolean;
  onSelect: (s: SuspensionResponse) => void;
}

const columns: Column<SuspensionResponse>[] = [
  { key: "phone", header: "Phone", render: (s) => s.contact_phone },
  {
    key: "type",
    header: "Type",
    render: (s) => <StatusBadge type="suspension" value={s.suspension_type} />,
  },
  { key: "reason", header: "Reason", render: (s) => s.reason },
  {
    key: "suspended",
    header: "Suspended At",
    render: (s) => formatDateTime(s.suspended_at),
  },
  {
    key: "review",
    header: "Review",
    render: (s) =>
      s.review_decision ? (
        <StatusBadge type="review" value={s.review_decision} />
      ) : (
        <span className="text-xs text-amber-600 font-medium">Pending Review</span>
      ),
  },
];

export function SuspensionsTable({
  suspensions,
  isLoading,
  onSelect,
}: SuspensionsTableProps) {
  return (
    <DataTable
      columns={columns}
      data={suspensions}
      isLoading={isLoading}
      emptyMessage="No suspensions."
      onRowClick={onSelect}
    />
  );
}
