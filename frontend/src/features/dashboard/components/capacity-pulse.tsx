import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { format, parseISO } from "date-fns";
import {
  AlertCircle,
  CalendarDays,
  CheckCircle2,
  ChevronRight,
  Loader2,
  MapPin,
  Megaphone,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import {
  useStartCampaign,
  useUpcomingEvents,
} from "../hooks/use-dashboard";
import type { PlanningEvent } from "../api";

/**
 * Capacity Pulse — rich-row layout per event for the next 2 weeks.
 *
 *   ┌─ Event metadata ─┐ ┌── Bars (proportional within row + global) ──┐
 *   │ Food Drive       │ │ MIN     [██ 2 ░░ 1]      ← 25% wide          │
 *   │ Sat Jul 4 · 10–2 │ │ STRETCH [░░░░░ 6 ░░░░░]  ← 75% wide          │
 *   │ Community Center │ │                                              │
 *   │ [Start Campaign] │ │                                              │
 *   └──────────────────┘ └──────────────────────────────────────────────┘
 *
 * Bar widths scale within the row to (min/max : stretch/max) AND across
 * rows to (this_event.max / global_max), so a small event looks small
 * relative to a big one.
 */

// Bar 1 (MIN) — strong colors; this is the "at risk" signal.
const FILLED_MIN_COLOR = "bg-emerald-500";
const OPEN_MIN_COLOR = "bg-red-500";

// Bar 2 (STRETCH) — muted; "more would be nice but not critical".
const FILLED_STRETCH_COLOR = "bg-emerald-300";
const OPEN_STRETCH_COLOR = "bg-pink-200 dark:bg-pink-300";

export interface EventRow {
  event: PlanningEvent;
  filled_min: number;
  open_min: number;
  filled_stretch: number;
  open_stretch: number;
  min: number;
  max: number;
  booked: number;
}

/** Build a CapacityRow shape from a PlanningEvent. Exported so the
 *  Planning heatmap drawer can render the same rich row that the
 *  Capacity Pulse on Needs-You-Now does. */
export function buildEventRow(e: PlanningEvent): EventRow {
  const min = e.min_required_total;
  const max = e.capacity;
  const booked = e.booked;
  const filled_min = Math.min(booked, min);
  const open_min = Math.max(0, min - booked);
  const filled_stretch = Math.max(0, Math.min(booked - min, max - min));
  const open_stretch = Math.max(0, max - min - filled_stretch);
  return {
    event: e,
    min,
    max,
    booked,
    filled_min,
    open_min,
    filled_stretch,
    open_stretch,
  };
}

interface CapacityPulseProps {
  /** Source of events to render. Default: the Needs-You-Now hook
   *  (T-0 → T+14). Pass `usePlanning` to render the same chart for
   *  T+15 → T+60 in the Planning tab. */
  useSource?: () => {
    data: PlanningEvent[] | undefined;
    isLoading: boolean;
  };
  /** Eyebrow + emptyState copy can be customized per surface. */
  eyebrow?: string;
  emptyLabel?: string;
}

export function CapacityPulse({
  useSource = useUpcomingEvents,
  eyebrow = "Capacity pulse · next 2 weeks",
  emptyLabel = "No events in the next 2 weeks",
}: CapacityPulseProps = {}) {
  const { data, isLoading } = useSource();

  const rows = useMemo<EventRow[]>(() => {
    return (data ?? []).map(buildEventRow);
  }, [data]);

  const globalMax = useMemo(
    () => Math.max(1, ...rows.map((r) => r.max)),
    [rows],
  );

  if (isLoading) {
    return <Skeleton className="h-[260px] w-full rounded-2xl" />;
  }
  if (rows.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed py-10 text-center">
        <CalendarDays className="mb-2 h-7 w-7 text-muted-foreground" />
        <p className="text-sm font-medium">{emptyLabel}</p>
        <p className="mt-0.5 text-xs text-muted-foreground">
          Schedule something in Calendar to see it here.
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-2xl border bg-card p-4">
      <div className="mb-3 flex items-baseline justify-between">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
            {eyebrow}
          </p>
          <h3 className="text-sm font-semibold">
            Minimum + stretch coverage per event
          </h3>
        </div>
        <p className="text-[11px] text-muted-foreground">
          {rows.length} event{rows.length === 1 ? "" : "s"}
        </p>
      </div>

      <Legend />

      <div className="mt-3 space-y-3">
        {rows.map((r) => (
          <CapacityRow
            key={r.event.slot_id}
            row={r}
            globalMax={globalMax}
          />
        ))}
      </div>
    </div>
  );
}

export function Legend() {
  const items = [
    { color: FILLED_MIN_COLOR, label: "Filled to min" },
    { color: OPEN_MIN_COLOR, label: "Below min" },
    { color: FILLED_STRETCH_COLOR, label: "Stretch filled" },
    { color: OPEN_STRETCH_COLOR, label: "Stretch open" },
  ];
  return (
    <div className="flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-muted-foreground">
      {items.map((it) => (
        <span key={it.label} className="inline-flex items-center gap-1.5">
          <span className={cn("h-2.5 w-2.5 rounded-sm", it.color)} />
          {it.label}
        </span>
      ))}
    </div>
  );
}

export function CapacityRow({
  row,
  globalMax,
}: {
  row: EventRow;
  globalMax: number;
}) {
  const navigate = useNavigate();
  const startCampaign = useStartCampaign();
  const [agentReply, setAgentReply] = useState<string | null>(null);
  const { event, min, max, booked } = row;

  // Event metadata
  const dateLabel = useMemo(() => {
    try {
      return format(parseISO(event.date), "EEE, MMM d");
    } catch {
      return event.date;
    }
  }, [event.date]);
  const timeRange = event.time_range;

  // Bar widths
  const totalWidthPct = (max / globalMax) * 100;

  const isRecurring = event.kind === "recurring";

  function handleOpen() {
    // Open the roster for this occurrence. Specific slots have their
    // own roster route; recurring events route by (rule_id, date) so
    // the backend can materialize the same roster view without
    // requiring a SpecificDateSlot to exist yet.
    if (isRecurring && event.rule_id) {
      navigate(`/events/rule/${event.rule_id}/${event.date}`);
    } else if (isRecurring) {
      // Recurring row missing rule_id is unexpected — fall back to
      // the date-filtered bookings page so the click still lands
      // somewhere useful.
      navigate(`/bookings?date=${event.date}`);
    } else {
      navigate(`/events/specific/${event.slot_id}`);
    }
  }

  function handleStartCampaign() {
    // Recurring rows send (rule_id, date) — the server materializes
    // a specific_date_slot first so the campaign has an event_slot_id
    // to attach to. Specific rows send the slot_id directly.
    const args =
      isRecurring && event.rule_id
        ? { ruleId: event.rule_id, date: event.date }
        : { slotId: event.slot_id };
    startCampaign.mutate(args, {
      onSuccess: (data) => {
        setAgentReply(data.agent_reply ?? "Sent to agent.");
      },
    });
  }

  const hasCampaign = !!event.campaign;

  return (
    <div
      className={cn(
        "group flex gap-4 rounded-xl border bg-card/50 p-3 transition-all",
        "hover:shadow-md hover:-translate-y-px hover:border-foreground/20",
      )}
    >
      {/* Left: metadata column */}
      <div className="w-44 shrink-0 space-y-1">
        <button
          type="button"
          onClick={handleOpen}
          className="block w-full text-left"
        >
          <p className="truncate text-sm font-semibold">{event.label}</p>
        </button>
        <p className="text-[11px] text-muted-foreground">
          {dateLabel}
          {timeRange ? ` · ${timeRange}` : ""}
          {" · "}
          {event.days_until === 0
            ? "today"
            : event.days_until === 1
              ? "tomorrow"
              : `${event.days_until}d`}
        </p>
        {event.location && (
          <p className="flex items-center gap-1 truncate text-[11px] text-muted-foreground">
            <MapPin className="h-3 w-3 shrink-0" />
            {event.location}
          </p>
        )}
        <div className="flex flex-wrap items-center gap-1 pt-1">
          {isRecurring && (
            <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-medium text-slate-600 dark:bg-slate-800/60 dark:text-slate-300">
              Recurring
            </span>
          )}
          {hasCampaign ? (
            <CampaignBadge campaign={event.campaign!} />
          ) : agentReply ? (
            <span className="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-medium text-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-300">
              <CheckCircle2 className="h-3 w-3" />
              Agent replied
            </span>
          ) : (
            // Recurring rows materialize a SpecificDateSlot server-side
            // before the recruiter runs (see /start-campaign endpoint).
            <Button
              size="sm"
              variant="outline"
              className="h-7 px-2 text-[11px]"
              disabled={startCampaign.isPending || (isRecurring && !event.rule_id)}
              onClick={handleStartCampaign}
              title={
                isRecurring
                  ? "Promote this recurring occurrence to a real event and ask the recruiter agent to plan a campaign"
                  : "Ask the recruiter agent to plan a campaign for this event"
              }
            >
              {startCampaign.isPending ? (
                <>
                  <Loader2 className="mr-1 h-3 w-3 animate-spin" />
                  Asking agent…
                </>
              ) : (
                <>
                  <Megaphone className="mr-1 h-3 w-3" />
                  Start Campaign
                </>
              )}
            </Button>
          )}
          {startCampaign.error && (
            <span className="ml-1 inline-flex items-center gap-1 text-[11px] text-destructive">
              <AlertCircle className="h-3 w-3" />
              Failed
            </span>
          )}
        </div>
      </div>

      {/* Right: bars column */}
      <button
        type="button"
        onClick={handleOpen}
        className="relative flex-1 cursor-pointer space-y-2 self-center text-left"
        style={{ maxWidth: `${totalWidthPct}%` }}
      >
        <BarRow
          label="min"
          widthPct={max > 0 ? (min / max) * 100 : 0}
          totalCapacity={min}
          segments={[
            { value: row.filled_min, color: FILLED_MIN_COLOR, fg: "text-white" },
            { value: row.open_min, color: OPEN_MIN_COLOR, fg: "text-white" },
          ]}
        />
        <BarRow
          label="stretch"
          widthPct={max > 0 ? ((max - min) / max) * 100 : 0}
          totalCapacity={max - min}
          segments={[
            {
              value: row.filled_stretch,
              color: FILLED_STRETCH_COLOR,
              fg: "text-emerald-900",
            },
            {
              value: row.open_stretch,
              color: OPEN_STRETCH_COLOR,
              fg: "text-rose-900",
            },
          ]}
        />
        <p className="absolute -top-1 right-0 text-[10px] tabular-nums text-muted-foreground">
          {booked}/{max} booked · min {min}
        </p>
        <ChevronRight className="absolute right-0 top-1/2 h-4 w-4 -translate-y-1/2 translate-x-5 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100" />
      </button>
    </div>
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
  let label = campaign.status;
  if (isActive) {
    tone = "bg-sky-100 text-sky-800 dark:bg-sky-950/40 dark:text-sky-300";
    label = `Active · ${campaign.waves_completed}/${campaign.waves_total} waves`;
  } else if (isAwaiting) {
    tone = "bg-amber-100 text-amber-800 dark:bg-amber-950/40 dark:text-amber-300";
    label = "Awaiting approval";
  } else if (isDone) {
    tone = "bg-emerald-100 text-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-300";
    label = campaign.status === "completed" ? "Campaign done" : "Cancelled";
  }
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium",
        tone,
      )}
    >
      <Megaphone className="h-3 w-3" />
      {label}
    </span>
  );
}

