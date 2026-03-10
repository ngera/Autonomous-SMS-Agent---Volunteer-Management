import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { PageHeader } from "@/components/shared/page-header";
import { SettingsForm } from "../components/settings-form";
import { AdminUsersTable } from "../components/admin-users-table";

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
        </TabsList>

        <TabsContent value="settings" className="mt-4">
          <SettingsForm />
        </TabsContent>

        <TabsContent value="users" className="mt-4">
          <AdminUsersTable />
        </TabsContent>
      </Tabs>
    </div>
  );
}
