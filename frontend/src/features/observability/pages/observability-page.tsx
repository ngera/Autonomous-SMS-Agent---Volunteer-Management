import { useState } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import {
  usePhase1Metrics,
  usePhase2Metrics,
  usePhase3Metrics,
  usePhase4Metrics,
  usePhase5Metrics,
} from "../hooks/use-observability";
import { WindowPicker } from "../components/window-picker";
import type { ObservabilityMetric } from "@/types/api";

const METRIC_LABELS: Record<string, { title: string; description: string }> = {
  check_in_completion_rate: {
    title: "Check-in completion rate",
    description: "% of bookings with a check-in timestamp",
  },
  admin_vs_volunteer_checkin_split: {
    title: "Admin vs. volunteer check-in split",
    description: "Fraction of check-ins initiated by admin override",
  },
  auto_close_rate: {
    title: "Auto-close rate",
    description: "% of check-outs handled by the T+end+1h job",
  },
  walkup_candidate_volume: {
    title: "Walk-up candidates",
    description: "New volunteer_candidate rows created in the window",
  },
  candidate_promote_dismiss_split: {
    title: "Candidate promote vs. dismiss",
    description: "Fraction of resolved candidates that were invited",
  },
  // Phase 2 — Roster auto-pings
  pings_sent_volume: {
    title: "Pings scheduled",
    description: "Total ping rows (sent + skipped + suppressed)",
  },
  stop_status_optout_rate: {
    title: "STOP STATUS opt-out rate",
    description: "% of pings silenced by admin opt-out",
  },
  all_checked_in_suppression_rate: {
    title: "All-in suppression rate",
    description: "% of pings suppressed because everyone arrived early",
  },
  dispatch_failed_rate: {
    title: "Dispatch failure rate",
    description: "% of attempted dispatches that failed (Twilio errors)",
  },
  // Phase 3 — Service log + mid-event switch
  switch_request_volume: {
    title: "SWITCH/ALSO requests",
    description: "Volunteer-initiated service changes",
  },
  approval_rate: {
    title: "Approval rate",
    description: "Fraction of decisioned requests that were approved",
  },
  supersede_rate: {
    title: "Supersede rate",
    description: "% of requests that were churned by a later one",
  },
  approval_latency_seconds: {
    title: "Approval latency (p50, sec)",
    description: "Median time admin took to decide. p95/max in extras.",
  },
  // Phase 4 — Post-event review + grading
  review_approval_rate: {
    title: "Review approval rate",
    description: "% of non-no-show reviews that admin finalized",
  },
  time_to_review_seconds: {
    title: "Time-to-review (p50, sec)",
    description: "Review created → admin approved. p95/max in extras.",
  },
  grade_distribution: {
    title: "Average grade",
    description: "Mean of 1-5 grades. Per-grade counts in extras.",
  },
  consider_striking_rate: {
    title: "Consider-striking rate",
    description: "% of approved reviews with grade=1 (admin-flagged concerns)",
  },
  owner_unlock_rate: {
    title: "OWNER unlock share",
    description: "Fraction of unlocks done by OWNER (vs SUPER_ADMIN)",
  },
  super_admin_unlock_rate: {
    title: "SUPER_ADMIN unlock share",
    description: "Fraction of unlocks done by SUPER_ADMIN",
  },
  // Phase 5 — Recognition + quality score + candidate prune
  recognitions_earned_per_kind: {
    title: "Recognitions earned",
    description: "Grants in window. Per-kind breakdown in extras.",
  },
  congrats_sms_dispatch_volume: {
    title: "Congrats SMS dispatched",
    description: "Auto-send only fires when the opt-in flag is on.",
  },
  quality_score_distribution: {
    title: "Quality score (avg)",
    description: "Mean of historical_quality_score across volunteers.",
  },
  candidate_terminal_pool: {
    title: "Candidate auto-prune",
    description: "Candidates auto-dismissed after 1-year retention.",
  },
};

