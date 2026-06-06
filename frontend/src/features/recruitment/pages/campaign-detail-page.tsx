import { useMemo, useState } from "react";
import { useNavigate, useParams, Link } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  AlertCircle,
  ArrowLeft,
  CheckCircle,
  CheckCircle2,
  PauseCircle,
  PlayCircle,
  RefreshCw,
  Trash2,
  XCircle,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { format, parseISO } from "date-fns";
import {
  useApproveCampaign,
  useCampaign,
  useCancelCampaign,
  useCancelWave,
  useDeleteCampaign,
  useEditPlan,
  usePauseCampaign,
  useRegeneratePlan,
  useResumeCampaign,
  useWaveRecipients,
} from "../hooks/use-recruitment";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { CampaignStatus, WaveStatus } from "@/types/enums";
import { useAppointmentTypes } from "@/features/appointment-types/hooks/use-appointment-types";
import { useSpecificSlotEventRoster } from "@/features/bookings/hooks/use-bookings";

const STATUS_VARIANT: Record<
  string,
  "default" | "secondary" | "destructive" | "outline"
> = {
  [CampaignStatus.DRAFT]: "outline",
  [CampaignStatus.AWAITING_APPROVAL]: "secondary",
  [CampaignStatus.ACTIVE]: "default",
  [CampaignStatus.PAUSED]: "outline",
  [CampaignStatus.COMPLETED]: "default",
  [CampaignStatus.CANCELLED]: "outline",
  [CampaignStatus.FAILED]: "destructive",
};

const WAVE_VARIANT: Record<
  string,
  "default" | "secondary" | "destructive" | "outline"
> = {
  [WaveStatus.PLANNED]: "outline",
  [WaveStatus.SENDING]: "secondary",
  [WaveStatus.SENT]: "default",
  [WaveStatus.SKIPPED]: "outline",
  [WaveStatus.CANCELLED]: "destructive",
  // Synthetic status used for plan_preview rows shown before approval.
  proposed: "secondary",
};

