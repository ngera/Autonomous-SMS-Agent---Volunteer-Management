import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  ChevronRight,
  MapPin,
  Megaphone,
  Sparkles,
  AlertCircle,
  Loader2,
  CheckCircle2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { fillPercent, type AggregatedEvent } from "../lib/aggregate";
import type { PlanningEvent } from "../api";
import { useStartCampaign } from "../hooks/use-dashboard";

/**
 * Compact event card with a circular fill ring as the headline visual,
 * inline campaign status (when one exists), and a Start Campaign button
 * (when one doesn't). Used by both ThisWeekStrip and the Planning horizon.
 *
 * Two input modes:
 *   - `weekly` (AggregatedEvent) — from the weekly slot status feed
 *   - `planning` (PlanningEvent) — from the /dashboard/planning endpoint
 *     (carries campaign info).
 */
interface BaseProps {
  bucket?: string; // e.g. "Today", "Tomorrow", "Sat"
  className?: string;
}

interface WeeklyEventCardProps extends BaseProps {
  variant: "weekly";
  event: AggregatedEvent;
}

interface PlanningEventCardProps extends BaseProps {
  variant: "planning";
  event: PlanningEvent;
}

type EventCardProps = WeeklyEventCardProps | PlanningEventCardProps;

function ringTint(fill: number): { ring: string; track: string; tone: string } {
  if (fill >= 1) {
    return {
      ring: "stroke-emerald-500",
      track: "stroke-emerald-100 dark:stroke-emerald-950/40",
      tone: "text-emerald-700 dark:text-emerald-300",
    };
  }
  if (fill >= 0.6) {
    return {
      ring: "stroke-sky-500",
      track: "stroke-sky-100 dark:stroke-sky-950/40",
      tone: "text-sky-700 dark:text-sky-300",
    };
  }
  return {
    ring: "stroke-amber-500",
    track: "stroke-amber-100 dark:stroke-amber-950/40",
    tone: "text-amber-700 dark:text-amber-300",
  };
}

function FillRing({
  pct,
  booked,
  capacity,
  size = 64,
}: {
  pct: number;
  booked: number;
  capacity: number;
  size?: number;
}) {
  const tint = ringTint(pct);
  const strokeWidth = 6;
  const r = (size - strokeWidth) / 2;
  const c = 2 * Math.PI * r;
  const dash = Math.max(0.01, Math.min(1, pct)) * c;
  return (
    <div className="relative shrink-0" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          strokeWidth={strokeWidth}
          className={tint.track}
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          strokeWidth={strokeWidth}
          strokeDasharray={`${dash} ${c - dash}`}
          strokeLinecap="round"
          className={cn(tint.ring, "transition-all duration-500")}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span
          className={cn(
            "text-sm font-bold tabular-nums leading-none",
            tint.tone,
          )}
        >
          {booked}
        </span>
        <span className="text-[9px] uppercase tracking-wide text-muted-foreground">
          of {capacity}
        </span>
      </div>
    </div>
  );
}

function CampaignBadge({
  status,
  wavesTotal,
  wavesCompleted,
  onClick,
}: {
  status: string;
  wavesTotal: number;
  wavesCompleted: number;
  onClick?: () => void;
}) {
  let tone = "bg-slate-100 text-slate-700 dark:bg-slate-800/60 dark:text-slate-300";
  let icon = <Sparkles className="h-3 w-3" />;
  let label: string = status;
  if (status === "active") {
    tone = "bg-sky-100 text-sky-800 dark:bg-sky-950/40 dark:text-sky-300";
    icon = <Megaphone className="h-3 w-3" />;
    label = `Active · ${wavesCompleted}/${wavesTotal} waves`;
  } else if (status === "awaiting_approval") {
    tone = "bg-amber-100 text-amber-800 dark:bg-amber-950/40 dark:text-amber-300";
    label = "Awaiting approval";
  } else if (status === "completed" || status === "cancelled") {
    tone = "bg-emerald-100 text-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-300";
    label = status === "completed" ? "all mustr'ed" : "Campaign cancelled";
  }
  const Tag = onClick ? "button" : "span";
  return (
    <Tag
      type={onClick ? "button" : undefined}
      onClick={(e) => {
        if (onClick) {
          e.stopPropagation();
          onClick();
        }
      }}
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium",
        tone,
        onClick && "hover:opacity-90 cursor-pointer",
      )}
    >
      {icon}
      {label}
    </Tag>
  );
}

