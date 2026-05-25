import { useState } from "react";
import { Link } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { format, parseISO } from "date-fns";
import { AlertTriangle, Users } from "lucide-react";
import { useCampaigns } from "../hooks/use-recruitment";
import { CampaignStatus } from "@/types/enums";
import type {
  CampaignListItem,
  FillPerService,
} from "@/types/api";

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

function fillSummary(fill: Record<string, FillPerService>): string {
  const entries = Object.values(fill);
  if (entries.length === 0) return "—";
  return entries
    .map((e) => {
      const min = e.min_required ?? e.target;
      const maxLabel = e.max_allowed ? `/max ${e.max_allowed}` : "";
      return `${e.service_name ?? "service"} ${e.signups}/${min}${maxLabel}`;
    })
    .join(", ");
}

// Per-campaign roll-ups across all services. max_allowed=null on a service
// means "no ceiling" — surface that as "∞" rather than silently treating
// it as 0 (which would mis-display campaigns that have any uncapped service
// as having a smaller max than min).
function campaignTotals(fill: Record<string, FillPerService>) {
  const entries = Object.values(fill);
  let minTotal = 0;
  let maxTotal = 0;
  let hasUncapped = false;
  let signedTotal = 0;
  for (const e of entries) {
    const min = e.min_required ?? e.target ?? 0;
    minTotal += min;
    signedTotal += e.signups ?? 0;
    if (e.max_allowed == null) hasUncapped = true;
    else maxTotal += e.max_allowed;
  }
  const remainingMin = Math.max(0, minTotal - signedTotal);
  return {
    minTotal,
    maxLabel: hasUncapped
      ? entries.length === 1
        ? "∞"
        : `${maxTotal}+∞`
      : maxTotal.toString(),
    signedTotal,
    remainingMin,
  };
}

function AggregateStrip({
  active,
  needed,
  signedUp,
  messaged7d,
  atRisk,
}: {
  active: number;
  needed: number;
  signedUp: number;
  messaged7d: number;
  atRisk: number;
}) {
  const overallPct = needed > 0 ? signedUp / needed : 0;
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
      <StatCard label="Active campaigns" value={active.toString()} />
      <StatCard
        label="Volunteers needed"
        value={needed.toString()}
        subtitle={`across active events`}
      />
      <StatCard
        label="Signed up"
        value={`${signedUp}/${needed}`}
        subtitle={`${formatPct(overallPct)} filled`}
      />
      <StatCard
        label="Messaged (7d)"
        value={messaged7d.toString()}
        subtitle="across all waves"
      />
      <StatCard
        label="At risk"
        value={atRisk.toString()}
        subtitle={atRisk > 0 ? "needs attention" : "all on track"}
        warning={atRisk > 0}
      />
    </div>
  );
}

function StatCard({
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
    <Card>
      <CardContent className="p-4">
        <div className="text-xs uppercase tracking-wide text-muted-foreground">
          {label}
        </div>
        <div
          className={
            "mt-1 text-2xl font-semibold " +
            (warning ? "text-destructive" : "")
          }
        >
          {value}
        </div>
        {subtitle && (
          <div className="mt-1 text-xs text-muted-foreground">{subtitle}</div>
        )}
      </CardContent>
    </Card>
  );
}

function FillBar({ pct }: { pct: number }) {
  const clamped = Math.max(0, Math.min(1, pct));
  return (
    <div className="h-2 w-32 overflow-hidden rounded-full bg-muted">
      <div
        className="h-full bg-primary"
        style={{ width: `${clamped * 100}%` }}
      />
    </div>
  );
}

