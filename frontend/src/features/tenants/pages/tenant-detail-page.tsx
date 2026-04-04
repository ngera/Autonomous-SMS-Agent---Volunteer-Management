import { useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { ArrowLeft, Pause, Play, Power, PowerOff } from "lucide-react";
import { PageHeader } from "@/components/shared/page-header";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  useTenant,
  useUpdateTenant,
  usePauseTenant,
  useUnpauseTenant,
  useDeactivateTenant,
  useReactivateTenant,
} from "../hooks/use-tenants";
import { TenantForm } from "../components/tenant-form";
import { TenantInfoCard } from "../components/tenant-info-card";
import { TenantUsersTab } from "../components/tenant-users-tab";
import { useTenantFilter } from "@/context/tenant-filter-context";
import type { TenantCreate, TenantUpdate } from "@/types/api";

export function TenantDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: tenant, isLoading } = useTenant(id || "");
  const updateMutation = useUpdateTenant();
  const pauseMutation = usePauseTenant();
  const unpauseMutation = useUnpauseTenant();
  const deactivateMutation = useDeactivateTenant();
  const reactivateMutation = useReactivateTenant();
  const { setSelectedTenantIds } = useTenantFilter();

  // Set tenant context via the filter (single source of truth for X-Tenant-Id)
  useEffect(() => {
    if (id) {
      setSelectedTenantIds([id]);
    }
  }, [id, setSelectedTenantIds]);

  if (isLoading || !tenant) {
    return <div className="p-8 text-center text-muted-foreground">Loading...</div>;
  }

  const handleProfileSubmit = (data: TenantCreate) => {
    const update: TenantUpdate = {};
    for (const [key, value] of Object.entries(data)) {
      if (value !== "" && value !== undefined) {
        (update as Record<string, unknown>)[key] = value;
      }
    }
    updateMutation.mutate({ id: tenant.id, body: update });
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title={tenant.name}
        description={tenant.business_name}
        actions={
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={() => navigate("/tenants")}>
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back
            </Button>
            {tenant.is_active && !tenant.is_paused && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => pauseMutation.mutate(tenant.id)}
                disabled={pauseMutation.isPending}
              >
                <Pause className="mr-2 h-4 w-4" />
                Pause
              </Button>
            )}
            {tenant.is_active && tenant.is_paused && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => unpauseMutation.mutate(tenant.id)}
                disabled={unpauseMutation.isPending}
              >
                <Play className="mr-2 h-4 w-4" />
                Unpause
              </Button>
            )}
            {tenant.is_active && (
              <Button
                variant="destructive"
                size="sm"
                onClick={() => {
                  if (confirm("Deactivate this tenant? This will prevent all access.")) {
                    deactivateMutation.mutate(tenant.id);
                  }
                }}
              >
                <PowerOff className="mr-2 h-4 w-4" />
                Deactivate
              </Button>
            )}
            {!tenant.is_active && (
              <Button
                size="sm"
                onClick={() => reactivateMutation.mutate(tenant.id)}
                disabled={reactivateMutation.isPending}
              >
                <Power className="mr-2 h-4 w-4" />
                Reactivate
              </Button>
            )}
          </div>
        }
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Left sidebar */}
        <div className="lg:col-span-1">
          <TenantInfoCard tenant={tenant} />
        </div>

        {/* Right content - tabs */}
        <div className="lg:col-span-2">
          <Tabs defaultValue="profile">
            <TabsList>
              <TabsTrigger value="profile">Profile</TabsTrigger>
              <TabsTrigger value="users">Users</TabsTrigger>
            </TabsList>

            <TabsContent value="profile" className="mt-4">
              <TenantForm
                tenant={tenant}
                onSubmit={handleProfileSubmit}
                isLoading={updateMutation.isPending}
              />
            </TabsContent>

            <TabsContent value="users" className="mt-4">
              <TenantUsersTab tenantId={id || ""} />
            </TabsContent>
          </Tabs>
        </div>
      </div>
    </div>
  );
}
