import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { PageHeader } from "@/components/shared/page-header";
import { useAuth } from "@/hooks/use-auth";
import { AdminRole } from "@/types/enums";
import { WeeklyScheduleBuilder } from "../components/weekly-schedule-builder";
import { BlockedDatesPanel } from "../components/blocked-dates-panel";
import { SpecificDateSlotsPanel } from "../components/specific-date-slots-panel";
import { SlotPreview } from "../components/slot-preview";
import {
  useAvailabilityRules,
  useUpdateAvailabilityRules,
} from "../hooks/use-availability";

export function AvailabilityPage() {
  const { hasRole } = useAuth();
  const canEdit = hasRole(AdminRole.MANAGER);
  const rules = useAvailabilityRules();
  const updateRules = useUpdateAvailabilityRules();

  return (
    <div className="space-y-6">
      <PageHeader
        title="Availability"
        description="Configure working hours, blocked dates, and view slot previews."
      />

      <Tabs defaultValue="schedule">
        <TabsList>
          <TabsTrigger value="schedule">Weekly Schedule</TabsTrigger>
          <TabsTrigger value="specific">Specific Dates</TabsTrigger>
          <TabsTrigger value="blocked">Blocked Dates</TabsTrigger>
          <TabsTrigger value="preview">Slot Preview</TabsTrigger>
        </TabsList>

        <TabsContent value="schedule" className="mt-4">
          <WeeklyScheduleBuilder
            rules={rules.data ?? []}
            onSave={(r) => updateRules.mutate({ rules: r })}
            isSaving={updateRules.isPending}
            canEdit={canEdit}
          />
        </TabsContent>

        <TabsContent value="specific" className="mt-4">
          <SpecificDateSlotsPanel canEdit={canEdit} />
        </TabsContent>

        <TabsContent value="blocked" className="mt-4">
          <BlockedDatesPanel canEdit={canEdit} />
        </TabsContent>

        <TabsContent value="preview" className="mt-4">
          <SlotPreview />
        </TabsContent>
      </Tabs>
    </div>
  );
}
