import { useState } from "react";
import { PageHeader } from "@/components/shared/page-header";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { PendingAlerts } from "../components/pending-alerts";
import { VolunteerBreakdown } from "../components/volunteer-breakdown";
import { WeeklySlotsTable } from "../components/weekly-slots-table";
import {
  useDashboardSummary,
  useWeeklySlotStatuses,
} from "../hooks/use-dashboard";

export function DashboardPage() {
  const summary = useDashboardSummary();
  const [weekOffset, setWeekOffset] = useState(0);
  const weeklySlots = useWeeklySlotStatuses(weekOffset);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Dashboard"
        description="Volunteer scheduling overview."
      />

      <PendingAlerts data={summary.data} isLoading={summary.isLoading} />

      <Tabs defaultValue="availability">
        <TabsList>
          <TabsTrigger value="availability">Weekly Availability</TabsTrigger>
          <TabsTrigger value="coverage">Volunteer Coverage (30 Days)</TabsTrigger>
        </TabsList>

        <TabsContent value="availability" className="mt-4">
          <WeeklySlotsTable
            data={weeklySlots.data}
            isLoading={weeklySlots.isLoading}
            weekOffset={weekOffset}
            onPrevWeek={() => setWeekOffset((o) => o - 7)}
            onNextWeek={() => setWeekOffset((o) => o + 7)}
            onResetWeek={() => setWeekOffset(0)}
          />
        </TabsContent>

        <TabsContent value="coverage" className="mt-4">
          <VolunteerBreakdown data={summary.data} isLoading={summary.isLoading} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
