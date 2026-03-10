import { useState } from "react";
import { Send } from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/shared/page-header";
import { useAuth } from "@/hooks/use-auth";
import { AdminRole } from "@/types/enums";
import { ReminderAnalyticsCards } from "../components/reminder-analytics-cards";
import { UpcomingRemindersTable } from "../components/upcoming-reminders-table";
import { ReminderHistoryTable } from "../components/reminder-history-table";
import { TriggerReminderDialog } from "../components/trigger-reminder-dialog";

export function RemindersPage() {
  const { hasRole } = useAuth();
  const canEdit = hasRole(AdminRole.MANAGER);
  const [showTrigger, setShowTrigger] = useState(false);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Reminders"
        description="View upcoming reminders, history, and conversion analytics."
        actions={
          canEdit ? (
            <Button size="sm" onClick={() => setShowTrigger(true)}>
              <Send className="mr-1 h-3 w-3" />
              Trigger Reminder
            </Button>
          ) : undefined
        }
      />

      <ReminderAnalyticsCards />

      <Tabs defaultValue="upcoming">
        <TabsList>
          <TabsTrigger value="upcoming">Upcoming</TabsTrigger>
          <TabsTrigger value="history">History</TabsTrigger>
        </TabsList>

        <TabsContent value="upcoming" className="mt-4">
          <UpcomingRemindersTable canEdit={canEdit} />
        </TabsContent>

        <TabsContent value="history" className="mt-4">
          <ReminderHistoryTable />
        </TabsContent>
      </Tabs>

      <TriggerReminderDialog
        open={showTrigger}
        onClose={() => setShowTrigger(false)}
      />
    </div>
  );
}
