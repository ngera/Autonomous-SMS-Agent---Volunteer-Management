import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { PageHeader } from "@/components/shared/page-header";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  useTenants,
  useCreateTenant,
  useDeactivateTenant,
  usePauseTenant,
  useUnpauseTenant,
  useReactivateTenant,
} from "../hooks/use-tenants";
import { TenantForm } from "../components/tenant-form";
import type { TenantCreate, TenantResponse } from "@/types/api";

function TenantStatusBadge({ tenant }: { tenant: TenantResponse }) {
  if (!tenant.is_active) {
    return <Badge variant="destructive">Deactivated</Badge>;
  }
  if (tenant.is_paused) {
    return <Badge variant="secondary" className="bg-yellow-100 text-yellow-800">Paused</Badge>;
  }
  return <Badge variant="default">Active</Badge>;
}

export function TenantsPage() {
  const navigate = useNavigate();
  const { data, isLoading } = useTenants();
  const createMutation = useCreateTenant();
  const deactivateMutation = useDeactivateTenant();
  const pauseMutation = usePauseTenant();
  const unpauseMutation = useUnpauseTenant();
  const reactivateMutation = useReactivateTenant();
  const [showCreate, setShowCreate] = useState(false);

  const handleCreate = (body: TenantCreate) => {
    createMutation.mutate(body, {
      onSuccess: () => setShowCreate(false),
      onError: (error: unknown) => {
        const msg =
          (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
          "Failed to create tenant";
        alert(msg);
      },
    });
  };

  const tenants = data?.items || [];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Tenants"
        description="Manage tenant organizations and their configurations."
        actions={
          <Button onClick={() => setShowCreate(true)}>Create Tenant</Button>
        }
      />

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Slug</TableHead>
              <TableHead>Business Name</TableHead>
              <TableHead>Contact</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              <TableRow>
                <TableCell colSpan={6} className="text-center py-8 text-muted-foreground">
                  Loading...
                </TableCell>
              </TableRow>
            ) : tenants.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6} className="text-center py-8 text-muted-foreground">
                  No tenants found
                </TableCell>
              </TableRow>
            ) : (
              tenants.map((tenant) => (
                <TableRow
                  key={tenant.id}
                  className="cursor-pointer"
                  onClick={() => navigate(`/tenants/${tenant.id}`)}
                >
                  <TableCell className="font-medium">{tenant.name}</TableCell>
                  <TableCell className="text-muted-foreground">{tenant.slug}</TableCell>
                  <TableCell>{tenant.business_name}</TableCell>
                  <TableCell className="text-sm">
                    {tenant.contact_name || tenant.phone || "—"}
                  </TableCell>
                  <TableCell>
                    <TenantStatusBadge tenant={tenant} />
                  </TableCell>
                  <TableCell className="text-right" onClick={(e) => e.stopPropagation()}>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => navigate(`/tenants/${tenant.id}`)}
                    >
                      View
                    </Button>
                    {tenant.is_active && !tenant.is_paused && (
                      <Button
                        variant="outline"
                        size="sm"
                        className="ml-2"
                        onClick={() => pauseMutation.mutate(tenant.id)}
                        disabled={pauseMutation.isPending}
                      >
                        Pause
                      </Button>
                    )}
                    {tenant.is_active && tenant.is_paused && (
                      <Button
                        variant="outline"
                        size="sm"
                        className="ml-2"
                        onClick={() => unpauseMutation.mutate(tenant.id)}
                        disabled={unpauseMutation.isPending}
                      >
                        Unpause
                      </Button>
                    )}
                    {tenant.is_active && (
                      <Button
                        variant="destructive"
                        size="sm"
                        className="ml-2"
                        onClick={() => {
                          if (confirm("Deactivate this tenant? This will prevent all access.")) {
                            deactivateMutation.mutate(tenant.id);
                          }
                        }}
                      >
                        Deactivate
                      </Button>
                    )}
                    {!tenant.is_active && (
                      <Button
                        size="sm"
                        className="ml-2"
                        onClick={() => reactivateMutation.mutate(tenant.id)}
                        disabled={reactivateMutation.isPending}
                      >
                        Reactivate
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      <Dialog open={showCreate} onOpenChange={setShowCreate}>
        <DialogContent className="w-[50vw] sm:max-w-none max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Create Tenant</DialogTitle>
          </DialogHeader>
          <TenantForm onSubmit={handleCreate} isLoading={createMutation.isPending} />
        </DialogContent>
      </Dialog>
    </div>
  );
}
