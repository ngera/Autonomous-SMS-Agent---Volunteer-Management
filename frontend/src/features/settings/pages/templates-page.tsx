import { PageHeader } from "@/components/shared/page-header";
import { PromptEditor, TEMPLATE_ENTRIES } from "../components/prompt-editor";

export function TemplatesPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        title="Templates"
        description="Message templates the system uses for event-tied announcements and volunteer reminders. Edits are saved per-tenant."
      />
      <PromptEditor
        entries={TEMPLATE_ENTRIES}
        title="Templates"
        emptyMessage="Select a tenant from the filter above to view and edit templates."
      />
    </div>
  );
}
