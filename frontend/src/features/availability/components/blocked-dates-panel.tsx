import { useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { DataTable, type Column } from "@/components/shared/data-table";
import { formatDate } from "@/lib/utils";
import type { BlockedDateResponse } from "@/types/api";
import {
  useBlockedDates,
  useCreateBlockedDate,
  useDeleteBlockedDate,
} from "../hooks/use-availability";

interface BlockedDatesPanelProps {
  canEdit: boolean;
}

const columns = (
  onDelete: (id: string) => void,
  canEdit: boolean
): Column<BlockedDateResponse>[] => [
  { key: "from", header: "From", render: (b) => formatDate(b.date_from) },
  { key: "to", header: "To", render: (b) => formatDate(b.date_to) },
  { key: "reason", header: "Reason", render: (b) => b.reason || "—" },
  ...(canEdit
    ? [
        {
          key: "actions" as const,
          header: "",
          render: (b: BlockedDateResponse) => (
            <Button size="icon" variant="ghost" onClick={() => onDelete(b.id)}>
              <Trash2 className="h-4 w-4 text-destructive" />
            </Button>
          ),
          className: "w-12",
        },
      ]
    : []),
];

export function BlockedDatesPanel({ canEdit }: BlockedDatesPanelProps) {
  const blocked = useBlockedDates();
  const createBlocked = useCreateBlockedDate();
  const deleteBlocked = useDeleteBlockedDate();

  const [showAdd, setShowAdd] = useState(false);
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [reason, setReason] = useState("");

  function handleAdd() {
    if (!dateFrom || !dateTo) return;
    const body = {
      date_from: dateFrom,
      date_to: dateTo,
      reason: reason || undefined,
    };
    const onSuccess = () => {
      setShowAdd(false);
      setDateFrom("");
      setDateTo("");
      setReason("");
    };
    const showError = (err: unknown) => {
      const detail =
        (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail ??
        (err as Error)?.message ??
        "Failed to add blocked date";
      alert(
        `Could not add blocked date: ${typeof detail === "string" ? detail : JSON.stringify(detail)}`
      );
    };

    function submit(force: boolean) {
      createBlocked.mutate({ body, force }, { onSuccess, onError: handleError });
    }

    function handleError(err: unknown) {
      const detail = (err as { response?: { data?: { detail?: unknown } } })
        ?.response?.data?.detail;
      if (
        detail &&
        typeof detail === "object" &&
        (detail as { code?: string }).code === "events_inside_block"
      ) {
        const events = (
          (detail as {
            events?: Array<{ date: string; label: string | null; start_time: string; end_time: string }>;
          }).events ?? []
        )
          .map(
            (e) =>
              `• ${e.date} ${e.start_time}–${e.end_time}${e.label ? ` "${e.label}"` : ""}`
          )
          .join("\n");
        const ok = window.confirm(
          `${(detail as { message: string }).message}\n\nEvents inside the range:\n${events}\n\nAdd the block anyway?`
        );
        if (ok) submit(true);
        return;
      }
      showError(err);
    }

    submit(false);
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>Blocked Dates</CardTitle>
        {canEdit && (
          <Button size="sm" variant="outline" onClick={() => setShowAdd(!showAdd)}>
            <Plus className="mr-1 h-3 w-3" />
            Add
          </Button>
        )}
      </CardHeader>
      <CardContent className="space-y-4">
        {showAdd && (
          <div className="flex flex-wrap items-end gap-3 rounded-md border p-3">
            <div className="space-y-1">
              <Label className="text-xs">From</Label>
              <Input
                type="date"
                value={dateFrom}
                onChange={(e) => setDateFrom(e.target.value)}
                className="w-40 h-8"
              />
            </div>
            <div className="space-y-1">
              <Label className="text-xs">To</Label>
              <Input
                type="date"
                value={dateTo}
                onChange={(e) => setDateTo(e.target.value)}
                className="w-40 h-8"
              />
            </div>
            <div className="space-y-1">
              <Label className="text-xs">Reason</Label>
              <Input
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="Holiday, etc."
                className="w-48 h-8"
              />
            </div>
            <Button size="sm" onClick={handleAdd} disabled={createBlocked.isPending}>
              {createBlocked.isPending ? "Adding..." : "Add"}
            </Button>
          </div>
        )}
        <DataTable
          columns={columns((id) => deleteBlocked.mutate(id), canEdit)}
          data={blocked.data ?? []}
          isLoading={blocked.isLoading}
          emptyMessage="No blocked dates."
        />
      </CardContent>
    </Card>
  );
}
