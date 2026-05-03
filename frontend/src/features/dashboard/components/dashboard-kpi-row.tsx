import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

interface KpiCardProps {
  label: string;
  value: string | number;
  subline?: string;
  isLoading: boolean;
}

function KpiCard({ label, value, subline, isLoading }: KpiCardProps) {
  return (
    <Card>
      <CardContent className="space-y-1 pt-5">
        <p className="text-sm text-muted-foreground">{label}</p>
        {isLoading ? (
          <Skeleton className="h-9 w-16" />
        ) : (
          <p className="text-3xl font-semibold leading-tight">{value}</p>
        )}
        {subline && (
          <p className="text-xs text-muted-foreground">{subline}</p>
        )}
      </CardContent>
    </Card>
  );
}

interface DashboardKpiRowProps {
  totalVolunteers?: number;
  eventsThisWeek?: number;
  recurringCount?: number;
  oneTimeCount?: number;
  openSlots?: number;
  monthlyBookings?: number;
  isLoading: boolean;
}

export function DashboardKpiRow({
  totalVolunteers,
  eventsThisWeek,
  recurringCount,
  oneTimeCount,
  openSlots,
  monthlyBookings,
  isLoading,
}: DashboardKpiRowProps) {
  const eventsSubline =
    typeof recurringCount === "number" && typeof oneTimeCount === "number"
      ? `${recurringCount} recurring · ${oneTimeCount} one-time`
      : undefined;

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <KpiCard
        label="Active volunteers"
        value={totalVolunteers ?? 0}
        isLoading={isLoading}
      />
      <KpiCard
        label="Events this week"
        value={eventsThisWeek ?? 0}
        subline={eventsSubline}
        isLoading={isLoading}
      />
      <KpiCard
        label="Open slots"
        value={openSlots ?? 0}
        subline="Slots needing more volunteers"
        isLoading={isLoading}
      />
      <KpiCard
        label="Bookings this month"
        value={monthlyBookings ?? 0}
        isLoading={isLoading}
      />
    </div>
  );
}
