import { useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { format, parseISO } from "date-fns";
import {
  CalendarDays,
  ChevronRight,
  MapPin,
  Megaphone,
  Sparkles,
} from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import type { PlanningEvent } from "../api";
import { usePlanning } from "../hooks/use-dashboard";

const BUCKET_LABELS: Record<PlanningEvent["bucket"], { label: string; sub: string }> = {
  week_2: { label: "Next 2 weeks", sub: "8–14 days out" },
  weeks_3_4: { label: "Weeks 3–4", sub: "15–28 days out" },
  month_2: { label: "Month 2", sub: "29–60 days out" },
};

const HEALTH_STYLES: Record<
  PlanningEvent["health"],
  { ring: string; bar: string; label: string; tone: string }
> = {
  filled: {
    ring: "ring-emerald-200/70 dark:ring-emerald-900/40",
    bar: "bg-emerald-500",
    label: "Filled",
    tone: "text-emerald-700 dark:text-emerald-300",
  },
  filling: {
    ring: "ring-sky-200/70 dark:ring-sky-900/40",
    bar: "bg-sky-500",
    label: "Filling",
    tone: "text-sky-700 dark:text-sky-300",
  },
  needs_campaign: {
    ring: "ring-amber-200/70 dark:ring-amber-900/40",
    bar: "bg-amber-500",
    label: "Needs campaign",
    tone: "text-amber-700 dark:text-amber-300",
  },
  not_started: {
    ring: "ring-slate-200/70 dark:ring-slate-800/50",
    bar: "bg-slate-400",
    label: "Not started",
    tone: "text-slate-600 dark:text-slate-400",
  },
};

export function HorizonTimeline() {
  const navigate = useNavigate();
  const { data, isLoading } = usePlanning();

  const buckets = useMemo(() => {
    const groups: Record<PlanningEvent["bucket"], PlanningEvent[]> = {
      week_2: [],
      weeks_3_4: [],
      month_2: [],
    };
    for (const e of data ?? []) {
      groups[e.bucket].push(e);
    }
    return groups;
  }, [data]);

  if (isLoading) {
    return (
      <div className="grid gap-4 lg:grid-cols-3">
        <Skeleton className="h-64 rounded-2xl" />
        <Skeleton className="h-64 rounded-2xl" />
        <Skeleton className="h-64 rounded-2xl" />
      </div>
    );
  }

  if (!data || data.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed py-10 text-center">
        <CalendarDays className="mb-2 h-8 w-8 text-muted-foreground" />
        <p className="text-sm font-medium">
          No events in the next 60 days
        </p>
        <p className="mt-1 max-w-sm text-xs text-muted-foreground">
          Schedule an event on the Calendar to see it here, and the
          recommendations engine will surface campaign suggestions
          automatically.
        </p>
      </div>
    );
  }

  return (
    <div className="grid gap-4 lg:grid-cols-3">
      {(["week_2", "weeks_3_4", "month_2"] as const).map((bucket) => (
        <BucketColumn
          key={bucket}
          bucket={bucket}
          events={buckets[bucket]}
          onOpen={(e) => navigate(`/run-sheet/${e.slot_id}`)}
          onStartCampaign={(e) =>
            navigate(`/campaigns?event_slot_id=${e.slot_id}`)
          }
        />
      ))}
    </div>
  );
}

interface BucketColumnProps {
  bucket: PlanningEvent["bucket"];
  events: PlanningEvent[];
  onOpen: (e: PlanningEvent) => void;
  onStartCampaign: (e: PlanningEvent) => void;
}

function BucketColumn({
  bucket,
  events,
  onOpen,
  onStartCampaign,
}: BucketColumnProps) {
  const meta = BUCKET_LABELS[bucket];
  return (
    <section className="rounded-2xl border bg-card/50 p-3">
      <header className="mb-3 px-1">
        <div className="flex items-baseline gap-2">
          <h3 className="text-sm font-semibold">{meta.label}</h3>
          <span className="text-[11px] text-muted-foreground">
            {events.length}
          </span>
        </div>
        <p className="text-[11px] text-muted-foreground">{meta.sub}</p>
      </header>
      {events.length === 0 ? (
        <p className="rounded-xl border border-dashed bg-muted/30 px-3 py-6 text-center text-xs text-muted-foreground">
          Nothing scheduled in this window
        </p>
      ) : (
        <div className="space-y-2">
          {events.map((e) => (
            <PlanningEventCard
              key={e.slot_id}
              event={e}
              onOpen={() => onOpen(e)}
              onStartCampaign={() => onStartCampaign(e)}
            />
          ))}
        </div>
      )}
    </section>
  );
}

