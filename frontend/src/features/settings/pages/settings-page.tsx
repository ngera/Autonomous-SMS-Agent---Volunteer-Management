import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { PageHeader } from "@/components/shared/page-header";
import { SettingsForm } from "../components/settings-form";
import { AdminUsersTable } from "../components/admin-users-table";
import {
  PromptEditor,
  AI_PROMPT_ENTRIES,
  TEMPLATE_ENTRIES,
} from "../components/prompt-editor";

export function SettingsPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        title="Settings"
        description="System configuration and admin user management."
      />

      <Tabs defaultValue="settings">
        <TabsList>
          <TabsTrigger value="settings">System Settings</TabsTrigger>
          <TabsTrigger value="users">Admin Users</TabsTrigger>
          <TabsTrigger value="prompts">AI Prompts</TabsTrigger>
          <TabsTrigger value="templates">Templates</TabsTrigger>
        </TabsList>

        <TabsContent value="settings" className="mt-4">
          <SettingsForm />
        </TabsContent>

        <TabsContent value="users" className="mt-4">
          <AdminUsersTable />
        </TabsContent>
        <TabsContent value="prompts" className="mt-4">
          <PromptEditor entries={AI_PROMPT_ENTRIES} title="AI Prompts" />
        </TabsContent>
        <TabsContent value="templates" className="mt-4">
          <PromptEditor
            entries={TEMPLATE_ENTRIES}
            title="Templates"
            emptyMessage="Select a tenant from the filter above to view and edit templates."
          />
        </TabsContent>
      </Tabs>
    </div>
  );
}