export default function CampaignsListPage() {
  const [statusFilter, setStatusFilter] = useState<CampaignStatus | "all">(
    "all"
  );
  const [atRiskOnly, setAtRiskOnly] = useState(false);

  const { data, isLoading } = useCampaigns({
    status: statusFilter === "all" ? undefined : statusFilter,
    at_risk_only: atRiskOnly,
  });

  const items = data?.items ?? [];
  const aggregate = data?.aggregate;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Campaigns</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Volunteer recruitment campaigns, closest event first.
          </p>
        </div>
      </div>

      {aggregate && (
        <AggregateStrip
          active={aggregate.active_campaigns}
          needed={aggregate.total_volunteers_needed}
          signedUp={aggregate.total_signed_up}
          messaged7d={aggregate.total_messaged_7d}
          atRisk={aggregate.at_risk_count}
        />
      )}

      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-3">
          <CardTitle className="text-base">Campaigns</CardTitle>
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <Switch
                id="at-risk"
                checked={atRiskOnly}
                onCheckedChange={setAtRiskOnly}
              />
              <Label htmlFor="at-risk" className="text-sm">
                At-risk only
              </Label>
            </div>
            <select
              value={statusFilter}
              onChange={(e) =>
                setStatusFilter(
                  e.target.value as CampaignStatus | "all"
                )
              }
              className="h-9 rounded-md border border-input bg-background px-2 text-sm"
            >
              <option value="all">All statuses</option>
              {Object.values(CampaignStatus).map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </div>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <p className="py-8 text-center text-sm text-muted-foreground">
              Loading…
            </p>
          ) : items.length === 0 ? (
            <p className="py-8 text-center text-sm text-muted-foreground">
              No campaigns. Create one from any event with services configured.
            </p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Event</TableHead>
                  <TableHead>Date</TableHead>
                  <TableHead>Days</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Fill</TableHead>
                  <TableHead className="text-right" title="Sum of min_required across all services in this campaign">Min</TableHead>
                  <TableHead className="text-right" title="Sum of max_allowed across all services (∞ when any service is uncapped)">Max</TableHead>
                  <TableHead className="text-right" title="Total volunteers signed up across all services">Signed up</TableHead>
                  <TableHead className="text-right" title="Volunteers still needed to hit the minimum across all services">Need (min)</TableHead>
                  <TableHead>Last sent</TableHead>
                  <TableHead>Next wave</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((c: CampaignListItem) => {
                  const totals = campaignTotals(c.fill_per_service);
                  return (
                  <TableRow key={c.id} className="cursor-pointer">
                    <TableCell>
                      <Link
                        to={`/recruitment/${c.id}`}
                        className="font-medium hover:underline"
                      >
                        {c.event_label ?? "Event"}
                      </Link>
                      {c.at_risk && (
                        <Badge
                          variant="destructive"
                          className="ml-2 align-middle text-[10px]"
                        >
                          <AlertTriangle className="mr-1 h-3 w-3" />
                          at risk
                        </Badge>
                      )}
                    </TableCell>
                    <TableCell className="text-sm">
                      {format(parseISO(c.event_date), "MMM d, yyyy")}
                    </TableCell>
                    <TableCell className="text-sm">
                      {c.days_to_event >= 0
                        ? `${c.days_to_event}d`
                        : `${Math.abs(c.days_to_event)}d ago`}
                    </TableCell>
                    <TableCell>
                      <Badge variant={STATUS_VARIANT[c.status]}>
                        {c.status}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <FillBar pct={c.overall_fill_pct} />
                        <span className="text-xs text-muted-foreground">
                          {formatPct(c.overall_fill_pct)}
                        </span>
                      </div>
                      <div className="mt-1 text-xs text-muted-foreground">
                        {fillSummary(c.fill_per_service)}
                      </div>
                    </TableCell>
                    <TableCell className="text-right tabular-nums text-sm">
                      {totals.minTotal}
                    </TableCell>
                    <TableCell className="text-right tabular-nums text-sm">
                      {totals.maxLabel}
                    </TableCell>
                    <TableCell className="text-right tabular-nums text-sm">
                      {totals.signedTotal}
                    </TableCell>
                    <TableCell
                      className={
                        "text-right tabular-nums text-sm " +
                        (totals.remainingMin > 0 ? "font-medium text-amber-700 dark:text-amber-400" : "text-muted-foreground")
                      }
                    >
                      {totals.remainingMin}
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {c.last_wave_sent_at
                        ? format(parseISO(c.last_wave_sent_at), "MMM d HH:mm")
                        : "—"}
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {c.next_wave_due_at
                        ? format(parseISO(c.next_wave_due_at), "MMM d HH:mm")
                        : "—"}
                    </TableCell>
                  </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
