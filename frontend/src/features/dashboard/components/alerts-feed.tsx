import { useMemo } from "react";
import { CheckCircle2, Inbox } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import type { AlertItem } from "../api";
import { useAlerts } from "../hooks/use-dashboard";
import { useAlertState } from "../lib/alert-state";
import { AlertCard } from "./alert-card";

const SEVERITY_GROUPS: { key: AlertItem["severity"]; label: string; accent: string }[] = [
  { key: "high",   label: "Urgent",       accent: "text-amber-700 dark:text-amber-300" },
  { key: "medium", label: "Needs review", accent: "text-violet-700 dark:text-violet-300" },
  { key: "low",    label: "Heads-up",     accent: "text-slate-600 dark:text-slate-400" },
];

export function AlertsFeed() {
  const { data, isLoading } = useAlerts();
  const state = useAlertState();

  // Filter locally-dismissed and snoozed items so the feed stays clean.
  // Snoozed past their expiry naturally come back into view.
  const visible = useMemo(() => {
    if (!data) return [];
    const now = Date.now();
    return data.filter((a) => {
      const snoozedUntil = state.snoozedUntil(a.id);
      if (snoozedUntil && snoozedUntil > now) return false;
      if (state.dismissedRecord(a.id)) return false;
      return true;
    });
  }, [data, state]);

  const grouped = useMemo(() => {
    const map = new Map<AlertItem["severity"], AlertItem[]>();
    for (const a of visible) {
      if (!map.has(a.severity)) map.set(a.severity, []);
      map.get(a.severity)!.push(a);
    }
    return map;
  }, [visible]);

  if (isLoading) {
    return (
      <div className="space-y-3">
        {[0, 1, 2].map((i) => (
          <Skeleton key={i} className="h-20 w-full rounded-xl" />
        ))}
      </div>
    );
  }

  if (visible.length === 0) {
    return <EmptyAlertsState totalRaw={data?.length ?? 0} />;
  }

  return (
    <div className="space-y-5">
      {SEVERITY_GROUPS.map(({ key, label, accent }) => {
        const items = grouped.get(key) ?? [];
        if (items.length === 0) return null;
        return (
          <section key={key} className="space-y-2">
            <div className="flex items-center gap-2">
              <h3
                className={cn(
                  "text-[11px] font-semibold uppercase tracking-wider",
                  accent,
                )}
              >
                {label}
              </h3>
              <span className="text-[11px] text-muted-foreground">
                {items.length}
              </span>
              <div className="h-px flex-1 bg-border" />
            </div>
            <div className="space-y-2">
              {items.map((a) => (
                <AlertCard key={a.id} alert={a} />
              ))}
            </div>
          </section>
        );
      })}
    </div>
  );
}

function EmptyAlertsState({ totalRaw }: { totalRaw: number }) {
  const hasSnoozed = totalRaw > 0;
  return (
    <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed py-10 text-center">
      <div className="flex h-14 w-14 items-center justify-center rounded-full bg-gradient-to-br from-emerald-100 to-emerald-50 ring-1 ring-emerald-200 dark:from-emerald-950/50 dark:to-emerald-950/20 dark:ring-emerald-900/50">
        {hasSnoozed ? (
          <Inbox className="h-7 w-7 text-emerald-700 dark:text-emerald-300" />
        ) : (
          <CheckCircle2 className="h-7 w-7 text-emerald-700 dark:text-emerald-300" />
        )}
      </div>
      <h3 className="mt-3 text-base font-semibold">
        {hasSnoozed ? "Inbox zero — for now" : "All clear"}
      </h3>
      <p className="mt-1 max-w-sm text-sm text-muted-foreground">
        {hasSnoozed
          ? "Snoozed items will return when their timer's up."
          : "Nothing needs your attention right now. New volunteer signals show up here as they happen."}
      </p>
    </div>
  );
}