interface PlanningEventCardProps {
  event: PlanningEvent;
  onOpen: () => void;
  onStartCampaign: () => void;
}

function PlanningEventCard({
  event,
  onOpen,
  onStartCampaign,
}: PlanningEventCardProps) {
  const tint = HEALTH_STYLES[event.health];
  const fillPct = Math.min(100, event.fill_pct * 100);
  const dateLabel = useMemo(() => {
    try {
      return format(parseISO(event.date), "EEE, MMM d");
    } catch {
      return event.date;
    }
  }, [event.date]);

  return (
    <button
      type="button"
      onClick={onOpen}
      className={cn(
        "group block w-full rounded-xl bg-card px-3 py-2.5 text-left ring-1 transition-all",
        "hover:shadow-md hover:-translate-y-px",
        tint.ring,
      )}
    >
      <div className="flex items-baseline gap-2">
        <p className="truncate text-sm font-semibold">{event.label}</p>
        <span className="ml-auto shrink-0 text-[11px] text-muted-foreground">
          {dateLabel} · {event.days_until}d
        </span>
      </div>
      <div className="mt-1 flex items-center gap-2 text-[11px] text-muted-foreground">
        {event.location && (
          <span className="inline-flex items-center gap-0.5">
            <MapPin className="h-3 w-3" />
            <span className="truncate">{event.location}</span>
          </span>
        )}
        <span className={cn("ml-auto shrink-0 font-medium", tint.tone)}>
          {tint.label}
        </span>
      </div>
      {/* Fill bar */}
      <div className="mt-2 flex items-center gap-2">
        <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
          <div
            className={cn("h-full rounded-full transition-all", tint.bar)}
            style={{ width: `${fillPct}%` }}
          />
        </div>
        <span className="shrink-0 text-[11px] font-medium tabular-nums">
          {event.booked}/{event.capacity}
        </span>
        <ChevronRight className="h-3.5 w-3.5 shrink-0 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100" />
      </div>
      {/* Campaign sub-row */}
      <div className="mt-2 flex items-center gap-1.5 text-[11px]">
        {event.campaign ? (
          <CampaignBadge campaign={event.campaign} />
        ) : event.health === "needs_campaign" ? (
          <span
            role="button"
            tabIndex={0}
            onClick={(ev) => {
              ev.stopPropagation();
              onStartCampaign();
            }}
            onKeyDown={(ev) => {
              if (ev.key === "Enter" || ev.key === " ") {
                ev.stopPropagation();
                onStartCampaign();
              }
            }}
            className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2 py-0.5 font-medium text-amber-800 hover:bg-amber-200 dark:bg-amber-950/40 dark:text-amber-300 dark:hover:bg-amber-900/40"
          >
            <Megaphone className="h-3 w-3" />
            Start a campaign
          </span>
        ) : (
          <span className="text-muted-foreground">No campaign yet</span>
        )}
      </div>
    </button>
  );
}

function CampaignBadge({
  campaign,
}: {
  campaign: NonNullable<PlanningEvent["campaign"]>;
}) {
  const isActive = campaign.status === "active";
  const isAwaiting = campaign.status === "awaiting_approval";
  const isDone =
    campaign.status === "completed" || campaign.status === "cancelled";

  let tone = "bg-slate-100 text-slate-700 dark:bg-slate-800/60 dark:text-slate-300";
  let icon = <Sparkles className="h-3 w-3" />;
  let label: string = campaign.status;

  if (isActive) {
    tone = "bg-sky-100 text-sky-800 dark:bg-sky-950/40 dark:text-sky-300";
    label = `Active · ${campaign.waves_completed}/${campaign.waves_total} waves`;
    icon = <Megaphone className="h-3 w-3" />;
  } else if (isAwaiting) {
    tone = "bg-amber-100 text-amber-800 dark:bg-amber-950/40 dark:text-amber-300";
    label = "Awaiting approval";
  } else if (isDone) {
    tone = "bg-emerald-100 text-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-300";
    label = "Campaign closed";
  }

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 font-medium",
        tone,
      )}
    >
      {icon}
      {label}
    </span>
  );
}
