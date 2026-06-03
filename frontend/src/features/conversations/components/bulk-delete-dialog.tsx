import { useMemo, useState } from "react";
import { format, subDays } from "date-fns";
import { AlertTriangle } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useBulkDeleteConversations } from "../hooks/use-conversations";

interface BulkDeleteDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** When set, the dialog is in "delete selected rows" mode. */
  selectedIds?: string[];
  /** Clears any local selection after a successful delete. */
  onDeleted?: () => void;
}

export function BulkDeleteDialog({
  open,
  onOpenChange,
  selectedIds,
  onDeleted,
}: BulkDeleteDialogProps) {
  const isSelectionMode = (selectedIds?.length ?? 0) > 0;

  // Default: 90 days ago.
  const [olderThan, setOlderThan] = useState<string>(
    format(subDays(new Date(), 90), "yyyy-MM-dd")
  );
  const [contactPhone, setContactPhone] = useState<string>("");
  const mutation = useBulkDeleteConversations();

  function reset() {
    setOlderThan(format(subDays(new Date(), 90), "yyyy-MM-dd"));
    setContactPhone("");
    mutation.reset();
  }

  function close() {
    onOpenChange(false);
    reset();
  }

  // What gets sent on submit. In selection mode we send only the IDs;
  // otherwise we send whichever filter fields the user has filled.
  const payload = useMemo(() => {
    if (isSelectionMode) {
      return { ids: selectedIds ?? null };
    }
    const out: {
      older_than?: string | null;
      contact_phone?: string | null;
    } = {};
    if (olderThan) {
      // End-of-day cutoff so "older than 2026-01-15" means anything before
      // 2026-01-16 00:00 — easier mental model for admins.
      out.older_than = new Date(`${olderThan}T00:00:00`).toISOString();
    }
    if (contactPhone.trim()) {
      out.contact_phone = contactPhone.trim();
    }
    return out;
  }, [isSelectionMode, selectedIds, olderThan, contactPhone]);

  const hasCriteria =
    isSelectionMode || !!payload.older_than || !!payload.contact_phone;

  function handleConfirm() {
    if (!hasCriteria) return;
    mutation.mutate(payload, {
      onSuccess: () => {
        onDeleted?.();
        close();
      },
    });
  }

  return (
    <Dialog open={open} onOpenChange={(o) => (o ? onOpenChange(true) : close())}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>
            {isSelectionMode
              ? `Delete ${selectedIds!.length} conversation${selectedIds!.length === 1 ? "" : "s"}?`
              : "Bulk delete conversations"}
          </DialogTitle>
          <DialogDescription>
            Deleted conversations are removed from the list and their agent
            trace events are cleared. Bookings, suspensions, and token-usage
            rows tied to them are preserved (their conversation link is
            simply nulled out).
          </DialogDescription>
        </DialogHeader>

        {!isSelectionMode && (
          <div className="space-y-3">
            <div className="space-y-1">
              <Label htmlFor="older-than">
                Delete conversations older than
              </Label>
              <Input
                id="older-than"
                type="date"
                value={olderThan}
                onChange={(e) => setOlderThan(e.target.value)}
              />
              <p className="text-xs text-muted-foreground">
                Last-message-at strictly before the start of this date.
                Leave blank to skip the date filter.
              </p>
            </div>
            <div className="space-y-1">
              <Label htmlFor="contact-phone">
                Only for volunteer phone (optional)
              </Label>
              <Input
                id="contact-phone"
                type="tel"
                value={contactPhone}
                onChange={(e) => setContactPhone(e.target.value)}
                placeholder="+15551234567"
              />
              <p className="text-xs text-muted-foreground">
                Combined with the date filter — both must match.
              </p>
            </div>
          </div>
        )}

        {mutation.isSuccess && (
          <div className="rounded-md border border-green-500 bg-green-500/10 px-3 py-2 text-xs">
            Deleted {mutation.data.deleted_count} conversation
            {mutation.data.deleted_count === 1 ? "" : "s"}.
          </div>
        )}
        {mutation.error && (
          <div className="rounded-md border border-destructive bg-destructive/10 px-3 py-2 text-xs text-destructive">
            <AlertTriangle className="mr-1 inline h-3 w-3" />
            {(mutation.error as { message?: string })?.message ??
              "Delete failed."}
          </div>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={close}>
            Cancel
          </Button>
          <Button
            variant="destructive"
            onClick={handleConfirm}
            disabled={!hasCriteria || mutation.isPending}
          >
            {mutation.isPending ? "Deleting…" : "Delete"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
