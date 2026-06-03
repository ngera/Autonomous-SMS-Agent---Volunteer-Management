import { useNavigate } from "react-router-dom";
import {
  AlertTriangle,
  ChevronRight,
  Layers,
  Megaphone,
  Sparkles,
  TrendingUp,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import type { Recommendation } from "../api";
import { useRecommendations } from "../hooks/use-dashboard";

const KIND_ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  start_campaign: Megaphone,
  push_wave: TrendingUp,
  over_recruit: Sparkles,
  stagger: Layers,
};

const ACCENT_STYLES: Record<
  Recommendation["accent"],
  { ring: string; bg: string; iconBg: string; iconFg: string }
> = {
  amber: {
    ring: "ring-amber-200/70 dark:ring-amber-900/40",
    bg: "bg-gradient-to-br from-amber-50/70 to-transparent dark:from-amber-950/30",
    iconBg: "bg-amber-100 dark:bg-amber-950/50",
    iconFg: "text-amber-700 dark:text-amber-300",
  },
  red: {
    ring: "ring-red-200/70 dark:ring-red-900/40",
    bg: "bg-gradient-to-br from-red-50/70 to-transparent dark:from-red-950/30",
    iconBg: "bg-red-100 dark:bg-red-950/50",
    iconFg: "text-red-700 dark:text-red-300",
  },
  blue: {
    ring: "ring-sky-200/70 dark:ring-sky-900/40",
    bg: "bg-gradient-to-br from-sky-50/70 to-transparent dark:from-sky-950/30",
    iconBg: "bg-sky-100 dark:bg-sky-950/50",
    iconFg: "text-sky-700 dark:text-sky-300",
  },
  violet: {
    ring: "ring-violet-200/70 dark:ring-violet-900/40",
    bg: "bg-gradient-to-br from-violet-50/70 to-transparent dark:from-violet-950/30",
    iconBg: "bg-violet-100 dark:bg-violet-950/50",
    iconFg: "text-violet-700 dark:text-violet-300",
  },
  rose: {
    ring: "ring-rose-200/70 dark:ring-rose-900/40",
    bg: "bg-gradient-to-br from-rose-50/70 to-transparent dark:from-rose-950/30",
    iconBg: "bg-rose-100 dark:bg-rose-950/50",
    iconFg: "text-rose-700 dark:text-rose-300",
  },
  slate: {
    ring: "ring-slate-200/70 dark:ring-slate-800/40",
    bg: "bg-gradient-to-br from-slate-50 to-transparent dark:from-slate-900/30",
    iconBg: "bg-slate-100 dark:bg-slate-900/50",
    iconFg: "text-slate-700 dark:text-slate-300",
  },
};

export function RecommendationsStrip() {
  const navigate = useNavigate();
  const { data, isLoading } = useRecommendations();

  if (isLoading) {
    return (
      <div className="space-y-2">
        <Skeleton className="h-20 w-full rounded-xl" />
      </div>
    );
  }

  if (!data || data.length === 0) {
    return (
      <div className="flex items-center gap-3 rounded-2xl border border-dashed bg-gradient-to-br from-emerald-50/40 to-transparent p-4 dark:from-emerald-950/20">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-emerald-100 dark:bg-emerald-950/50">
          <Sparkles className="h-5 w-5 text-emerald-700 dark:text-emerald-300" />
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold">
            Nothing to recommend right now
          </p>
          <p className="mt-0.5 text-xs text-muted-foreground">
            Campaigns are pacing well. We'll surface ideas here when an
            event looks at-risk or a campaign stalls.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
      {data.map((rec) => {
        const Icon = KIND_ICONS[rec.kind] ?? AlertTriangle;
        const styles = ACCENT_STYLES[rec.accent] ?? ACCENT_STYLES.slate;
        return (
          <div
            key={rec.id}
            className={cn(
              "group relative flex flex-col gap-2 rounded-2xl p-3 ring-1 transition-all",
              "hover:shadow-md hover:-translate-y-px",
              styles.ring,
              styles.bg,
            )}
          >
            <div className="flex items-start gap-2.5">
              <div
                className={cn(
                  "flex h-9 w-9 shrink-0 items-center justify-center rounded-lg",
                  styles.iconBg,
                )}
              >
                <Icon className={cn("h-4.5 w-4.5", styles.iconFg)} />
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold leading-tight">
                  {rec.title}
                </p>
                <p className="mt-1 line-clamp-3 text-xs text-muted-foreground">
                  {rec.body}
                </p>
              </div>
            </div>
            <div className="mt-auto">
              <Button
                size="sm"
                variant="default"
                className="h-7 text-xs"
                onClick={() => navigate(rec.cta_url)}
              >
                {rec.cta_label}
                <ChevronRight className="ml-0.5 h-3 w-3" />
              </Button>
            </div>
          </div>
        );
      })}
    </div>
  );
}
