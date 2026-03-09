import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { StatusBadge } from "@/components/shared/status-badge";
import { formatPhone } from "@/lib/utils";
import { useAuth } from "@/hooks/use-auth";
import { AdminRole } from "@/types/enums";
import type { CustomerResponse } from "@/types/api";
import { useUpdateCustomer } from "../hooks/use-customers";

interface CustomerInfoCardProps {
  customer: CustomerResponse;
}

export function CustomerInfoCard({ customer }: CustomerInfoCardProps) {
  const { hasRole } = useAuth();
  const canEdit = hasRole(AdminRole.MANAGER);
  const updateCustomer = useUpdateCustomer();

  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(customer.name ?? "");
  const [email, setEmail] = useState(customer.email ?? "");

  function handleSave() {
    updateCustomer.mutate(
      {
        phone: customer.phone,
        body: { name: name || undefined, email: email || undefined },
      },
      { onSuccess: () => setEditing(false) }
    );
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>Contact Information</CardTitle>
        {customer.consent_status && (
          <StatusBadge type="consent" value={customer.consent_status} />
        )}
      </CardHeader>
      <CardContent className="space-y-4">
        <div>
          <Label className="text-muted-foreground">Phone</Label>
          <p className="font-medium">{formatPhone(customer.phone)}</p>
        </div>

        {editing ? (
          <>
            <div className="space-y-1">
              <Label>Name</Label>
              <Input value={name} onChange={(e) => setName(e.target.value)} />
            </div>
            <div className="space-y-1">
              <Label>Email</Label>
              <Input value={email} onChange={(e) => setEmail(e.target.value)} type="email" />
            </div>
            <div className="flex gap-2">
              <Button size="sm" onClick={handleSave} disabled={updateCustomer.isPending}>
                {updateCustomer.isPending ? "Saving..." : "Save"}
              </Button>
              <Button size="sm" variant="outline" onClick={() => setEditing(false)}>
                Cancel
              </Button>
            </div>
          </>
        ) : (
          <>
            <div>
              <Label className="text-muted-foreground">Name</Label>
              <p className="font-medium">{customer.name || "—"}</p>
            </div>
            <div>
              <Label className="text-muted-foreground">Email</Label>
              <p className="font-medium">{customer.email || "—"}</p>
            </div>
            {canEdit && (
              <Button size="sm" variant="outline" onClick={() => setEditing(true)}>
                Edit
              </Button>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}
