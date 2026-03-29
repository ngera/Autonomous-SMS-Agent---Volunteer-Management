import { useParams, useNavigate } from "react-router-dom";
import { PageHeader } from "@/components/shared/page-header";
import { Button } from "@/components/ui/button";
import { useTenant, useUpdateTenant } from "../hooks/use-tenants";
import { TenantForm } from "../components/tenant-form";
import type { TenantCreate, TenantUpdate } from "@/types/api";

export function TenantDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: tenant, isLoading } = useTenant(id || "");
  const updateMutation = useUpdateTenant();

  if (isLoading || !tenant) {
    return <div className="p-8 text-center text-muted-foreground">Loading...</div>;
  }

  const handleSubmit = (data: TenantCreate) => {
    // Filter out empty credential fields so they don't overwrite existing values
    const update: TenantUpdate = {};
    for (const [key, value] of Object.entries(data)) {
      if (value !== "" && value !== undefined) {
        (update as Record<string, unknown>)[key] = value;
      }
    }

    updateMutation.mutate(
      { id: tenant.id, body: update },
      { onSuccess: () => navigate("/tenants") }
    );
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title={`Edit: ${tenant.name}`}
        description={`Slug: ${tenant.slug}`}
        actions={
          <Button variant="outline" onClick={() => navigate("/tenants")}>
            Back to Tenants
          </Button>
        }
      />
      <TenantForm
        tenant={tenant}
        onSubmit={handleSubmit}
        isLoading={updateMutation.isPending}
      />
    </div>
  );
}
