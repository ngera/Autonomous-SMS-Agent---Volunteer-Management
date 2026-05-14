import { useMemo, useState } from "react";
import { DashboardGreeting } from "../components/dashboard-greeting";
import { DashboardKpiRow } from "../components/dashboard-kpi-row";
import { WeeklyScheduleList } from "../components/weekly-schedule-list";
import { NeedsAttentionPanel } from "../components/needs-attention-panel";
import { QuickActionsPanel } from "../components/quick-actions-panel";
import { UpcomingOneTimeEvents } from "../components/upcoming-one-time-events";
import {
  useDashboardSummary,
  useSendSlotReminder,
  useWeeklySlotStatuses,
} from "../hooks/use-dashboard";
import { aggregateBySchedule, fillPercent, type AggregatedEvent } from "../lib/aggregate";
import { AnnouncementForm } from "@/features/announcements/components/announcement-form";
import { useCreateAnnouncement } from "@/features/announcements/hooks/use-announcements";
import type { EventContext } from "@/types/api";

export function DashboardPage() {
  const summary = useDashboardSummary();
  const weeklySlots = useWeeklySlotStatuses(0);
  const sendReminder = useSendSlotReminder();
  const createAnnouncement = useCreateAnnouncement();
  const [announcementCtx, setAnnouncementCtx] = useState<EventContext | null>(null);
  const [announcementOpen, setAnnouncementOpen] = useState(false);

  const aggregated = useMemo(
    () => aggregateBySchedule(weeklySlots.data ?? []),
    [weeklySlots.data]
  );

  const recurringCount = useMemo(
    () => aggregated.filter((e) => e.source === "recurring").length,
    [aggregated]
  );
  const oneTimeCount = useMemo(
    () => aggregated.filter((e) => e.source === "one_time").length,
    [aggregated]
  );
  const needingVolunteers = useMemo(
    () => aggregated.filter((e) => e.any_needs_more).length,
    [aggregated]
  );
  const understaffed = useMemo(() => {
    const candidates = aggregated.filter((e) => e.any_needs_more);
    if (candidates.length === 0) return null;
    return candidates.reduce((worst, ev) =>
      fillPercent(ev.booked, ev.max_allowed) <
      fillPercent(worst.booked, worst.max_allowed)
        ? ev
        : worst
    );
  }, [aggregated]);
  const oneTimeEvents = useMemo(
    () => aggregated.filter((e) => e.source === "one_time"),
    [aggregated]
  );

  const isLoading = summary.isLoading || weeklySlots.isLoading;

  function handleSendAnnouncement(ev: AggregatedEvent) {
    const [start, end] = ev.window_time.split(" – ");
    setAnnouncementCtx({
      event_label: ev.display_name,
      event_date: ev.date,
      event_start_time: start || null,
      event_end_time: end || null,
      event_location: ev.location,
      service_name: ev.services[0]?.service_name ?? null,
      appointment_type_id: ev.services[0]?.appointment_type_id ?? null,
    });
    setAnnouncementOpen(true);
  }

  async function handleSendReminder(ev: AggregatedEvent) {
    const services = ev.services;
    if (services.length === 0) return;
    const label = ev.display_name;
    if (!confirm(`Send reminders for "${label}" on ${ev.date} to opted-in volunteers across ${services.length} service(s)?`)) {
      return;
    }
    let totalSent = 0;
    let totalConfirm = 0;
    for (const svc of services) {
      try {
        const r = await sendReminder.mutateAsync({
          date: ev.date,
          appointmentTypeId: svc.appointment_type_id,
        });
        totalSent += r.sent_signup;
        totalConfirm += r.sent_confirmation;
      } catch (err) {
        console.error("Reminder failed for", svc.service_name, err);
      }
    }
    alert(`Reminders sent: ${totalSent} sign-up · ${totalConfirm} confirmation`);
  }

  return (
    <div className="space-y-6">
      <DashboardGreeting
        eventsThisWeek={aggregated.length}
        needingVolunteers={needingVolunteers}
        isLoading={isLoading}
      />

      <DashboardKpiRow
        totalVolunteers={summary.data?.total_volunteers}
        eventsThisWeek={aggregated.length}
        recurringCount={recurringCount}
        oneTimeCount={oneTimeCount}
        openSlots={summary.data?.slots_needing_bookings}
        monthlyBookings={summary.data?.monthly_bookings}
        isLoading={isLoading}
      />

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <WeeklyScheduleList
            events={aggregated}
            isLoading={weeklySlots.isLoading}
            onSendAnnouncement={handleSendAnnouncement}
            onSendReminder={handleSendReminder}
          />
          <UpcomingOneTimeEvents
            events={oneTimeEvents}
            isLoading={weeklySlots.isLoading}
          />
        </div>

        <div className="space-y-6">
          <NeedsAttentionPanel
            understaffed={understaffed}
            unreviewedSuspensions={summary.data?.unreviewed_suspensions_count ?? 0}
            suspendedOrBanned={summary.data?.suspended_or_banned_count ?? 0}
            isLoading={isLoading}
          />
          <QuickActionsPanel />
        </div>
      </div>

      <AnnouncementForm
        open={announcementOpen}
        onOpenChange={(open) => {
          setAnnouncementOpen(open);
          if (!open) setAnnouncementCtx(null);
        }}
        initialEventContext={announcementCtx}
        isLoading={createAnnouncement.isPending}
        onSubmit={(data) =>
          createAnnouncement.mutate(data, {
            onSuccess: () => {
              setAnnouncementOpen(false);
              setAnnouncementCtx(null);
            },
            onError: (err: unknown) => {
              const detail =
                (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
                (err as Error)?.message ||
                "Failed to send announcement";
              alert(`Could not send announcement: ${detail}`);
            },
          })
        }
      />
    </div>
  );
}