/**
 * Phase 1 Observability dashboard (decision #33).
 *
 * Available to OWNER + MANAGER (the backend enforces it via role gate).
 * Tenant-scoped; SUPER_ADMIN gets the same view per-tenant plus a
 * separate cross-tenant comparator (future page).
 */
export function ObservabilityPage() {
  const [days, setDays] = useState(30);
  const [tab, setTab] = useState("phase1");

  const phase1 = usePhase1Metrics(days);
  const phase2 = usePhase2Metrics(days);
  const phase3 = usePhase3Metrics(days);
  const phase4 = usePhase4Metrics(days);
  const phase5 = usePhase5Metrics(days);

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold">Observability</h1>
          <p className="text-sm text-muted-foreground">
            Phase rollout metrics for engineering quality + adoption.
          </p>
        </div>
        <WindowPicker value={days} onChange={setDays} />
      </div>

      <Tabs value={tab} onValueChange={setTab}>
        <TabsList>
          <TabsTrigger value="phase1">Phase 1 — Check-in</TabsTrigger>
          <TabsTrigger value="phase2">Phase 2 — Auto-pings</TabsTrigger>
          <TabsTrigger value="phase3">Phase 3 — Service log</TabsTrigger>
          <TabsTrigger value="phase4">Phase 4 — Reviews</TabsTrigger>
          <TabsTrigger value="phase5">Phase 5 — Recognition</TabsTrigger>
        </TabsList>

        <TabsContent value="phase1" className="mt-4">
          <MetricsGrid metrics={phase1.data} isLoading={phase1.isLoading} />
        </TabsContent>

        <TabsContent value="phase2" className="mt-4">
          <MetricsGrid metrics={phase2.data} isLoading={phase2.isLoading} />
        </TabsContent>

        <TabsContent value="phase3" className="mt-4">
          <MetricsGrid metrics={phase3.data} isLoading={phase3.isLoading} />
        </TabsContent>

        <TabsContent value="phase4" className="mt-4">
          <MetricsGrid metrics={phase4.data} isLoading={phase4.isLoading} />
        </TabsContent>

        <TabsContent value="phase5" className="mt-4">
          <MetricsGrid metrics={phase5.data} isLoading={phase5.isLoading} />
        </TabsContent>
      </Tabs>
    </div>
  );
}

function MetricsGrid({
  metrics,
  isLoading,
}: {
  metrics: ObservabilityMetric[] | undefined;
  isLoading: boolean;
}) {
  if (isLoading) {
    return (
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {[0, 1, 2, 3, 4].map((i) => (
          <Skeleton key={i} className="h-32 w-full" />
        ))}
      </div>
    );
  }
  if (!metrics || metrics.length === 0) {
    return (
      <p className="rounded-md border border-dashed p-8 text-center text-sm text-muted-foreground">
        No data for the selected window.
      </p>
    );
  }
  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
      {metrics.map((m) => (
        <MetricCard key={m.label} metric={m} />
      ))}
    </div>
  );
}

function MetricCard({ metric }: { metric: ObservabilityMetric }) {
  const info =
    METRIC_LABELS[metric.label] || {
      title: metric.label,
      description: "",
    };

  // Format value: rate metrics show as %; count metrics show whole numbers.
  const isRate = metric.label.includes("rate") || metric.label.includes("split");
  const displayValue = isRate
    ? `${(metric.value * 100).toFixed(1)}%`
    : metric.value.toLocaleString();

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">
          {info.title}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-3xl font-semibold tabular-nums">{displayValue}</p>
        <CardDescription className="mt-1">
          {metric.denominator > 0 && (
            <span className="tabular-nums">
              {metric.numerator}/{metric.denominator}
            </span>
          )}
          {info.description && (
            <span className="ml-1 block text-xs">{info.description}</span>
          )}
        </CardDescription>
      </CardContent>
    </Card>
  );
}
