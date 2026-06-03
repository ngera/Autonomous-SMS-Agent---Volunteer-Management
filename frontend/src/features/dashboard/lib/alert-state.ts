// Server-side alert state (Phase 2).
//
// Snooze + dismiss are persisted in `dashboard_alert_state` so they
// survive reload, work across devices, and are shared across admins on
// the same tenant. The hook below preserves the same API surface as the
// Phase-1 localStorage version so consumers don't change.
//
// The /alerts endpoint already filters suppressed items server-side;
// this hook exists so the UI can show "snoozed until 4pm" badges and
// reflect optimistic state immediately on click.

import { useCallback } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  clearAlertState,
  dismissAlert,
  listAlertState,
  snoozeAlert,
  type AlertStateRecord,
} from "../api";
import { useActiveTenantId } from "@/hooks/use-active-tenant";

export interface DismissRecord {
  reason: string;
  dismissed_at: number; // epoch ms
}

export interface AlertStateActions {
  snoozedUntil: (alertId: string) => number | null;
  dismissedRecord: (alertId: string) => DismissRecord | null;
  snooze: (alertId: string, hours: number) => void;
  dismiss: (alertId: string, reason: string) => void;
  clear: (alertId: string) => void;
}

function useAlertStateQuery() {
  const tenantId = useActiveTenantId();
  return useQuery({
    queryKey: ["dashboard", "alert-state", tenantId],
    queryFn: listAlertState,
    enabled: tenantId !== "none",
    staleTime: 30_000,
  });
}

export function useAlertState(): AlertStateActions {
  const qc = useQueryClient();
  const { data } = useAlertStateQuery();

  const invalidate = useCallback(() => {
    void qc.invalidateQueries({ queryKey: ["dashboard", "alert-state"] });
    void qc.invalidateQueries({ queryKey: ["dashboard", "alerts"] });
  }, [qc]);

  const snoozeMutation = useMutation({
    mutationFn: ({ id, hours }: { id: string; hours: number }) =>
      snoozeAlert(id, hours),
    onSuccess: invalidate,
  });
  const dismissMutation = useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) =>
      dismissAlert(id, reason),
    onSuccess: invalidate,
  });
  const clearMutation = useMutation({
    mutationFn: (id: string) => clearAlertState(id),
    onSuccess: invalidate,
  });

  function snoozedUntil(alertId: string): number | null {
    const row = (data ?? []).find(
      (r: AlertStateRecord) => r.alert_id === alertId,
    );
    if (!row || row.state !== "snoozed" || !row.snoozed_until) return null;
    const until = new Date(row.snoozed_until).getTime();
    return until > Date.now() ? until : null;
  }

  function dismissedRecord(alertId: string): DismissRecord | null {
    const row = (data ?? []).find(
      (r: AlertStateRecord) => r.alert_id === alertId,
    );
    if (!row || row.state !== "dismissed") return null;
    return {
      reason: row.dismiss_reason ?? "",
      dismissed_at: new Date(row.created_at).getTime(),
    };
  }

  return {
    snoozedUntil,
    dismissedRecord,
    snooze: (id, hours) => snoozeMutation.mutate({ id, hours }),
    dismiss: (id, reason) => dismissMutation.mutate({ id, reason }),
    clear: (id) => clearMutation.mutate(id),
  };
}
