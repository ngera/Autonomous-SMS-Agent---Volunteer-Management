import { useState } from "react";
import { DataTable, type Column } from "@/components/shared/data-table";
import { StatusBadge } from "@/components/shared/status-badge";
import { Pagination } from "@/components/shared/pagination";
import { formatDate, formatDateTime } from "@/lib/utils";
import type { ReminderResponse } from "@/types/api";
import { useReminderHistory } from "../hooks/use-reminders";

const columns: Column<ReminderResponse>[] = [
  { key: "phone", header: "Phone", render: (r) => r.contact_phone },
  { key: "scheduled", header: "Scheduled", render: (r) => formatDate(r.scheduled_for) },
  {
    key: "sent",
    header: "Sent At",
    render: (r) => (r.sent_at ? formatDateTime(r.sent_at) : "—"),
  },
  {
    key: "status",
    header: "Status",
    render: (r) => <StatusBadge type="reminder" value={r.status} />,
  },
  {
    key: "reason",
    header: "Skip Reason",
    render: (r) => r.skip_reason || "—",
  },
];

export function ReminderHistoryTable() {
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const { data, isLoading } = useReminderHistory(page, pageSize);

  return (
    <div className="space-y-3">
      <DataTable
        columns={columns}
        data={data?.items ?? []}
        isLoading={isLoading}
        emptyMessage="No reminder history."
      />
      <Pagination
        page={page}
        pageSize={pageSize}
        total={data?.total ?? 0}
        onPageChange={setPage}
      />
    </div>
  );
}
