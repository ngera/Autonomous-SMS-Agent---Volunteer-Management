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
  /** Headline for the events card — varies by tab horizon (e.g.
   *  "Events this week" vs "Events 15-60 days"). */
  eventsLabel: string;
  eventsCount?: number;
  /** Optional subline under the events count
   *  (e.g. "3 recurring · 5 one-time"). */
  eventsSubline?: string;
  /** Open-slots card value — usually rendered as "openMin / totalRequired". */
  openSlotsValue: string | number;
  openSlotsSubline?: string;
  /** Number of events under their minimum staffing in the horizon. */
  atRiskCount?: number;
  atRiskSubline?: string;
  /** Campaigns-running headline value — e.g. "3 / 14"
   *  (events with a non-terminal campaign / total events). */
  campaignsValue?: string | number;
  campaignsSubline?: string;
  isLoading: boolean;
}

export function DashboardKpiRow({
  eventsLabel,
  eventsCount,
  eventsSubline,
  openSlotsValue,
  openSlotsSubline,
  atRiskCount,
  atRiskSubline,
  campaignsValue,
  campaignsSubline,
  isLoading,
}: DashboardKpiRowProps) {
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <KpiCard
        label={eventsLabel}
        value={eventsCount ?? 0}
        subline={eventsSubline}
        isLoading={isLoading}
      />
      <KpiCard
        label="Open slots"
        value={openSlotsValue}
        subline={openSlotsSubline}
        isLoading={isLoading}
      />
      <KpiCard
        label="At-risk events"
        value={atRiskCount ?? 0}
        subline={atRiskSubline}
        isLoading={isLoading}
      />
      <KpiCard
        label="Campaigns running"
        value={campaignsValue ?? 0}
        subline={campaignsSubline}
        isLoading={isLoading}
      />
    </div>
  );
}
