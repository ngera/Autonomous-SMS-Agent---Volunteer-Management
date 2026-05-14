import { useNavigate } from "react-router-dom";
import { format, parseISO } from "date-fns";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import type { AggregatedEvent } from "../lib/aggregate";

interface NeedsAttentionPanelProps {
  understaffed: AggregatedEvent | null;
  unreviewedSuspensions: number;
  suspendedOrBanned: number;
  isLoading: boolean;
}

interface AttentionItemProps {
  tone: "rose" | "amber" | "blue";
  title: string;
  description: string;
  actionLabel?: string;
  onAction?: () => void;
}

const TONE_STYLES: Record<
  AttentionItemProps["tone"],
  { bg: string; border: string; title: string; body: string; btn: string }
> = {
  rose: {
    bg: "bg-rose-50 dark:bg-rose-950/30",
    border: "border-rose-200 dark:border-rose-900",
    title: "text-rose-900 dark:text-rose-200",
    body: "text-rose-800 dark:text-rose-300",
    btn: "border-rose-300 text-rose-900 hover:bg-rose-100 dark:border-rose-800 dark:text-rose-200 dark:hover:bg-rose-950",
  },
  amber: {
    bg: "bg-amber-50 dark:bg-amber-950/30",
    border: "border-amber-200 dark:border-amber-900",
    title: "text-amber-900 dark:text-amber-200",
    body: "text-amber-800 dark:text-amber-300",
    btn: "border-amber-300 text-amber-900 hover:bg-amber-100 dark:border-amber-800 dark:text-amber-200 dark:hover:bg-amber-950",
  },
  blue: {
    bg: "bg-sky-50 dark:bg-sky-950/30",
    border: "border-sky-200 dark:border-sky-900",
    title: "text-sky-900 dark:text-sky-200",
    body: "text-sky-800 dark:text-sky-300",
    btn: "border-sky-300 text-sky-900 hover:bg-sky-100 dark:border-sky-800 dark:text-sky-200 dark:hover:bg-sky-950",
  },
};

function AttentionItem({
  tone,
  title,
  description,
  actionLabel,
  onAction,
}: AttentionItemProps) {
  const s = TONE_STYLES[tone];
  return (
    <div className={cn("space-y-2 rounded-md border p-3", s.bg, s.border)}>
      <p className={cn("text-sm font-medium", s.title)}>{title}</p>
      <p className={cn("text-xs", s.body)}>{description}</p>
      {actionLabel && onAction && (
        <Button
          size="sm"
          variant="outline"
          className={cn("h-7 bg-background/40 text-xs", s.btn)}
          onClick={onAction}
        >
          {actionLabel}
        </Button>
      )}
    </div>
  );
}

export function NeedsAttentionPanel({
  understaffed,
  unreviewedSuspensions,
  suspendedOrBanned,
  isLoading,
}: NeedsAttentionPanelProps) {
  const navigate = useNavigate();

  const items: AttentionItemProps[] = [];
  if (suspendedOrBanned > 0) {
    items.push({
      tone: "rose",
      title: `${suspendedOrBanned} volunteer${suspendedOrBanned === 1 ? "" : "s"} suspended or banned`,
      description: "These volunteers cannot book until reinstated.",
      actionLabel: "Review",
      onAction: () => navigate("/customers?status=suspended"),
    });
  }
  if (understaffed) {
    const open = understaffed.max_allowed - understaffed.booked;
    const day = format(parseISO(understaffed.date), "EEEE");
    // Route to the event roster so the admin can see who's signed up and
    // who else they might invite. Falls back to Schedule Setup only if the
    // source ID is missing (shouldn't normally happen).
    const rosterRoute = understaffed.source_id
      ? understaffed.source === "one_time"
        ? `/events/specific/${understaffed.source_id}`
        : `/events/rule/${understaffed.source_id}/${understaffed.date}`
      : "/availability";
    items.push({
      tone: "rose",
      title: `${understaffed.display_name} understaffed`,
      description: `${day} — ${open} ${open === 1 ? "slot" : "slots"} open`,
      actionLabel: "Review event",
      onAction: () => navigate(rosterRoute),
    });
  }
  if (unreviewedSuspensions > 0) {
    items.push({
      tone: "amber",
      title: `${unreviewedSuspensions} unreviewed suspension${unreviewedSuspensions === 1 ? "" : "s"}`,
      description: "Suspensions awaiting admin review",
      actionLabel: "Review queue",
      onAction: () => navigate("/suspensions"),
    });
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Needs attention</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {isLoading ? (
          <>
            <Skeleton className="h-20 w-full" />
            <Skeleton className="h-20 w-full" />
          </>
        ) : items.length === 0 ? (
          <p className="text-sm text-muted-foreground">All clear — nothing needs your attention.</p>
        ) : (
          items.map((item, i) => <AttentionItem key={i} {...item} />)
        )}
      </CardContent>
    </Card>
  );
}
