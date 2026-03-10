import { PageHeader } from "@/components/shared/page-header";
import { RetentionCards } from "../components/retention-cards";
import { BookingVolumeChart } from "../components/booking-volume-chart";
import { RevenueChart } from "../components/revenue-chart";
import { ConsentFunnelChart } from "../components/consent-funnel-chart";

export function AnalyticsPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        title="Analytics"
        description="Booking volume, revenue, retention, and consent metrics."
      />

      <RetentionCards />

      <div className="grid gap-6 lg:grid-cols-2">
        <BookingVolumeChart />
        <RevenueChart />
      </div>

      <ConsentFunnelChart />
    </div>
  );
}
