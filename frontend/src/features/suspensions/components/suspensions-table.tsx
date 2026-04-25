import { DataTable, type Column } from "@/components/shared/data-table";
import { StatusBadge } from "@/components/shared/status-badge";
import { formatDateTime, formatPhone } from "@/lib/utils";
import type { SuspensionResponse } from "@/types/api";

interface SuspensionsTableProps {
  suspensions: SuspensionResponse[];
  isLoading: boolean;
  onSelect: (s: SuspensionResponse) => void;
}

const columns: Column<SuspensionResponse>[] = [
  {
    key: "customer",
    header: "Volunteer",
    render: (s) => (
      <div>
        {s.contact_name && <div className="font-medium">{s.contact_name}</div>}
        <div className="text-xs text-muted-foreground">{formatPhone(s.contact_phone)}</div>
      </div>
    ),
  },
  {
    key: "type",
    header: "Type",
    render: (s) => <StatusBadge type="suspension" value={s.suspension_type} />,
  },
  { key: "reason", header: "Reason", render: (s) => s.reason },
  {
    key: "message",
    header: "Triggering Message",
    render: (s) =>
      s.triggering_message ? (
        <span className="text-xs italic text-muted-foreground max-w-48 truncate block">
          &ldquo;{s.triggering_message}&rdquo;
        </span>
      ) : (
        <span className="text-xs text-muted-foreground">—</span>
      ),
  },
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
