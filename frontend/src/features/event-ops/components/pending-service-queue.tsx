import { format, parseISO } from "date-fns";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { ArrowRight } from "lucide-react";
import type { PendingServiceEntry } from "@/types/api";
import {
  useApprovePending,
  usePendingForSlot,
  useRejectPending,
} from "../hooks/use-run-sheet";

interface PendingServiceQueueProps {
  slotId: string;
}

/**
 * Phase 3 — pending SWITCH/ALSO requests for one slot.
 *
 * Renders at the TOP of the run-sheet page (decision: most urgent
 * inbox item). Auto-refresh every 30s via tanstack-query. Approve /
 * Reject mutations include the row's `version` for optimistic
 * concurrency (decision #29b) — backend rejects stale clicks with
 * 409 and the UI surfaces a "refresh" toast.
 */
export function PendingServiceQueue({ slotId }: PendingServiceQueueProps) {
  const { data, isLoading } = usePendingForSlot(slotId);
  const approve = useApprovePending(slotId);
  const reject = useRejectPending(slotId);

  // Hide entirely when nothing is pending — keeps the run-sheet clean
  // until there's something to act on.
  if (isLoading) {
    return (
      <Card>
        <CardHeader className="pb-2">
          <CardTitle>Pending service requests</CardTitle>
        </CardHeader>
        <CardContent>
          <Skeleton className="h-16 w-full" />
        </CardContent>
      </Card>
    );
  }
  if (!data || data.length === 0) {
    return null;
  }

  return (
    <Card className="border-amber-300 dark:border-amber-900">
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2">
          <span className="inline-flex h-2.5 w-2.5 animate-pulse rounded-full bg-amber-500" />
          Pending service requests ({data.length})
        </CardTitle>
        <CardDescription>
          Volunteers requested a mid-event service switch or addition.
          Approve to record it on their booking_service_log; reject if
          they shouldn't be doing that role.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-2">
        {data.map((entry) => (
          <PendingRow
            key={entry.id}
            entry={entry}
            onApprove={() =>
              approve.mutate({
                entryId: entry.id,
                expectedVersion: entry.version,
              })
            }
            onReject={() =>
              reject.mutate({
                entryId: entry.id,
                expectedVersion: entry.version,
                reason: "rejected_via_runsheet",
              })
            }
            busy={approve.isPending || reject.isPending}
          />
        ))}
      </CardContent>
    </Card>
  );
}

interface PendingRowProps {
  entry: PendingServiceEntry;
  onApprove: () => void;
  onReject: () => void;
  busy: boolean;
}

function PendingRow({ entry, onApprove, onReject, busy }: PendingRowProps) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-md border border-border bg-card p-3">
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <p className="truncate font-medium">
            {entry.contact_name ?? entry.contact_phone}
          </p>
          <Badge variant="outline" className="text-xs">
            v{entry.version}
          </Badge>
        </div>
        <div className="mt-1 flex items-center gap-1 text-xs text-muted-foreground">
          <ArrowRight className="h-3 w-3" />
          <span className="truncate">{entry.target_service}</span>
          <span className="mx-1">·</span>
          <span>{format(parseISO(entry.created_at), "h:mm a")}</span>
        </div>
      </div>
      <div className="flex shrink-0 gap-2">
        <Button size="sm" onClick={onApprove} disabled={busy}>
          Approve
        </Button>
        <Button
          size="sm"
          variant="outline"
          onClick={onReject}
          disabled={busy}
        >
          Reject
        </Button>
      </div>
    </div>
  );
}