export function EventCard(props: EventCardProps) {
  const navigate = useNavigate();
  const startCampaign = useStartCampaign();
  const [agentReply, setAgentReply] = useState<string | null>(null);

  const {
    booked,
    capacity,
    fillPct,
    label,
    location,
    dateLabel,
    slotId,
    campaign,
    days_until,
    ruleId,
    isoDate,
  } = useMemo(() => {
    if (props.variant === "weekly") {
      const e = props.event;
      return {
        booked: e.booked,
        capacity: e.max_allowed,
        fillPct: fillPercent(e.booked, e.max_allowed),
        label: e.display_name,
        location: e.location,
        dateLabel: `${e.day_name.slice(0, 3)} · ${e.window_time}`,
        slotId: e.source_id ?? null,
        campaign: null,
        days_until: null as number | null,
        ruleId: null as string | null,
        isoDate: null as string | null,
      };
    }
    const e = props.event;
    return {
      booked: e.booked,
      capacity: e.capacity,
      fillPct: e.fill_pct,
      label: e.label,
      location: e.location,
      dateLabel: `${e.days_until}d away`,
      slotId: e.slot_id,
      campaign: e.campaign,
      days_until: e.days_until,
      ruleId: e.kind === "recurring" ? e.rule_id : null,
      isoDate: e.date,
    };
  }, [props]);

  function handleOpen() {
    if (props.variant === "planning") {
      navigate(`/run-sheet/${slotId}`);
      return;
    }
    const e = props.event;
    navigate(
      e.source === "one_time" && e.source_id
        ? `/events/specific/${e.source_id}`
        : `/bookings?date=${e.date}`,
    );
  }

  function handleStartCampaign() {
    // Recurring planning row → server materializes a specific slot
    // from (rule_id, date) before invoking the recruiter agent.
    const args =
      ruleId && isoDate
        ? { ruleId, date: isoDate }
        : slotId
          ? { slotId }
          : null;
    if (!args) return;
    startCampaign.mutate(args, {
      onSuccess: (data) => {
        setAgentReply(data.agent_reply ?? "Sent to agent.");
      },
    });
  }

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={handleOpen}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") handleOpen();
      }}
      className={cn(
        "group relative flex w-full items-center gap-3 rounded-2xl border bg-card p-3 text-left transition-all",
        "hover:shadow-md hover:-translate-y-px hover:border-foreground/20",
        props.className,
      )}
    >
      {/* Fill ring */}
      <FillRing pct={fillPct} booked={booked} capacity={capacity} />

      {/* Content */}
      <div className="min-w-0 flex-1 space-y-1">
        <div className="flex items-baseline gap-2">
          <p className="truncate text-sm font-semibold">{label}</p>
          {props.bucket && (
            <span className="ml-auto shrink-0 text-[10px] uppercase tracking-wider text-muted-foreground">
              {props.bucket}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
          <span className="truncate">{dateLabel}</span>
          {location && (
            <span className="inline-flex items-center gap-0.5 truncate">
              <MapPin className="h-3 w-3 shrink-0" />
              {location}
            </span>
          )}
        </div>

        {/* Campaign status or Start Campaign button */}
        <div className="flex flex-wrap items-center gap-1.5 pt-1">
          {campaign ? (
            <CampaignBadge
              status={campaign.status}
              wavesTotal={campaign.waves_total}
              wavesCompleted={campaign.waves_completed}
              onClick={() => navigate(`/campaigns/${campaign.id}`)}
            />
          ) : agentReply ? (
            <span className="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-2 py-0.5 text-[11px] font-medium text-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-300">
              <CheckCircle2 className="h-3 w-3" />
              Agent: {agentReply.length > 60 ? `${agentReply.slice(0, 60)}…` : agentReply}
            </span>
          ) : slotId ? (
            <Button
              size="sm"
              variant="outline"
              className="h-6 px-2 text-[11px]"
              disabled={startCampaign.isPending}
              onClick={(e) => {
                e.stopPropagation();
                handleStartCampaign();
              }}
              title="Ask the recruiter agent to plan a campaign for this event"
            >
              {startCampaign.isPending ? (
                <>
                  <Loader2 className="mr-1 h-3 w-3 animate-spin" />
                  Asking agent…
                </>
              ) : (
                <>
                  <Megaphone className="mr-1 h-3 w-3" />
                  Muster Volunteers
                </>
              )}
            </Button>
          ) : null}

          {startCampaign.error && (
            <span className="inline-flex items-center gap-1 text-[11px] text-destructive">
              <AlertCircle className="h-3 w-3" />
              Couldn't start campaign
            </span>
          )}
        </div>
      </div>

      <ChevronRight className="absolute right-2 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100" />
    </div>
  );
}
