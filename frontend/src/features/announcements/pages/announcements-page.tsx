import { useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Megaphone, Plus, Trash2 } from "lucide-react";
import { format } from "date-fns";
import { AnnouncementForm } from "../components/announcement-form";
import {
  useAnnouncements,
  useCreateAnnouncement,
  useCancelAnnouncement,
  useBulkDeleteAnnouncements,
} from "../hooks/use-announcements";
import { AnnouncementStatus } from "@/types/enums";
import { useAppointmentTypes } from "@/features/appointment-types/hooks/use-appointment-types";
import type { AnnouncementResponse } from "@/types/api";
import { cn } from "@/lib/utils";

// Per-status copy for the delete-confirmation dialog. SENT/SENDING get
// a stronger warning since the SMSes are already out the door — the
// delete only removes the audit record, it can't recall messages.
const DELETE_COPY: Record<string, { title: string; description: string; confirm: string }> = {
  [AnnouncementStatus.SCHEDULED]: {
    title: "Cancel this scheduled announcement?",
    description: "The announcement will be removed before its scheduled send time. No SMS will go out.",
    confirm: "Cancel announcement",
  },
  [AnnouncementStatus.DRAFT]: {
    title: "Delete this draft?",
    description: "The draft will be permanently removed.",
    confirm: "Delete draft",
  },
  [AnnouncementStatus.SENDING]: {
    title: "Delete this announcement?",
    description: "Dispatch is in progress. Some recipients may still receive this SMS before the cancellation takes effect.",
    confirm: "Delete anyway",
  },
  [AnnouncementStatus.SENT]: {
    title: "Delete this announcement record?",
    description: "The SMSes have already gone out and cannot be recalled. This removes the announcement from the history view only.",
    confirm: "Delete record",
  },
  [AnnouncementStatus.FAILED]: {
    title: "Delete this announcement record?",
    description: "Removes the failed announcement from the history view.",
    confirm: "Delete record",
  },
};

const STATUS_VARIANT: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  [AnnouncementStatus.DRAFT]: "outline",
  [AnnouncementStatus.SCHEDULED]: "secondary",
  [AnnouncementStatus.SENDING]: "default",
  [AnnouncementStatus.SENT]: "default",
  [AnnouncementStatus.FAILED]: "destructive",
};

