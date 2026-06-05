import { CalendarClock } from "lucide-react";
import { RecommendationsStrip } from "./recommendations-strip";
import { PlanningHeatmap } from "./planning-heatmap";

/**
 * Planning tab — strategic view of T+8 → T+60.
 *
 * Two zones:
 *   1. Recommendations strip   — suggestive AI; admin clicks Start.
 *   2. Horizon timeline        — 3 buckets (Next 2 weeks · Weeks 3-4 · Month 2)
 *                                with per-event fill bars and campaign status.
 */
export function PlanningView() {
  return (
    <div className="space-y-6">
      {/* Hero band */}
      <div className="overflow-hidden rounded-2xl bg-gradient-to-br from-sky-50 via-violet-50 to-amber-50 p-5 ring-1 ring-border dark:from-sky-950/30 dark:via-violet-950/30 dark:to-amber-950/20">
        <div className="flex items-start gap-3">
          <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-white/80 shadow-sm ring-1 ring-border dark:bg-slate-900/60">
            <CalendarClock className="h-5 w-5 text-sky-700 dark:text-sky-300" />
          </div>
          <div className="min-w-0 flex-1">
            <h2 className="text-lg font-semibold">
              Planning · beyond the next 2 weeks
            </h2>
            <p className="mt-0.5 max-w-2xl text-sm text-muted-foreground">
              Events 15–60 days out — past the operational window where
              you'd just send reminders. Start campaigns now to give the
              recruiter agent enough runway to fill them.
            </p>
          </div>
        </div>
      </div>

      {/* Recommendations */}
      <section>
        <SectionHeader
          eyebrow="Recommendations"
          title="Where to put your attention"
          hint="Rule-based today; AI-augmented next."
        />
        <RecommendationsStrip />
      </section>

      {/* Planning heatmap — a calendar grid (week × day) keeps a 60-day
          horizon scannable even when there are 20+ events. Clicking a
          cell expands the rich min/stretch bars used on Needs-You-Now,
          so the per-event detail is one click away rather than always
          on screen. */}
      <section>
        <SectionHeader
          eyebrow="Horizon"
          title="Events 15–60 days out"
          hint="Click a day for event details."
        />
        <PlanningHeatmap />
      </section>
    </div>
  );
}

function SectionHeader({
  eyebrow,
  title,
  hint,
}: {
  eyebrow: string;
  title: string;
  hint?: string;
}) {
  return (
    <div className="mb-3 flex items-baseline gap-3">
      <div>
        <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
          {eyebrow}
        </p>
        <h2 className="text-base font-semibold">{title}</h2>
      </div>
      {hint && (
        <p className="ml-auto hidden text-xs text-muted-foreground sm:block">
          {hint}
        </p>
      )}
    </div>
  );
}
