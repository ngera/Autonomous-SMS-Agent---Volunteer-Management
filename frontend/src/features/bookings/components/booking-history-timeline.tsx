import { formatDateTime } from "@/lib/utils";
import { StatusBadge } from "@/components/shared/status-badge";
import type { BookingHistoryResponse } from "@/types/api";

interface BookingHistoryTimelineProps {
  history: BookingHistoryResponse[];
  isLoading: boolean;
}

export function BookingHistoryTimeline({
  history,
  isLoading,
}: BookingHistoryTimelineProps) {
  if (isLoading) {
    return <p className="text-sm text-muted-foreground">Loading history...</p>;
  }

  if (history.length === 0) {
    return <p className="text-sm text-muted-foreground">No history recorded.</p>;
  }

  return (
    <div className="space-y-4">
      {history.map((entry) => (
        <div key={entry.id} className="flex gap-3">
          <div className="flex flex-col items-center">
            <div className="h-2 w-2 rounded-full bg-primary mt-2" />
            <div className="w-px flex-1 bg-border" />
          </div>
          <div className="pb-4">
            <p className="text-sm font-medium">
              {entry.event_type.replace("_", " ").toUpperCase()}
            </p>
            <p className="text-xs text-muted-foreground">
              {formatDateTime(entry.created_at)} &middot; by{" "}
              {entry.changed_by}
            </p>
            {entry.new_status && (
              <div className="mt-1">
                <StatusBadge type="booking" value={entry.new_status} />
              </div>
            )}
            {entry.new_scheduled_at && (
              <p className="text-xs mt-1">
                {entry.previous_scheduled_at && (
                  <span className="line-through text-muted-foreground mr-2">
                    {formatDateTime(entry.previous_scheduled_at)}
                  </span>
                )}
                {formatDateTime(entry.new_scheduled_at)}
              </p>
            )}
            {entry.notes && (
              <p className="text-xs text-muted-foreground mt-1 italic">
                {entry.notes}
              </p>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
