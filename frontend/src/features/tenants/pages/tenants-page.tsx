import { useState } from "react";
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
import { useTenants, useCreateTenant, useDeactivateTenant } from "../hooks/use-tenants";
import { TenantForm } from "../components/tenant-form";
import type { TenantCreate } from "@/types/api";

export function TenantsPage() {
  const { data, isLoading } = useTenants();
  const createMutation = useCreateTenant();
  const deactivateMutation = useDeactivateTenant();
  const [showCreate, setShowCreate] = useState(false);

  const handleCreate = (body: TenantCreate) => {
    createMutation.mutate(body, {
      onSuccess: () => setShowCreate(false),
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
              <TableHead>Phone</TableHead>
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
                <TableRow key={tenant.id}>
                  <TableCell className="font-medium">{tenant.name}</TableCell>
                  <TableCell className="text-muted-foreground">{tenant.slug}</TableCell>
                  <TableCell>{tenant.business_name}</TableCell>
                  <TableCell className="text-sm">
                    {tenant.twilio_phone_number || "—"}
                  </TableCell>
                  <TableCell>
                    <Badge variant={tenant.is_active ? "default" : "secondary"}>
                      {tenant.is_active ? "Active" : "Inactive"}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-right">
                    <Button
                      variant="outline"
                      size="sm"
                      asChild
                    >
                      <a href={`/tenants/${tenant.id}`}>Edit</a>
                    </Button>
                    {tenant.is_active && (
                      <Button
                        variant="destructive"
                        size="sm"
                        className="ml-2"
                        onClick={() => {
                          if (confirm("Deactivate this tenant?")) {
                            deactivateMutation.mutate(tenant.id);
                          }
                        }}
                      >
                        Deactivate
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
        <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Create Tenant</DialogTitle>
          </DialogHeader>
          <TenantForm onSubmit={handleCreate} isLoading={createMutation.isPending} />
        </DialogContent>
      </Dialog>
    </div>
  );
}
