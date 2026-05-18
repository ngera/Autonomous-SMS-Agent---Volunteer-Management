import { Link } from "react-router-dom";
import { AlertTriangle, ArrowRight, Users2 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { format, parseISO } from "date-fns";
import { useCampaigns } from "@/features/recruitment/hooks/use-recruitment";
import { CampaignStatus } from "@/types/enums";
import type { CampaignListItem, FillPerService } from "@/types/api";

const ACTIVE_LIKE_STATUSES: CampaignStatus[] = [
  CampaignStatus.DRAFT,
  CampaignStatus.AWAITING_APPROVAL,
  CampaignStatus.ACTIVE,
  CampaignStatus.PAUSED,
];

const STATUS_VARIANT: Record<
  string,
  "default" | "secondary" | "destructive" | "outline"
> = {
  [CampaignStatus.DRAFT]: "outline",
  [CampaignStatus.AWAITING_APPROVAL]: "secondary",
  [CampaignStatus.ACTIVE]: "default",
  [CampaignStatus.PAUSED]: "outline",
  [CampaignStatus.COMPLETED]: "default",
  [CampaignStatus.CANCELLED]: "outline",
  [CampaignStatus.FAILED]: "destructive",
};

function formatPct(pct: number): string {
  return `${Math.round(pct * 100)}%`;
}

function FillBar({ pct }: { pct: number }) {
  const clamped = Math.max(0, Math.min(1, pct));
  return (
    <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
      <div
        className="h-full bg-primary"
        style={{ width: `${clamped * 100}%` }}
      />
    </div>
  );
}

function fillSummary(fill: Record<string, FillPerService>): string {
  const entries = Object.values(fill);
  if (entries.length === 0) return "";
  return entries
    .map((e) => `${e.service_name ?? "service"} ${e.signups}/${e.min_required ?? e.target}`)
    .join(" · ");
}

const MAX_DASHBOARD_ROWS = 5;

export function CampaignsSummaryPanel() {
  const { data, isLoading } = useCampaigns();

  const allItems = data?.items ?? [];
  // Only campaigns still in motion — closed/cancelled belong on the full
  // Campaigns page, not the dashboard summary.
  const items = allItems.filter((c) =>
    ACTIVE_LIKE_STATUSES.includes(c.status)
  );
  const rows = items.slice(0, MAX_DASHBOARD_ROWS);
  const overflowCount = Math.max(0, items.length - rows.length);

  const aggregate = data?.aggregate;
  const overallPct =
    aggregate && aggregate.total_volunteers_needed > 0
      ? aggregate.total_signed_up / aggregate.total_volunteers_needed
      : 0;

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-3">
        <CardTitle className="text-base flex items-center gap-2">
          <Users2 className="h-4 w-4 text-muted-foreground" />
          Campaigns
        </CardTitle>
        <Button asChild variant="ghost" size="sm" className="h-7 px-2">
          <Link to="/campaigns" className="text-xs">
            View all
            <ArrowRight className="ml-1 h-3 w-3" />
          </Link>
        </Button>
      </CardHeader>
      <CardContent className="space-y-3">
        {isLoading ? (
          <p className="py-4 text-center text-xs text-muted-foreground">
            Loading…
          </p>
        ) : !aggregate || items.length === 0 ? (
          <p className="py-4 text-center text-xs text-muted-foreground">
            No active campaigns. Start one from any event with services
            configured.
          </p>
        ) : (
          <>
            {/* Compact aggregate strip */}
            <div className="grid grid-cols-3 gap-2">
              <Stat
                label="Active"
                value={aggregate.active_campaigns.toString()}
              />
              <Stat
                label="Filled"
                value={`${aggregate.total_signed_up}/${aggregate.total_volunteers_needed}`}
                subtitle={formatPct(overallPct)}
              />
              <Stat
                label="At risk"
                value={aggregate.at_risk_count.toString()}
                warning={aggregate.at_risk_count > 0}
              />
            </div>

            {/* Per-campaign rows */}
            <ul className="space-y-2.5">
              {rows.map((c) => (
                <CampaignRow key={c.id} c={c} />
              ))}
            </ul>

            {overflowCount > 0 && (
              <p className="text-center text-xs text-muted-foreground">
                +{overflowCount} more{" "}
                <Link to="/campaigns" className="underline">
                  on the Campaigns page
                </Link>
              </p>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}

function Stat({
  label,
  value,
  subtitle,
  warning,
}: {
  label: string;
  value: string;
  subtitle?: string;
  warning?: boolean;
}) {
  return (
    <div className="rounded-md border bg-muted/30 px-2 py-1.5">
      <div className="text-[10px] uppercase tracking-wide text-muted-foreground">
        {label}
      </div>
      <div
        className={
          "text-sm font-semibold " + (warning ? "text-destructive" : "")
        }
      >
        {value}
      </div>
      {subtitle && (
        <div className="text-[10px] text-muted-foreground">{subtitle}</div>
      )}
    </div>
  );
}

function CampaignRow({ c }: { c: CampaignListItem }) {
  const dateLabel = format(parseISO(c.event_date), "MMM d");
  const daysLabel =
    c.days_to_event >= 0
      ? `${c.days_to_event}d`
      : `${Math.abs(c.days_to_event)}d ago`;
  return (
    <li>
      <Link
        to={`/campaigns/${c.id}`}
        className="block rounded-md px-2 py-1.5 hover:bg-muted/50 transition-colors"
      >
        <div className="flex items-center gap-2 text-xs">
          <span className="flex-1 truncate font-medium text-foreground">
            {c.event_label ?? "Event"}
          </span>
          {c.at_risk && (
            <Badge variant="destructive" className="h-4 px-1 text-[9px]">
              <AlertTriangle className="mr-0.5 h-2.5 w-2.5" />
              at risk
            </Badge>
          )}
          <Badge
            variant={STATUS_VARIANT[c.status]}
            className="h-4 px-1.5 text-[9px]"
          >
            {c.status}
          </Badge>
        </div>
        <div className="mt-1 flex items-center gap-2">
          <FillBar pct={c.overall_fill_pct} />
          <span className="shrink-0 text-[10px] tabular-nums text-muted-foreground">
            {formatPct(c.overall_fill_pct)}
          </span>
        </div>
        <div className="mt-1 flex items-center justify-between text-[10px] text-muted-foreground">
          <span className="truncate">{fillSummary(c.fill_per_service)}</span>
          <span className="shrink-0 pl-2">
            {dateLabel} · {daysLabel}
          </span>
        </div>
      </Link>
    </li>
  );
}
