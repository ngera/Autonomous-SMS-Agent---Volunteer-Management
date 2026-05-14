import { useSearchParams } from "react-router-dom";
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

const TABS = ["schedule", "specific", "blocked", "preview"] as const;
type TabValue = (typeof TABS)[number];

export function AvailabilityPage() {
  const { hasRole } = useAuth();
  const canEdit = hasRole(AdminRole.MANAGER);
  const rules = useAvailabilityRules();
  const updateRules = useUpdateAvailabilityRules();
  const [searchParams, setSearchParams] = useSearchParams();

  // Deep-linking: ?tab=specific&edit_slot=<id> jumps to the Specific Dates
  // tab and auto-opens the edit form for that slot. ?tab=schedule routes to
  // the Weekly Schedule tab for rule edits.
  const rawTab = searchParams.get("tab");
  const tab: TabValue = (TABS as readonly string[]).includes(rawTab ?? "")
    ? (rawTab as TabValue)
    : "schedule";
  const editSlotId = searchParams.get("edit_slot");

  function handleTabChange(next: string) {
    const params = new URLSearchParams(searchParams);
    params.set("tab", next);
    // Drop deep-link payload when the admin switches away on their own.
    if (next !== "specific") params.delete("edit_slot");
    setSearchParams(params, { replace: true });
  }

  function clearEditSlotParam() {
    const params = new URLSearchParams(searchParams);
    params.delete("edit_slot");
    setSearchParams(params, { replace: true });
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Schedule Setup"
        description="Configure working hours, blocked dates, and view slot previews."
      />

      <Tabs value={tab} onValueChange={handleTabChange}>
        <TabsList>
          <TabsTrigger value="schedule">Weekly Schedule</TabsTrigger>
          <TabsTrigger value="specific">Specific Dates</TabsTrigger>
          <TabsTrigger value="blocked">Blocked Dates</TabsTrigger>
          <TabsTrigger value="preview">Slot Preview</TabsTrigger>
        </TabsList>

        <TabsContent value="schedule" className="mt-4">
          <WeeklyScheduleBuilder
            rules={rules.data ?? []}
            onSave={(r) =>
              updateRules.mutate(
                { rules: r },
                {
                  onError: (err: unknown) => {
                    const detail =
                      (err as { response?: { data?: { detail?: string } } })?.response?.data
                        ?.detail || (err as Error)?.message || "Failed to save schedule";
                    alert(`Could not save schedule: ${detail}`);
                  },
                }
              )
            }
            isSaving={updateRules.isPending}
            canEdit={canEdit}
          />
        </TabsContent>

        <TabsContent value="specific" className="mt-4">
          <SpecificDateSlotsPanel
            canEdit={canEdit}
            editSlotId={editSlotId}
            onConsumeEditSlot={clearEditSlotParam}
          />
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
