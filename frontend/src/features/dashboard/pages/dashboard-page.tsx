import { PageHeader } from "@/components/shared/page-header";
import { KpiCards } from "../components/kpi-cards";
import { PendingAlerts } from "../components/pending-alerts";
import { TodaysBookingsTable } from "../components/todays-bookings-table";
import {
  useDashboardSummary,
  useTodaysBookings,
} from "../hooks/use-dashboard";

export function DashboardPage() {
  const summary = useDashboardSummary();
  const todaysBookings = useTodaysBookings();

  return (
    <div className="space-y-6">
      <PageHeader
        title="Dashboard"
        description="Overview of today's activity and monthly performance."
      />

      <PendingAlerts data={summary.data} isLoading={summary.isLoading} />

      <KpiCards data={summary.data} isLoading={summary.isLoading} />

      <div>
        <h3 className="text-lg font-semibold mb-3">Today's Bookings</h3>
        <TodaysBookingsTable
          data={todaysBookings.data}
          isLoading={todaysBookings.isLoading}
        />
      </div>
    </div>
  );
}