export default function AnnouncementsPage() {
  const [page, setPage] = useState(1);
  const [formOpen, setFormOpen] = useState(false);
  // `pendingDelete` controls the AlertDialog:
  //   - AnnouncementResponse  → single-row confirmation, per-status copy
  //   - "bulk"                → bulk-delete confirmation for all selected rows
  //   - null                  → dialog closed
  const [pendingDelete, setPendingDelete] = useState<AnnouncementResponse | "bulk" | null>(null);
  // Selection state for multi-select. Scoped to a Set for O(1) toggle;
  // gets cleared when the page changes or after a successful bulk delete
  // (it'd otherwise hold stale ids from a previous page).
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  const { data, isLoading } = useAnnouncements(page);
  const { data: appointmentTypes } = useAppointmentTypes();
  const createAnnouncement = useCreateAnnouncement();
  const deleteAnnouncement = useCancelAnnouncement();
  const bulkDelete = useBulkDeleteAnnouncements();

  const items = data?.items ?? [];
  const total = data?.total ?? 0;
  const totalPages = Math.ceil(total / 20);

  // Visible ids on the current page — used by the select-all checkbox.
  const visibleIds = useMemo(() => items.map((a) => a.id), [items]);
  const allVisibleSelected =
    visibleIds.length > 0 && visibleIds.every((id) => selectedIds.has(id));
  const someVisibleSelected =
    !allVisibleSelected && visibleIds.some((id) => selectedIds.has(id));

  function toggleOne(id: string, checked: boolean) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (checked) next.add(id);
      else next.delete(id);
      return next;
    });
  }

  function toggleAllVisible(checked: boolean) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (checked) visibleIds.forEach((id) => next.add(id));
      else visibleIds.forEach((id) => next.delete(id));
      return next;
    });
  }

  function clearSelection() {
    setSelectedIds(new Set());
  }

  // Page changes — drop selection so the bulk-action chip doesn't claim
  // rows the user can no longer see.
  function changePage(next: number) {
    setPage(next);
    clearSelection();
  }

  function getTypeNames(ids: string[] | null) {
    if (!ids || !appointmentTypes) return "All customers";
    const names = ids
      .map((id) => appointmentTypes.find((t) => t.id === id)?.name)
      .filter(Boolean);
    return names.length > 0 ? names.join(", ") : "All customers";
  }

  const selectionCount = selectedIds.size;
  const anyMutationPending = deleteAnnouncement.isPending || bulkDelete.isPending;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Megaphone className="h-6 w-6" />
          <h1 className="text-2xl font-bold">Announcements</h1>
        </div>
        <Button onClick={() => setFormOpen(true)}>
          <Plus className="h-4 w-4 mr-2" />
          New Announcement
        </Button>
      </div>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>Announcement History</CardTitle>
          {selectionCount > 0 && (
            <div className="flex items-center gap-2">
              <span className="text-sm text-muted-foreground">
                {selectionCount} selected
              </span>
              <Button
                variant="ghost"
                size="sm"
                onClick={clearSelection}
                disabled={anyMutationPending}
              >
                Clear
              </Button>
              <Button
                variant="destructive"
                size="sm"
                onClick={() => setPendingDelete("bulk")}
                disabled={anyMutationPending}
              >
                <Trash2 className="h-4 w-4 mr-2" />
                Delete {selectionCount}
              </Button>
            </div>
          )}
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <p className="text-muted-foreground py-4">Loading...</p>
          ) : items.length === 0 ? (
            <p className="text-muted-foreground py-4">
              No announcements yet
            </p>
          ) : (
            <>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-10">
                      <input
                        type="checkbox"
                        aria-label="Select all on this page"
                        className={cn(
                          "size-4 cursor-pointer rounded border-hairline-strong",
                          "accent-primary"
                        )}
                        checked={allVisibleSelected}
                        ref={(el) => {
                          // Indeterminate isn't a JSX prop; set on the DOM node.
                          if (el) el.indeterminate = someVisibleSelected;
                        }}
                        onChange={(e) => toggleAllVisible(e.target.checked)}
                      />
                    </TableHead>
                    <TableHead>Message</TableHead>
                    <TableHead>Audience</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Recipients</TableHead>
                    <TableHead>Created</TableHead>
                    <TableHead />
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {items.map((ann) => (
                    <TableRow
                      key={ann.id}
                      data-state={selectedIds.has(ann.id) ? "selected" : undefined}
                    >
                      <TableCell className="w-10">
                        <input
                          type="checkbox"
                          aria-label={`Select announcement ${ann.id.slice(0, 8)}`}
                          className="size-4 cursor-pointer rounded border-hairline-strong accent-primary"
                          checked={selectedIds.has(ann.id)}
                          onChange={(e) => toggleOne(ann.id, e.target.checked)}
                        />
                      </TableCell>
                      <TableCell className="max-w-[300px] truncate">
                        {ann.message}
                      </TableCell>
                      <TableCell className="text-sm">
                        {getTypeNames(ann.filter_appointment_type_ids)}
                      </TableCell>
                      <TableCell>
                        <Badge variant={STATUS_VARIANT[ann.status] ?? "outline"}>
                          {ann.status}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        {ann.status === AnnouncementStatus.SENT ||
                        ann.status === AnnouncementStatus.FAILED
                          ? `${ann.sent_count}/${ann.total_recipients}`
                          : "—"}
                      </TableCell>
                      <TableCell className="text-sm">
                        {format(new Date(ann.created_at), "MMM d, yyyy HH:mm")}
                      </TableCell>
                      <TableCell>
                        <Button
                          variant="ghost"
                          size="icon-sm"
                          className="text-destructive"
                          onClick={() => setPendingDelete(ann)}
                          disabled={anyMutationPending}
                          aria-label={
                            ann.status === AnnouncementStatus.SCHEDULED
                              ? "Cancel scheduled announcement"
                              : "Delete announcement"
                          }
                          title={
                            ann.status === AnnouncementStatus.SCHEDULED
                              ? "Cancel scheduled announcement"
                              : "Delete announcement"
                          }
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>

              {totalPages > 1 && (
                <div className="flex justify-center gap-2 pt-4">
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={page <= 1}
                    onClick={() => changePage(page - 1)}
                  >
                    Previous
                  </Button>
                  <span className="text-sm py-1">
                    Page {page} of {totalPages}
                  </span>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={page >= totalPages}
                    onClick={() => changePage(page + 1)}
                  >
                    Next
                  </Button>
                </div>
              )}
            </>
          )}
        </CardContent>
      </Card>

      <AnnouncementForm
        open={formOpen}
        onOpenChange={setFormOpen}
        onSubmit={(data) => {
          createAnnouncement.mutate(data, {
            onSuccess: () => setFormOpen(false),
          });
        }}
        isLoading={createAnnouncement.isPending}
      />

      <AlertDialog
        open={pendingDelete !== null}
        onOpenChange={(open) => {
          if (!open) setPendingDelete(null);
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {pendingDelete === "bulk"
                ? `Delete ${selectionCount} announcement${selectionCount === 1 ? "" : "s"}?`
                : pendingDelete
                  ? DELETE_COPY[pendingDelete.status]?.title ?? "Delete this announcement?"
                  : "Delete this announcement?"}
            </AlertDialogTitle>
            <AlertDialogDescription>
              {pendingDelete === "bulk"
                ? "Selected announcements will be removed. Scheduled ones are cancelled before dispatch; sent ones are removed from history only (SMSes already went out)."
                : pendingDelete
                  ? DELETE_COPY[pendingDelete.status]?.description ??
                    "This action cannot be undone."
                  : "This action cannot be undone."}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={anyMutationPending}>
              Keep them
            </AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive/10 text-destructive hover:bg-destructive/20"
              disabled={anyMutationPending}
              onClick={() => {
                if (pendingDelete === "bulk") {
                  if (selectionCount === 0) {
                    setPendingDelete(null);
                    return;
                  }
                  bulkDelete.mutate(Array.from(selectedIds), {
                    onSettled: () => {
                      setPendingDelete(null);
                      clearSelection();
                    },
                  });
                  return;
                }
                if (!pendingDelete) return;
                const target = pendingDelete;
                deleteAnnouncement.mutate(target.id, {
                  onSettled: () => {
                    setPendingDelete(null);
                    // Also drop this id from selection if it happened
                    // to be checked when the single-row trash was used.
                    setSelectedIds((prev) => {
                      if (!prev.has(target.id)) return prev;
                      const next = new Set(prev);
                      next.delete(target.id);
                      return next;
                    });
                  },
                });
              }}
            >
              {pendingDelete === "bulk"
                ? `Delete ${selectionCount}`
                : pendingDelete
                  ? DELETE_COPY[pendingDelete.status]?.confirm ?? "Delete"
                  : "Delete"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
