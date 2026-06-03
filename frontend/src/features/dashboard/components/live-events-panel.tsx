import { useNavigate } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { useLiveEvents } from "../hooks/use-dashboard";
import type { LiveEventRow } from "@/types/api";

/**
 * Live Events panel (decision #21).
 *
 * Visibility rule: panel renders only when at least one slot is in the
 * live window. Hides entirely on idle days — no empty state, no clutter.
 *
 * Sort: events with missing check-ins first (highest urgency), then by
 * start_at ascending (backend already sorts this way).
 *
 * Auto-refresh: 30s via useLiveEvents.
 */
export function LiveEventsPanel() {
  const navigate = useNavigate();
  const { data, isLoading } = useLiveEvents();

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Live Events</CardTitle>
        </CardHeader>
        <CardContent>
          <Skeleton className="h-16 w-full" />
        </CardContent>
      </Card>
    );
  }

  // Hide entirely when no events are live.
  if (!data || data.length === 0) {
    return null;
  }

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2">
          <span className="inline-flex h-2.5 w-2.5 animate-pulse rounded-full bg-emerald-500" />
          Live Events ({data.length})
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {data.map((row) => (
          <LiveEventRowItem
            key={row.slot_id}
            row={row}
            onOpen={() => navigate(`/run-sheet/${row.slot_id}`)}
          />
        ))}
      </CardContent>
    </Card>
  );
}

interface LiveEventRowItemProps {
  row: LiveEventRow;
  onOpen: () => void;
}

const DOT_CLASSES: Record<LiveEventRow["status_dot"], string> = {
  red: "bg-rose-500",
  amber: "bg-amber-500",
  green: "bg-emerald-500",
};

function LiveEventRowItem({ row, onOpen }: LiveEventRowItemProps) {
  const fillPct =
    row.total_count > 0
      ? Math.round((row.checked_in_count / row.total_count) * 100)
      : 0;
  const missingPreview =
    row.first_missing_names.length === 0
      ? ""
      : row.first_missing_names.join(", ") +
        (row.missing_count > row.first_missing_names.length
          ? ` +${row.missing_count - row.first_missing_names.length} more`
          : "");

  return (
    <button
      type="button"
      onClick={onOpen}
      className="block w-full rounded-lg border border-border bg-card p-3 text-left transition-colors hover:bg-accent"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 flex-1 items-start gap-2">
          <span
            className={cn(
              "mt-1 inline-flex h-2.5 w-2.5 shrink-0 rounded-full",
              DOT_CLASSES[row.status_dot]
            )}
          />
          <div className="min-w-0">
            <p className="truncate font-medium">{row.event_name}</p>
            <p className="text-xs text-muted-foreground">
              {row.start_time} – {row.end_time}
              {row.location ? ` · ${row.location}` : ""}
            </p>
            {missingPreview && (
              <p className="mt-1 text-xs text-muted-foreground">
                Missing: {missingPreview}
              </p>
            )}
          </div>
        </div>
        <div className="text-right">
          <p className="text-sm font-semibold tabular-nums">
            {row.checked_in_count}/{row.total_count}
          </p>
          <p className="text-xs text-muted-foreground">checked in</p>
          {row.pending_switches > 0 && (
            <p className="mt-1 text-xs font-medium text-amber-600">
              {row.pending_switches} pending
            </p>
          )}
        </div>
      </div>
      <div className="mt-2 h-1 w-full overflow-hidden rounded-full bg-muted">
        <div
          className={cn("h-full transition-all", DOT_CLASSES[row.status_dot])}
          style={{ width: `${fillPct}%` }}
        />
      </div>
    </button>
  );
}
