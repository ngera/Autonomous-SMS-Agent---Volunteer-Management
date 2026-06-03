import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  AlertTriangle,
  ArrowRightLeft,
  ChevronRight,
  ClipboardCheck,
  Clock,
  MessageSquareWarning,
  MessagesSquare,
  ShieldAlert,
  Sparkles,
  UserPlus,
  X,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import type { AlertItem } from "../api";
import { useAlertState } from "../lib/alert-state";

// Map icon name from server → component. Keeps the server free of any
// React-specific knowledge.
const ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  AlertTriangle,
  ArrowRightLeft,
  ClipboardCheck,
  MessageSquareWarning,
  MessagesSquare,
  ShieldAlert,
  Sparkles,
  UserPlus,
};

// Tailwind class fragments per accent. Centralized so visual rhythm
// across the alerts list stays uniform.
const ACCENT_STYLES: Record<
  AlertItem["accent"],
  { ring: string; bg: string; iconBg: string; iconFg: string; dot: string }
> = {
  amber: {
    ring: "ring-amber-200/70 dark:ring-amber-900/40",
    bg: "bg-gradient-to-br from-amber-50/80 to-transparent dark:from-amber-950/30",
    iconBg: "bg-amber-100 dark:bg-amber-950/50",
    iconFg: "text-amber-700 dark:text-amber-300",
    dot: "bg-amber-500",
  },
  red: {
    ring: "ring-red-200/70 dark:ring-red-900/40",
    bg: "bg-gradient-to-br from-red-50/80 to-transparent dark:from-red-950/30",
    iconBg: "bg-red-100 dark:bg-red-950/50",
    iconFg: "text-red-700 dark:text-red-300",
    dot: "bg-red-500",
  },
  blue: {
    ring: "ring-sky-200/70 dark:ring-sky-900/40",
    bg: "bg-gradient-to-br from-sky-50/80 to-transparent dark:from-sky-950/30",
    iconBg: "bg-sky-100 dark:bg-sky-950/50",
    iconFg: "text-sky-700 dark:text-sky-300",
    dot: "bg-sky-500",
  },
  violet: {
    ring: "ring-violet-200/70 dark:ring-violet-900/40",
    bg: "bg-gradient-to-br from-violet-50/80 to-transparent dark:from-violet-950/30",
    iconBg: "bg-violet-100 dark:bg-violet-950/50",
    iconFg: "text-violet-700 dark:text-violet-300",
    dot: "bg-violet-500",
  },
  rose: {
    ring: "ring-rose-200/70 dark:ring-rose-900/40",
    bg: "bg-gradient-to-br from-rose-50/80 to-transparent dark:from-rose-950/30",
    iconBg: "bg-rose-100 dark:bg-rose-950/50",
    iconFg: "text-rose-700 dark:text-rose-300",
    dot: "bg-rose-500",
  },
  slate: {
    ring: "ring-slate-200/70 dark:ring-slate-800/40",
    bg: "bg-gradient-to-br from-slate-50 to-transparent dark:from-slate-900/30",
    iconBg: "bg-slate-100 dark:bg-slate-900/50",
    iconFg: "text-slate-700 dark:text-slate-300",
    dot: "bg-slate-400",
  },
};

function formatAge(seconds: number): string {
  if (seconds < 60) return "just now";
  const m = Math.floor(seconds / 60);
  if (m < 60) return `${m} min ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.floor(h / 24);
  return `${d}d ago`;
}

interface AlertCardProps {
  alert: AlertItem;
}

export function AlertCard({ alert }: AlertCardProps) {
  const navigate = useNavigate();
  const state = useAlertState();
  const Icon = ICONS[alert.icon] ?? AlertTriangle;
  const styles = ACCENT_STYLES[alert.accent] ?? ACCENT_STYLES.slate;

  const [dismissOpen, setDismissOpen] = useState(false);
  const [reason, setReason] = useState("");

  function handleCta() {
    navigate(alert.cta_url);
  }

  function handleSnooze(hours: number) {
    state.snooze(alert.id, hours);
  }

  function handleDismissConfirm() {
    state.dismiss(alert.id, reason.trim() || "(no reason)");
    setDismissOpen(false);
    setReason("");
  }

  return (
    <div
      className={cn(
        "group relative flex gap-3 rounded-xl p-3 ring-1 transition-all",
        "hover:shadow-md hover:-translate-y-px",
        styles.ring,
        styles.bg,
      )}
    >
      <div
        className={cn(
          "flex h-10 w-10 shrink-0 items-center justify-center rounded-lg",
          styles.iconBg,
        )}
      >
        <Icon className={cn("h-5 w-5", styles.iconFg)} />
      </div>

      <div className="min-w-0 flex-1">
        <div className="flex items-baseline gap-2">
          <p className="truncate text-sm font-semibold leading-tight text-foreground">
            {alert.title}
          </p>
          <span
            className={cn(
              "inline-block h-1.5 w-1.5 shrink-0 rounded-full",
              styles.dot,
            )}
          />
          <span className="ml-auto shrink-0 text-[11px] text-muted-foreground">
            {formatAge(alert.age_seconds)}
          </span>
        </div>
        {alert.body && (
          <p className="mt-0.5 line-clamp-2 text-xs text-muted-foreground">
            {alert.body}
          </p>
        )}
        <div className="mt-2 flex items-center gap-1.5">
          <Button
            size="sm"
            variant="default"
            className="h-7 text-xs"
            onClick={handleCta}
          >
            {alert.cta_label}
            <ChevronRight className="ml-0.5 h-3 w-3" />
          </Button>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                size="sm"
                variant="ghost"
                className="h-7 px-2 text-xs text-muted-foreground"
                title="Snooze"
              >
                <Clock className="h-3.5 w-3.5" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start">
              <DropdownMenuItem onClick={() => handleSnooze(1)}>
                Snooze 1 hour
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => handleSnooze(4)}>
                Snooze 4 hours
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => handleSnooze(24)}>
                Snooze until tomorrow
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem
                onClick={() => setDismissOpen(true)}
                className="text-destructive"
              >
                Dismiss with reason
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
          {alert.context?.placeholder === true && (
            <span className="ml-1 inline-flex items-center rounded-full bg-slate-200/70 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-slate-600 dark:bg-slate-700/50 dark:text-slate-300">
              Preview
            </span>
          )}
        </div>
      </div>

      <Dialog open={dismissOpen} onOpenChange={setDismissOpen}>
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle>Dismiss this alert</DialogTitle>
            <DialogDescription>
              Tell us why so we can stop surfacing similar items later.
              It's optional — leave blank to dismiss silently.
            </DialogDescription>
          </DialogHeader>
          <Textarea
            placeholder="e.g. handled in person · not relevant · already resolved"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            rows={3}
          />
          <DialogFooter>
            <Button variant="outline" onClick={() => setDismissOpen(false)}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={handleDismissConfirm}>
              <X className="mr-1 h-3 w-3" />
              Dismiss
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
