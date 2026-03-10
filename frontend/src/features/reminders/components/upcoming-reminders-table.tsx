import { useState } from "react";
import { XCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { DataTable, type Column } from "@/components/shared/data-table";
import { StatusBadge } from "@/components/shared/status-badge";
import { formatDate } from "@/lib/utils";
import type { ReminderResponse } from "@/types/api";
import { useUpcomingReminders, useCancelReminder } from "../hooks/use-reminders";
import { CancelReminderDialog } from "./cancel-reminder-dialog";

interface UpcomingRemindersTableProps {
  canEdit: boolean;
}

export function UpcomingRemindersTable({ canEdit }: UpcomingRemindersTableProps) {
  const { data, isLoading } = useUpcomingReminders();
  const cancelReminder = useCancelReminder();
  const [cancelTarget, setCancelTarget] = useState<ReminderResponse | null>(null);

  const columns: Column<ReminderResponse>[] = [
    { key: "phone", header: "Phone", render: (r) => r.contact_phone },
    { key: "scheduled", header: "Scheduled For", render: (r) => formatDate(r.scheduled_for) },
    {
      key: "status",
      header: "Status",
      render: (r) => <StatusBadge type="reminder" value={r.status} />,
    },
    ...(canEdit
      ? [
          {
            key: "actions" as const,
            header: "",
            render: (r: ReminderResponse) => (
              <Button
                size="icon"
                variant="ghost"
                onClick={() => setCancelTarget(r)}
              >
                <XCircle className="h-4 w-4 text-destructive" />
              </Button>
            ),
            className: "w-12",
          },
        ]
      : []),
  ];

  return (
    <>
      <DataTable
        columns={columns}
        data={data?.items ?? []}
        isLoading={isLoading}
        emptyMessage="No upcoming reminders."
      />
      <CancelReminderDialog
        reminder={cancelTarget}
        onClose={() => setCancelTarget(null)}
        onConfirm={(id, reason) =>
          cancelReminder.mutate(
            { id, body: { reason } },
            { onSuccess: () => setCancelTarget(null) }
          )
        }
        isPending={cancelReminder.isPending}
      />
    </>
  );
}