function BarRow({
  label,
  widthPct,
  totalCapacity,
  segments,
}: {
  label: string;
  widthPct: number;
  totalCapacity: number;
  segments: {
    value: number;
    color: string;
    fg: string;
  }[];
}) {
  if (totalCapacity === 0) {
    return (
      <div className="flex h-5 items-center gap-2">
        <span className="w-14 shrink-0 text-[10px] uppercase tracking-wider text-muted-foreground">
          {label}
        </span>
        <div className="h-1.5 w-8 rounded-full bg-muted/40" />
      </div>
    );
  }
  return (
    <div className="flex h-5 items-center gap-2">
      <span className="w-14 shrink-0 text-[10px] uppercase tracking-wider text-muted-foreground">
        {label}
      </span>
      <div
        className="flex h-5 overflow-hidden rounded-md"
        style={{ width: `${widthPct}%` }}
      >
        {segments.map((seg, i) => {
          if (seg.value <= 0) return null;
          return (
            <div
              key={i}
              className={cn(
                "flex items-center justify-center text-[11px] font-semibold tabular-nums",
                seg.color,
                seg.fg,
              )}
              style={{ flex: seg.value }}
            >
              {seg.value / totalCapacity >= 0.12 ? seg.value : ""}
            </div>
          );
        })}
      </div>
    </div>
  );
}