export default function CampaignDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: campaign, isLoading } = useCampaign(id);

  const approve = useApproveCampaign();
  const pause = usePauseCampaign();
  const resume = useResumeCampaign();
  const cancel = useCancelCampaign();
  const remove = useDeleteCampaign();
  const regenerate = useRegeneratePlan();
  const editPlan = useEditPlan();
  const cancelWave = useCancelWave();

  // Resolve IDs to human-readable names. Both queries are cheap and cached;
  // they fall back gracefully (UUID prefix) while loading.
  const { data: appointmentTypes } = useAppointmentTypes();
  const slotRoster = useSpecificSlotEventRoster(campaign?.event_slot_id);

  const serviceNameById = useMemo(() => {
    const map = new Map<string, string>();
    for (const t of appointmentTypes ?? []) {
      map.set(t.id, t.name);
    }
    return map;
  }, [appointmentTypes]);

  function serviceName(id: string): string {
    return serviceNameById.get(id) ?? `${id.slice(0, 8)}…`;
  }

  const [editingTemplates, setEditingTemplates] = useState<
    Record<string, string> | null
  >(null);
  const [recipientsWaveId, setRecipientsWaveId] = useState<string | null>(null);

  // Roster is the source of truth for volunteer requirements. The campaign's
  // stored goals are a snapshot that the backend syncs whenever the slot's
  // service_config changes — but we also join here so the UI matches the
  // event's Roster section immediately, before the sync has propagated.
  //
  // This memo runs unconditionally so it stays in the same hook-order slot
  // on every render (we mustn't call hooks after the early-return below).
  const rosterServices = slotRoster.data?.services ?? [];
  const rosterByType = useMemo(() => {
    const m = new Map<string, (typeof rosterServices)[number]>();
    for (const s of rosterServices) m.set(s.appointment_type_id, s);
    return m;
  }, [rosterServices]);

  if (isLoading || !campaign) {
    return (
      <div className="py-12 text-center text-sm text-muted-foreground">
        Loading campaign…
      </div>
    );
  }

  const eventInfo = slotRoster.data?.event;
  const eventLabel = eventInfo?.label || "Event";
  const eventDate = eventInfo?.date
    ? format(parseISO(eventInfo.date), "EEE, MMM d, yyyy")
    : "";

  const isAwaitingApproval =
    campaign.status === CampaignStatus.AWAITING_APPROVAL;
  const isTerminal = [
    CampaignStatus.COMPLETED,
    CampaignStatus.CANCELLED,
    CampaignStatus.FAILED,
  ].includes(campaign.status as never);

  const storedGoals = (campaign.goals ?? []) as Array<{
    appointment_type_id: string;
    min_required?: number;
    max_allowed?: number | null;
    target?: number; // legacy
  }>;

  function liveCountForService(typeId: string): number {
    const svc = rosterByType.get(typeId);
    if (!svc) return campaign?.current_signups?.[typeId] ?? 0;
    return svc.signups.filter(
      (sg) => sg.status === "scheduled" || sg.status === "rescheduled"
    ).length;
  }

  const goals = storedGoals.map((g) => {
    const live = rosterByType.get(g.appointment_type_id);
    return {
      appointment_type_id: g.appointment_type_id,
      min_required:
        live?.min_required ?? g.min_required ?? g.target ?? 0,
      max_allowed:
        live?.max_allowed !== undefined ? live.max_allowed : g.max_allowed,
    };
  });

  // Format the wave's offset from the event as "T-Nd" / "T-day" / "T+Nd".
  function timingLabel(scheduledIso: string): string {
    if (!eventInfo?.date) return "—";
    const ev = parseISO(`${eventInfo.date}T${eventInfo.start_time || "00:00"}`);
    const sched = parseISO(scheduledIso);
    const ms = ev.getTime() - sched.getTime();
    const days = Math.round(ms / (1000 * 60 * 60 * 24));
    if (days > 0) return `T-${days}d`;
    if (days === 0) return "T-day";
    return `T+${Math.abs(days)}d`;
  }

  type WaveRow = {
    key: string;
    wave_number: number;
    service_label: string;
    scheduled_at: string;
    status: string;
    sent_count: number;
    signups_attributed: number;
    selection_reason: string | null;
    real_id: string | null; // null for synthetic "proposed" rows
  };

  // Real wave rows (post-approval) take priority. Pre-approval, synthesize
  // rows from plan_preview so the admin sees the same table both before
  // and after approval — only the status changes from "proposed" to
  // "planned" / "sent" / etc.
  const previewWaves: Array<{
    wave_number?: number;
    service_name?: string;
    appointment_type_id?: string;
    scheduled_at_iso?: string;
    target_count?: number;
    rationale?: string;
  }> = (campaign.plan_preview as { waves?: unknown[] } | null)?.waves as never ?? [];

  const waveRows: WaveRow[] =
    campaign.waves.length > 0
      ? campaign.waves.map((w) => ({
          key: w.id,
          wave_number: w.wave_number,
          service_label: serviceName(w.appointment_type_id),
          scheduled_at: w.scheduled_at,
          status: w.status,
          sent_count: w.sent_count,
          signups_attributed: w.signups_attributed,
          selection_reason: w.selection_reason,
          real_id: w.id,
        }))
      : previewWaves.map((p, i) => ({
          key: `preview-${i}`,
          wave_number: p.wave_number ?? i + 1,
          service_label:
            p.service_name ??
            (p.appointment_type_id
              ? serviceName(p.appointment_type_id)
              : "service"),
          scheduled_at: p.scheduled_at_iso ?? "",
          status: "proposed",
          sent_count: 0,
          signups_attributed: 0,
          selection_reason: p.rationale ?? null,
          real_id: null,
        }));

  const currentTemplates =
    editingTemplates ?? (campaign.message_templates ?? {});

  function saveTemplates() {
    if (!editingTemplates || !campaign) return;
    editPlan.mutate(
      { id: campaign.id, body: { message_templates: editingTemplates } },
      { onSuccess: () => setEditingTemplates(null) }
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Button asChild variant="ghost" size="icon">
          <Link to="/campaigns">
            <ArrowLeft className="h-4 w-4" />
          </Link>
        </Button>
        <div className="flex-1">
          <h1 className="text-2xl font-semibold tracking-tight">
            {eventLabel}
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Muster{eventDate ? ` · ${eventDate}` : ""}
            {eventInfo?.location ? ` · ${eventInfo.location}` : ""}
          </p>
        </div>
        <Badge variant={STATUS_VARIANT[campaign.status]}>
          {campaign.status}
        </Badge>
      </div>

      {/* Plan + Signups merged — per-service breakdown with per-wave
          signups, plus a completion banner at the top when all slots
          are filled. */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-3">
          <CardTitle className="text-base">Plan</CardTitle>
          <div className="flex items-center gap-2">
            {isAwaitingApproval && (
              <>
                <Button
                  onClick={() => regenerate.mutate(campaign.id)}
                  variant="outline"
                  size="sm"
                  disabled={regenerate.isPending}
                >
                  <RefreshCw className="mr-2 h-3 w-3" />
                  Regenerate
                </Button>
                <Button
                  onClick={() => approve.mutate(campaign.id)}
                  size="sm"
                  disabled={approve.isPending}
                >
                  <CheckCircle className="mr-2 h-3 w-3" />
                  Approve & start
                </Button>
              </>
            )}
            {campaign.status === CampaignStatus.ACTIVE && (
              <Button
                onClick={() => pause.mutate(campaign.id)}
                variant="outline"
                size="sm"
              >
                <PauseCircle className="mr-2 h-3 w-3" />
                Pause
              </Button>
            )}
            {campaign.status === CampaignStatus.PAUSED && (
              <Button
                onClick={() => resume.mutate(campaign.id)}
                variant="outline"
                size="sm"
              >
                <PlayCircle className="mr-2 h-3 w-3" />
                Resume
              </Button>
            )}
            {!isTerminal && (
              <Button
                onClick={() => {
                  if (confirm("Cancel this campaign?")) {
                    cancel.mutate(campaign.id);
                  }
                }}
                variant="ghost"
                size="sm"
              >
                <XCircle className="mr-2 h-3 w-3" />
                Cancel
              </Button>
            )}
            <Button
              onClick={() => {
                const warning = isTerminal
                  ? "Permanently delete this campaign and all its waves, signups, and reports?"
                  : "This campaign is still active. Permanently delete it along with all pending waves, signups, and reports?";
                if (confirm(warning)) {
                  remove.mutate(campaign.id, {
                    onSuccess: () => navigate("/campaigns"),
                  });
                }
              }}
              variant="ghost"
              size="sm"
              disabled={remove.isPending}
              className="text-destructive hover:text-destructive"
            >
              <Trash2 className="mr-2 h-3 w-3" />
              Delete
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <MusterStatusHeadline
            goals={goals}
            liveCountForService={liveCountForService}
            status={campaign.status as CampaignStatus}
            waves={campaign.waves}
          />

          {campaign.plan_summary && (
            <details className="text-sm">
              <summary className="cursor-pointer text-xs font-medium uppercase tracking-wide text-muted-foreground hover:text-foreground">
                Planner notes
              </summary>
              <p className="mt-2 whitespace-pre-wrap text-sm text-muted-foreground">
                {campaign.plan_summary}
              </p>
            </details>
          )}

          {/* Per-service breakdown — goal progress on top, then the
              waves targeting that service with sent count + signups
              attributed in each wave. Replaces the standalone Goals
              progress + standalone Waves table for a single coherent
              "what was planned and what came in" view. */}
          <div className="space-y-4">
            {goals.map((g) => {
              const signed = liveCountForService(g.appointment_type_id);
              const min = g.min_required;
              const max = g.max_allowed ?? null;
              const serviceWaves = campaign.waves
                .filter((w) => w.appointment_type_id === g.appointment_type_id)
                .sort((a, b) => a.wave_number - b.wave_number);
              return (
                <ServiceWaveBreakdown
                  key={g.appointment_type_id}
                  label={serviceName(g.appointment_type_id)}
                  signups={signed}
                  min={min}
                  max={max}
                  waves={serviceWaves}
                  campaignStatus={campaign.status as CampaignStatus}
                  onCancelWave={(id) => cancelWave.mutate(id)}
                  onViewRecipients={(id) => setRecipientsWaveId(id)}
                />
              );
            })}
          </div>
        </CardContent>
      </Card>

      {/* Editable message templates (pre-approval only) */}
      {isAwaitingApproval && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Message templates</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {Object.entries(currentTemplates).length === 0 ? (
              <p className="text-sm text-muted-foreground">
                The planner has not produced any templates yet.
              </p>
            ) : (
              Object.entries(currentTemplates).map(([wave, tpl]) => (
                <div key={wave}>
                  <Label className="text-xs">Wave {wave}</Label>
                  <Textarea
                    rows={2}
                    value={tpl as string}
                    onChange={(e) =>
                      setEditingTemplates({
                        ...currentTemplates,
                        [wave]: e.target.value,
                      })
                    }
                  />
                </div>
              ))
            )}
            <div className="text-xs text-muted-foreground">
              Supported tokens: {"{first_name}"}, {"{event_label}"},{" "}
              {"{event_date}"}, {"{event_location}"}, {"{service_name}"}.
            </div>
            {editingTemplates && (
              <div className="flex gap-2">
                <Button
                  size="sm"
                  onClick={saveTemplates}
                  disabled={editPlan.isPending}
                >
                  Save templates
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => setEditingTemplates(null)}
                >
                  Cancel
                </Button>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Waves */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Waves</CardTitle>
        </CardHeader>
        <CardContent>
          {waveRows.length === 0 ? (
            <p className="py-4 text-center text-sm text-muted-foreground">
              No waves yet. The planner will propose a schedule shortly.
            </p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>#</TableHead>
                  <TableHead>Service</TableHead>
                  <TableHead>Timing</TableHead>
                  <TableHead>Scheduled</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Sent</TableHead>
                  <TableHead>Signups</TableHead>
                  <TableHead>Reason</TableHead>
                  <TableHead></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {waveRows.map((w) => {
                  const isClickable = !!w.real_id;
                  return (
                    <TableRow
                      key={w.key}
                      className={
                        isClickable
                          ? "cursor-pointer hover:bg-muted/40 transition-colors"
                          : undefined
                      }
                      onClick={() => {
                        if (isClickable) setRecipientsWaveId(w.real_id);
                      }}
                      title={
                        isClickable
                          ? "Click to see who this wave was sent to"
                          : undefined
                      }
                    >
                      <TableCell className="font-mono text-xs">
                        {w.wave_number}
                      </TableCell>
                      <TableCell className="text-sm">
                        {w.service_label}
                      </TableCell>
                      <TableCell className="text-xs font-mono text-muted-foreground">
                        {w.scheduled_at ? timingLabel(w.scheduled_at) : "—"}
                      </TableCell>
                      <TableCell className="text-xs">
                        {w.scheduled_at
                          ? format(parseISO(w.scheduled_at), "MMM d HH:mm")
                          : "—"}
                      </TableCell>
                      <TableCell>
                        {(() => {
                          const eff = effectiveWaveStatus(
                            w.status,
                            campaign.status as CampaignStatus,
                          );
                          const auto = eff !== w.status;
                          return (
                            <>
                              <Badge variant={WAVE_VARIANT[eff] ?? "outline"}>
                                {eff}
                              </Badge>
                              {auto && (
                                <span
                                  className="ml-1 text-[10px] text-muted-foreground"
                                  title="Auto-cancelled because the muster completed before this wave fired."
                                >
                                  auto
                                </span>
                              )}
                            </>
                          );
                        })()}
                      </TableCell>
                      <TableCell>{w.sent_count}</TableCell>
                      <TableCell>{w.signups_attributed}</TableCell>
                      <TableCell className="max-w-[300px] truncate text-xs text-muted-foreground">
                        {w.selection_reason ?? "—"}
                      </TableCell>
                      <TableCell>
                        {w.real_id &&
                          effectiveWaveStatus(
                            w.status,
                            campaign.status as CampaignStatus,
                          ) === WaveStatus.PLANNED && (
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={(e) => {
                                e.stopPropagation();
                                cancelWave.mutate(w.real_id!);
                              }}
                            >
                              Cancel
                            </Button>
                          )}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Recent reports */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Recent daily reports</CardTitle>
        </CardHeader>
        <CardContent>
          {campaign.recent_reports.length === 0 ? (
            <p className="text-sm text-muted-foreground">No reports yet.</p>
          ) : (
            <ul className="space-y-3">
              {campaign.recent_reports.map((r) => (
                <li key={r.id} className="border-l-2 border-muted pl-3">
                  <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                    {format(parseISO(r.report_date), "MMM d, yyyy")} ·{" "}
                    {r.sent_via}
                  </div>
                  <div className="mt-1 text-sm">
                    {r.narrative ?? <span className="italic">no narrative</span>}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      {campaign.status === CampaignStatus.FAILED && (
        <Card className="border-destructive">
          <CardContent className="flex items-start gap-3 p-4">
            <AlertCircle className="mt-0.5 h-4 w-4 text-destructive" />
            <div className="text-sm">
              Planner failed. Try{" "}
              <button
                className="underline"
                onClick={() => regenerate.mutate(campaign.id)}
              >
                regenerating
              </button>
              .
            </div>
          </CardContent>
        </Card>
      )}

      <WaveRecipientsDialog
        waveId={recipientsWaveId}
        onClose={() => setRecipientsWaveId(null)}
      />
    </div>
  );
}

function WaveRecipientsDialog({
  waveId,
  onClose,
}: {
  waveId: string | null;
  onClose: () => void;
}) {
  const { data, isLoading } = useWaveRecipients(waveId);
  return (
    <Dialog open={!!waveId} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>
            {data
              ? `Wave ${data.wave_number} recipients`
              : "Wave recipients"}
          </DialogTitle>
          <DialogDescription>
            {data
              ? `${data.recipient_count} contact${
                  data.recipient_count === 1 ? "" : "s"
                } targeted · ${data.sent_count} delivered · ${
                  data.signups_attributed
                } signed up`
              : "Loading…"}
          </DialogDescription>
        </DialogHeader>
        {isLoading ? (
          <p className="py-8 text-center text-sm text-muted-foreground">
            Loading recipients…
          </p>
        ) : !data ? null : (
          <div className="space-y-4">
            {/* Template the wave was sent with */}
            {data.template_message && (
              <div className="rounded-md border bg-muted/30 p-3">
                <div className="mb-1.5 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Message template
                </div>
                <p className="whitespace-pre-wrap font-mono text-xs text-foreground">
                  {data.template_message}
                </p>
                <p className="mt-1.5 text-[10px] text-muted-foreground">
                  Tokens like {"{first_name}"} are substituted per recipient
                  below.
                </p>
              </div>
            )}

            {data.recipients.length === 0 ? (
              <p className="py-8 text-center text-sm text-muted-foreground">
                This wave has no targeted recipients on record. Recruiter
                resolves recipients only at send time, so unsent waves
                (planned, skipped, cancelled) won't show any contacts here.
              </p>
            ) : (
              <ul className="max-h-[420px] space-y-2 overflow-y-auto pr-1">
                {data.recipients.map((r) => (
                  <li
                    key={r.contact_id}
                    className="rounded-md border bg-card p-3"
                  >
                    <div className="mb-1.5 flex items-center justify-between gap-2 text-sm">
                      <span
                        className={
                          r.deleted
                            ? "italic text-muted-foreground"
                            : "font-medium"
                        }
                      >
                        {r.deleted
                          ? "(deleted contact)"
                          : r.name || "(unnamed)"}
                      </span>
                      <span className="font-mono text-xs text-muted-foreground">
                        {r.phone || "—"}
                      </span>
                    </div>
                    {r.message ? (
                      <p className="whitespace-pre-wrap rounded bg-muted/50 px-2 py-1.5 font-mono text-[11px] leading-snug text-foreground">
                        {r.message}
                      </p>
                    ) : (
                      <p className="text-xs italic text-muted-foreground">
                        No delivered text on record.
                      </p>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

function GoalProgress({
  label,
  signups,
  min,
  max,
}: {
  label: string;
  signups: number;
  min: number;
  max: number | null;
}) {
  // Bar scale = max if set, else min. The bar fills proportionally to
  // signups; a thin marker line denotes the min threshold when a max is
  // set so admin can see how much of the fill is "must-have" vs.
  // "stretch goal."
  const scale = max && max > 0 ? max : Math.max(min, 1);
  const fillPct = Math.max(0, Math.min(100, (signups / scale) * 100));
  const minPct =
    max && max > min ? Math.max(0, Math.min(100, (min / scale) * 100)) : null;
  const minMet = signups >= min;
  const maxMet = max != null && signups >= max;

  let fillClass: string;
  if (maxMet) fillClass = "bg-emerald-600 dark:bg-emerald-500";
  else if (minMet) fillClass = "bg-emerald-500 dark:bg-emerald-600";
  else fillClass = "bg-amber-500 dark:bg-amber-600";

  return (
    <li>
      <div className="mb-1 flex items-baseline justify-between gap-2 text-sm">
        <span className="font-medium truncate">{label}</span>
        <span className="shrink-0 text-xs tabular-nums text-muted-foreground">
          <span className="font-semibold text-foreground">{signups}</span>
          {" / "}
          <span>min {min}</span>
          {max != null && (
            <>
              {" · "}
              <span>max {max}</span>
            </>
          )}
        </span>
      </div>
      <div className="relative h-2 w-full overflow-hidden rounded-full bg-muted">
        <div
          className={"h-full transition-all " + fillClass}
          style={{ width: `${fillPct}%` }}
        />
        {minPct !== null && (
          <div
            className="pointer-events-none absolute top-0 h-full w-0.5 bg-foreground/60"
            style={{ left: `${minPct}%` }}
            title={`Min: ${min}`}
          />
        )}
      </div>
    </li>
  );
}

interface OverallStatusGoal {
  appointment_type_id: string;
  min_required: number;
  max_allowed: number | null | undefined;
}

interface OverallStatusWave {
  wave_number: number;
  status: string;
}

/**
 * When the muster is COMPLETED, any waves that hadn't fired yet were
 * either cancelled by the backend (new musters via mark_campaign_completed)
 * or are still in the DB as PLANNED on older musters. Either way, the
 * admin should see them as cancelled — no SMS will ever go out for
 * those.
 */
function effectiveWaveStatus(
  waveStatus: string,
  campaignStatus: CampaignStatus,
): string {
  if (
    campaignStatus === CampaignStatus.COMPLETED &&
    (waveStatus === WaveStatus.PLANNED || waveStatus === "proposed")
  ) {
    return WaveStatus.CANCELLED;
  }
  return waveStatus;
}

function MusterStatusHeadline({
  goals,
  liveCountForService,
  status,
  waves,
}: {
  goals: OverallStatusGoal[];
  liveCountForService: (typeId: string) => number;
  status: CampaignStatus;
  waves: OverallStatusWave[];
}) {
  const totalSigned = goals.reduce(
    (s, g) => s + liveCountForService(g.appointment_type_id),
    0,
  );
  const totalMin = goals.reduce((s, g) => s + (g.min_required ?? 0), 0);
  const totalMax = goals.reduce((s, g) => {
    const max = g.max_allowed ?? g.min_required ?? 0;
    return s + (max > 0 ? max : g.min_required ?? 0);
  }, 0);
  const totalNeed = Math.max(0, totalMin - totalSigned);
  const overallPct = totalMax > 0 ? Math.min(1, totalSigned / totalMax) : 0;

  const isCompleted = status === CampaignStatus.COMPLETED;
  const lastSentWaveNum = waves.reduce<number | null>((acc, w) => {
    if (w.status !== WaveStatus.SENT) return acc;
    if (acc == null || w.wave_number > acc) return w.wave_number;
    return acc;
  }, null);
  const cancelledOrPlanned = waves.filter((w) =>
    isCompleted
      ? w.status === WaveStatus.CANCELLED || w.status === WaveStatus.PLANNED
      : false,
  ).length;

  return (
    <div className="space-y-3">
      {isCompleted && (
        <div className="flex items-start gap-2 rounded-md border border-emerald-300 bg-emerald-50 p-3 text-sm text-emerald-900 dark:border-emerald-900 dark:bg-emerald-950 dark:text-emerald-200">
          <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" />
          <div className="flex-1">
            <p className="font-semibold">
              {lastSentWaveNum != null
                ? `All slots filled with Wave ${lastSentWaveNum}`
                : "All slots filled"}
            </p>
            {cancelledOrPlanned > 0 && (
              <p className="mt-0.5 text-xs">
                {cancelledOrPlanned} unsent wave
                {cancelledOrPlanned === 1 ? "" : "s"} cancelled — no further
                SMS will go out for this muster.
              </p>
            )}
          </div>
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
            Signups
          </p>
          <p className="mt-1 text-2xl font-bold tabular-nums">
            {totalSigned}
            <span className="ml-1 text-base font-normal text-muted-foreground">
              / {totalMin} min · {totalMax} max
            </span>
          </p>
        </div>
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
            Fill
          </p>
          <p className="mt-1 text-2xl font-bold tabular-nums">
            {Math.round(overallPct * 100)}%
            <span
              className={cn(
                "ml-2 text-base font-normal",
                totalNeed > 0
                  ? "text-amber-700 dark:text-amber-400"
                  : "text-emerald-700 dark:text-emerald-400",
              )}
            >
              {totalNeed > 0 ? `${totalNeed} more needed` : "min met"}
            </span>
          </p>
        </div>
      </div>
    </div>
  );
}

interface ServiceBreakdownWave {
  id: string;
  wave_number: number;
  scheduled_at: string | null;
  status: string;
  sent_count: number;
  signups_attributed: number;
}

function ServiceWaveBreakdown({
  label,
  signups,
  min,
  max,
  waves,
  campaignStatus,
  onCancelWave,
  onViewRecipients,
}: {
  label: string;
  signups: number;
  min: number;
  max: number | null;
  waves: ServiceBreakdownWave[];
  campaignStatus: CampaignStatus;
  onCancelWave: (waveId: string) => void;
  onViewRecipients: (waveId: string) => void;
}) {
  const scale = max && max > 0 ? max : Math.max(min, 1);
  const fillPct = Math.max(0, Math.min(100, (signups / scale) * 100));
  const minPct =
    max && max > min ? Math.max(0, Math.min(100, (min / scale) * 100)) : null;
  const minMet = signups >= min;
  const maxMet = max != null && signups >= max;
  const totalContacted = waves.reduce((s, w) => s + (w.sent_count ?? 0), 0);
  const attributedSignups = waves.reduce(
    (s, w) => s + (w.signups_attributed ?? 0),
    0,
  );

  return (
    <div className="rounded-md border bg-card/40 p-3">
      <div className="mb-1.5 flex items-baseline justify-between gap-2">
        <p className="text-sm font-semibold">{label}</p>
        <p className="text-xs tabular-nums text-muted-foreground">
          <span className="font-semibold text-foreground">{signups}</span>
          {" / "}min {min}
          {max != null && max > 0 && (
            <>
              {" · "}max {max}
            </>
          )}
        </p>
      </div>
      <div className="relative mb-3 h-2 w-full overflow-hidden rounded-full bg-muted">
        <div
          className={cn(
            "h-full transition-all",
            maxMet
              ? "bg-emerald-600 dark:bg-emerald-500"
              : minMet
                ? "bg-emerald-500 dark:bg-emerald-600"
                : "bg-amber-500 dark:bg-amber-600",
          )}
          style={{ width: `${fillPct}%` }}
        />
        {minPct !== null && (
          <div
            className="pointer-events-none absolute top-0 h-full w-0.5 bg-foreground/60"
            style={{ left: `${minPct}%` }}
            title={`Min: ${min}`}
          />
        )}
      </div>

      {waves.length === 0 ? (
        <p className="text-xs text-muted-foreground">
          No waves planned for this service yet.
        </p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="h-8 text-[10px] uppercase tracking-wider">
                Wave
              </TableHead>
              <TableHead className="h-8 text-[10px] uppercase tracking-wider">
                Scheduled
              </TableHead>
              <TableHead className="h-8 text-[10px] uppercase tracking-wider">
                Status
              </TableHead>
              <TableHead className="h-8 text-right text-[10px] uppercase tracking-wider">
                Contacted
              </TableHead>
              <TableHead className="h-8 text-right text-[10px] uppercase tracking-wider">
                Signups
              </TableHead>
              <TableHead className="h-8" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {waves.map((w) => {
              const effStatus = effectiveWaveStatus(w.status, campaignStatus);
              const autoCancelled =
                effStatus !== w.status && effStatus === WaveStatus.CANCELLED;
              return (
                <TableRow key={w.id}>
                  <TableCell className="text-xs tabular-nums">
                    #{w.wave_number}
                  </TableCell>
                  <TableCell className="text-xs">
                    {w.scheduled_at
                      ? format(parseISO(w.scheduled_at), "MMM d HH:mm")
                      : "—"}
                  </TableCell>
                  <TableCell>
                    <Badge variant={WAVE_VARIANT[effStatus] ?? "outline"}>
                      {effStatus}
                    </Badge>
                    {autoCancelled && (
                      <span
                        className="ml-1 text-[10px] text-muted-foreground"
                        title="Auto-cancelled because the muster completed before this wave fired."
                      >
                        auto
                      </span>
                    )}
                  </TableCell>
                  <TableCell className="text-right text-xs tabular-nums">
                    {w.sent_count}
                  </TableCell>
                  <TableCell className="text-right text-xs tabular-nums">
                    {w.signups_attributed}
                  </TableCell>
                  <TableCell className="text-right">
                    <div className="flex justify-end gap-1">
                      {w.sent_count > 0 && (
                        <Button
                          size="sm"
                          variant="ghost"
                          className="h-7 px-2 text-[11px]"
                          onClick={() => onViewRecipients(w.id)}
                        >
                          Recipients
                        </Button>
                      )}
                      {effStatus === WaveStatus.PLANNED && (
                        <Button
                          size="sm"
                          variant="ghost"
                          className="h-7 px-2 text-[11px]"
                          onClick={() => onCancelWave(w.id)}
                        >
                          Cancel
                        </Button>
                      )}
                    </div>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      )}
      {waves.length > 0 && (
        <p className="mt-2 text-[11px] text-muted-foreground">
          Total contacted: {totalContacted} · signups attributed:{" "}
          {attributedSignups}
        </p>
      )}
    </div>
  );
}

