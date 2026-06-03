import { Link, useParams } from "react-router-dom";
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
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  useAdminCheckin,
  useAdminCheckout,
  useRunSheet,
} from "../hooks/use-run-sheet";
import { PendingServiceQueue } from "../components/pending-service-queue";
import type { RunSheetVolunteer } from "@/types/api";

/**
 * Run-sheet page — live during-event roster (decision #21 sibling).
 *
 * Lists all volunteers for one event, with their check-in state.
 * Admin actions: manual Check in / Check out per row, mirroring the
 * SMS CHECKIN <name> / CHECKOUT <name> commands but bound to the
 * specific booking_id (no fuzzy name resolution needed here).
 *
 * Auto-refresh: 30s.
 */
export function RunSheetPage() {
  const { slotId } = useParams<{ slotId: string }>();
  const { data, isLoading } = useRunSheet(slotId);
  const checkin = useAdminCheckin(slotId);
  const checkout = useAdminCheckout(slotId);

  if (isLoading || !data) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-16 w-full" />
        <Skeleton className="h-96 w-full" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>{data.event_name}</CardTitle>
          <CardDescription>
            {data.start_time} – {data.end_time}
            {data.location ? ` · ${data.location}` : ""}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex items-center gap-4">
              <p className="text-2xl font-semibold tabular-nums">
                {data.checked_in_count}/{data.total_count}
              </p>
              <p className="text-sm text-muted-foreground">checked in</p>
            </div>
            <Link to={`/event-review/${slotId}`}>
              <Button variant="outline" size="sm">
                Post-event review →
              </Button>
            </Link>
          </div>
        </CardContent>
      </Card>

      {/* Phase 3 — pending service requests (renders only when data exists) */}
      {slotId && <PendingServiceQueue slotId={slotId} />}

      <Card>
        <CardHeader>
          <CardTitle>Roster</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Volunteer</TableHead>
                <TableHead>Service</TableHead>
                <TableHead>Checked in</TableHead>
                <TableHead>Checked out</TableHead>
                <TableHead>Source</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.volunteers.map((v) => (
                <RunSheetRow
                  key={v.booking_id}
                  v={v}
                  onCheckin={() =>
                    checkin.mutate({ bookingId: v.booking_id })
                  }
                  onCheckout={() =>
                    checkout.mutate({ bookingId: v.booking_id })
                  }
                  busy={checkin.isPending || checkout.isPending}
                />
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}

interface RunSheetRowProps {
  v: RunSheetVolunteer;
  onCheckin: () => void;
  onCheckout: () => void;
  busy: boolean;
}

function RunSheetRow({ v, onCheckin, onCheckout, busy }: RunSheetRowProps) {
  return (
    <TableRow>
      <TableCell>
        <div className="font-medium">{v.name ?? "—"}</div>
        <div className="text-xs text-muted-foreground">{v.phone}</div>
      </TableCell>
      <TableCell className="text-sm">{v.service_name ?? "—"}</TableCell>
      <TableCell className="text-sm">
        {v.checked_in_at ? (
          <span className="flex items-center gap-2">
            {format(parseISO(v.checked_in_at), "h:mm a")}
            {v.late_minutes != null && (
              <Badge variant="outline" className="text-amber-600">
                Late by {v.late_minutes} min
              </Badge>
            )}
          </span>
        ) : (
          <span className="text-muted-foreground">—</span>
        )}
      </TableCell>
      <TableCell className="text-sm">
        {v.checked_out_at ? (
          format(parseISO(v.checked_out_at), "h:mm a")
        ) : (
          <span className="text-muted-foreground">—</span>
        )}
      </TableCell>
      <TableCell className="text-xs text-muted-foreground">
        {v.checked_in_source ?? "—"}
      </TableCell>
      <TableCell className="text-right">
        <div className="flex justify-end gap-2">
          {!v.checked_in_at && (
            <Button size="sm" onClick={onCheckin} disabled={busy}>
              Check in
            </Button>
          )}
          {v.checked_in_at && !v.checked_out_at && (
            <Button
              size="sm"
              variant="outline"
              onClick={onCheckout}
              disabled={busy}
            >
              Check out
            </Button>
          )}
          {v.checked_out_at && (
            <span className="text-xs text-muted-foreground">Closed</span>
          )}
        </div>
      </TableCell>
    </TableRow>
  );
}
