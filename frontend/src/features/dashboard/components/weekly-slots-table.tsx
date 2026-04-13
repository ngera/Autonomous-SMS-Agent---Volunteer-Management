import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Send, ChevronLeft, ChevronRight } from "lucide-react";
import { cn, formatDateTime } from "@/lib/utils";
import { useSendSlotReminder } from "../hooks/use-dashboard";
import type { WeeklySlotStatus } from "@/types/api";

interface WeeklySlotsTableProps {
  data?: WeeklySlotStatus[];
  isLoading: boolean;
  weekOffset: number;
  onPrevWeek: () => void;
  onNextWeek: () => void;
  onResetWeek?: () => void;
}

function StatusBadge({ status, booked, min_required, max_allowed }: { status: string; booked: number; min_required: number; max_allowed: number }) {
  if (status === "full") {
    return <Badge variant="default" className="bg-green-100 text-green-800 hover:bg-green-100">Full ({booked}/{max_allowed})</Badge>;
  }
  if (status === "met_minimum") {
    return <Badge variant="default" className="bg-blue-100 text-blue-800 hover:bg-blue-100">{booked}/{max_allowed} (min met)</Badge>;
  }
  const needed = min_required - booked;
  return <Badge variant="default" className="bg-red-100 text-red-800 hover:bg-red-100">Needs {needed} more ({booked}/{min_required} min)</Badge>;
}

export function WeeklySlotsTable({ data, isLoading, weekOffset, onPrevWeek, onNextWeek, onResetWeek }: WeeklySlotsTableProps) {
  const sendReminder = useSendSlotReminder();
  const [lastResult, setLastResult] = useState<{ key: string; msg: string } | null>(null);

  if (isLoading) {
    return (
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-base">Weekly Availability</CardTitle>
        </CardHeader>
        <CardContent><Skeleton className="h-40 w-full" /></CardContent>
      </Card>
    );
  }

  if (!data || data.length === 0) {
    return (
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-base">Weekly Availability</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">No availability windows configured for this period.</p>
        </CardContent>
      </Card>
    );
  }

  const grouped: Record<string, WeeklySlotStatus[]> = {};
  for (const slot of data) {
    const key = `${slot.date}|${slot.day_name}`;
    if (!grouped[key]) grouped[key] = [];
    grouped[key].push(slot);
  }

  function handleSendReminder(slot: WeeklySlotStatus) {
    const key = `${slot.date}-${slot.appointment_type_id}`;
    sendReminder.mutate(
      { date: slot.date, appointmentTypeId: slot.appointment_type_id },
      {
        onSuccess: (result) => {
          setLastResult({
            key,
            msg: `Sent ${result.sent_signup} signup + ${result.sent_confirmation} confirmation reminders (${result.total_volunteers} volunteers)`,
          });
          setTimeout(() => setLastResult(null), 5000);
        },
      }
    );
  }

  // Compute date range label from data or offset
  const dateRangeLabel = (() => {
    if (data && data.length > 0) {
      const dates = [...new Set(data.map((s) => s.date))].sort();
      return `${dates[0]} to ${dates[dates.length - 1]}`;
    }
    const start = new Date();
    start.setDate(start.getDate() + weekOffset);
    const end = new Date();
    end.setDate(end.getDate() + weekOffset + 6);
    return `${start.toISOString().slice(0, 10)} to ${end.toISOString().slice(0, 10)}`;
  })();

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle className="text-base">
          Weekly Availability — {dateRangeLabel}
        </CardTitle>
        <div className="flex items-center gap-1">
          <Button
            variant="outline"
            size="icon"
            className="h-8 w-8"
            onClick={onPrevWeek}
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>
          {weekOffset > 0 && (
            <Button
              variant="ghost"
              size="sm"
              className="h-8 text-xs"
              onClick={() => onResetWeek?.()}
            >
              This Week
            </Button>
          )}
          <Button
            variant="outline"
            size="icon"
            className="h-8 w-8"
            onClick={onNextWeek}
          >
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {Object.entries(grouped).map(([key, slots]) => {
          const [dateStr, dayName] = key.split("|");
          const hasIssues = slots.some((s) => s.status === "needs_more");
          return (
            <div key={key} className={cn("rounded-md border p-3 space-y-2", hasIssues && "border-red-300 bg-red-50/50")}>
              <div className="flex items-center justify-between">
                <span className="text-sm font-semibold">{dayName} — {dateStr}</span>
                {hasIssues && <Badge variant="destructive" className="text-xs">Needs attention</Badge>}
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-xs text-muted-foreground border-b">
                      <th className="pb-1 pr-4">Window</th>
                      <th className="pb-1 pr-4">Service</th>
                      <th className="pb-1 pr-4">Min</th>
                      <th className="pb-1 pr-4">Max</th>
                      <th className="pb-1 pr-4">Booked</th>
                      <th className="pb-1 pr-4">Status</th>
                      <th className="pb-1">Reminder</th>
                    </tr>
                  </thead>
                  <tbody>
                    {slots.map((slot, i) => {
                      const reminderKey = `${slot.date}-${slot.appointment_type_id}`;
                      const isSending = sendReminder.isPending && sendReminder.variables?.date === slot.date && sendReminder.variables?.appointmentTypeId === slot.appointment_type_id;
                      return (
                        <tr key={i} className="border-b last:border-0">
                          <td className="py-1.5 pr-4 whitespace-nowrap">
                            {slot.window_label ? `${slot.window_label} (${slot.window_time})` : slot.window_time}
                          </td>
                          <td className="py-1.5 pr-4">{slot.service_name}</td>
                          <td className="py-1.5 pr-4">{slot.min_required}</td>
                          <td className="py-1.5 pr-4">{slot.max_allowed}</td>
                          <td className="py-1.5 pr-4">{slot.booked}</td>
                          <td className="py-1.5 pr-4">
                            <StatusBadge status={slot.status} booked={slot.booked} min_required={slot.min_required} max_allowed={slot.max_allowed} />
                          </td>
                          <td className="py-1.5">
                            <div className="flex flex-col gap-0.5">
                              <Button
                                variant="ghost"
                                size="sm"
                                className="h-6 text-xs px-2 gap-1"
                                onClick={() => handleSendReminder(slot)}
                                disabled={isSending}
                              >
                                <Send className="h-3 w-3" />
                                {isSending ? "Sending..." : "Send Reminder"}
                              </Button>
                              {slot.last_reminder_sent && (
                                <span className="text-[10px] text-muted-foreground">
                                  Last: {formatDateTime(slot.last_reminder_sent)}
                                </span>
                              )}
                              {lastResult?.key === reminderKey && (
                                <span className="text-[10px] text-green-600">{lastResult.msg}</span>
                              )}
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}
