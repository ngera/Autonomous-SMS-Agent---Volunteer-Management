import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import type { DashboardSummary } from "@/types/api";

interface VolunteerBreakdownProps {
  data?: DashboardSummary;
  isLoading: boolean;
}

export function VolunteerBreakdown({ data, isLoading }: VolunteerBreakdownProps) {
  if (isLoading) {
    return <Skeleton className="h-24 w-full" />;
  }

  const services = data?.volunteers_by_service ?? [];

  if (services.length === 0) {
    return <p className="text-sm text-muted-foreground py-4">No services configured.</p>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-xs text-muted-foreground border-b">
            <th className="pb-2 pr-4">Service</th>
            <th className="pb-2 pr-4 text-right">Available</th>
            <th className="pb-2 pr-4 text-right">Min / Slot</th>
            <th className="pb-2 pr-4 text-right">Max / Slot</th>
            <th className="pb-2 pr-4 text-right">Slots (30d)</th>
            <th className="pb-2 pr-4 text-right">Buffer</th>
            <th className="pb-2">Status</th>
          </tr>
        </thead>
        <tbody>
          {services.map((svc) => {
            // buffer = available - min_per_slot
            // buffer > 0: can absorb absences
            // buffer == 0: no room for absences
            // buffer < 0: not enough even if everyone shows up
            const noSlots = svc.occurrences_30d === 0;
            const critical = !noSlots && svc.buffer < 0;
            const tight = !noSlots && svc.buffer === 0;
            const ok = !noSlots && svc.buffer > 0;

            let badge;
            if (noSlots) {
              badge = <Badge variant="outline" className="text-xs">No slots</Badge>;
            } else if (critical) {
              badge = <Badge variant="destructive" className="text-xs">Need {Math.abs(svc.buffer)} more</Badge>;
            } else if (tight) {
              badge = <Badge className="bg-amber-100 text-amber-800 hover:bg-amber-100 text-xs">No buffer</Badge>;
            } else {
              badge = <Badge className="bg-green-100 text-green-800 hover:bg-green-100 text-xs">+{svc.buffer} buffer</Badge>;
            }

            return (
              <tr
                key={svc.service_name}
                className={cn(
                  "border-b last:border-0",
                  critical && "bg-red-50/50",
                  tight && "bg-amber-50/50",
                )}
              >
                <td className="py-2 pr-4 font-medium">{svc.service_name}</td>
                <td className="py-2 pr-4 text-right">{svc.available}</td>
                <td className="py-2 pr-4 text-right">{svc.min_per_slot}</td>
                <td className="py-2 pr-4 text-right">{svc.max_per_slot}</td>
                <td className="py-2 pr-4 text-right">{svc.occurrences_30d}</td>
                <td className={cn(
                  "py-2 pr-4 text-right font-semibold",
                  critical ? "text-red-600" : tight ? "text-amber-600" : "text-green-600",
                )}>
                  {svc.buffer >= 0 ? `+${svc.buffer}` : svc.buffer}
                  <span className="font-normal text-muted-foreground text-xs ml-1">({svc.buffer_pct > 0 ? "+" : ""}{svc.buffer_pct}%)</span>
                </td>
                <td className="py-2">{badge}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
