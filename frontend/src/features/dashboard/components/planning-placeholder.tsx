import { CalendarClock, Sparkles, TrendingUp } from "lucide-react";
import { Button } from "@/components/ui/button";

/**
 * Placeholder Planning tab content. Phase 2 will replace this with:
 *   - AI recommendations strip (suggestive — admin clicks Start)
 *   - Horizon timeline grouped by week-bucket (T+8 → T+60)
 *   - Per-event campaign status + fill bars
 *
 * For Phase 1 we ship the frame so the dashboard structure is final,
 * with a clear "what's coming" message that makes the absence
 * intentional rather than empty.
 */
export function PlanningPlaceholder() {
  return (
    <div className="space-y-6">
      {/* Hero block — sets the strategic mindset */}
      <div className="overflow-hidden rounded-2xl bg-gradient-to-br from-sky-50 via-violet-50 to-amber-50 p-6 ring-1 ring-border dark:from-sky-950/30 dark:via-violet-950/30 dark:to-amber-950/20">
        <div className="flex items-start gap-4">
          <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-white/80 shadow-sm ring-1 ring-border dark:bg-slate-900/60">
            <CalendarClock className="h-6 w-6 text-sky-700 dark:text-sky-300" />
          </div>
          <div className="min-w-0 flex-1">
            <h2 className="text-lg font-semibold">Planning · the next 1–2 months</h2>
            <p className="mt-1 max-w-xl text-sm text-muted-foreground">
              This is where you'll set the staffing strategy for upcoming events
              — start recruitment campaigns ahead of time, see which events are
              at risk, and act on AI recommendations.
            </p>
          </div>
        </div>
      </div>

      {/* Feature preview row — three cards that hint at what's coming */}
      <div className="grid gap-3 md:grid-cols-3">
        <PreviewCard
          icon={<Sparkles className="h-5 w-5" />}
          title="AI recommendations"
          body="Surfaces events that need a campaign started, with one-click action."
        />
        <PreviewCard
          icon={<CalendarClock className="h-5 w-5" />}
          title="Horizon timeline"
          body="Next 8–60 days, grouped by week. Fill status and campaign status at a glance."
        />
        <PreviewCard
          icon={<TrendingUp className="h-5 w-5" />}
          title="Demand signals"
          body="Demographic warnings and seasonality flags so you don't get caught short."
        />
      </div>

      {/* CTA — link to existing campaigns surface */}
      <div className="flex items-center justify-between rounded-2xl border bg-card p-4">
        <div>
          <p className="text-sm font-medium">Want to plan a campaign now?</p>
          <p className="text-xs text-muted-foreground">
            Use the existing Campaigns page until this view ships.
          </p>
        </div>
        <Button asChild variant="outline" size="sm">
          <a href="/campaigns">Open Campaigns</a>
        </Button>
      </div>

      <p className="text-center text-[11px] text-muted-foreground">
        Coming in the next sprint · Phase 2 of the dashboard rebuild.
      </p>
    </div>
  );
}

function PreviewCard({
  icon,
  title,
  body,
}: {
  icon: React.ReactNode;
  title: string;
  body: string;
}) {
  return (
    <div className="rounded-2xl border bg-card p-4">
      <div className="mb-2 flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-sky-100 to-violet-100 text-sky-700 dark:from-sky-950/40 dark:to-violet-950/40 dark:text-sky-300">
        {icon}
      </div>
      <p className="text-sm font-semibold">{title}</p>
      <p className="mt-1 text-xs text-muted-foreground">{body}</p>
    </div>
  );
}
