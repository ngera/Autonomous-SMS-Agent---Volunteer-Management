import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { StatusBadge } from "@/components/shared/status-badge";
import { formatPhone } from "@/lib/utils";
import { useAuth } from "@/hooks/use-auth";
import { AdminRole, ContactSex } from "@/types/enums";
import type { CustomerResponse, CustomerUpdate } from "@/types/api";
import { useUpdateCustomer } from "../hooks/use-customers";
import { useAppointmentTypes } from "@/features/appointment-types/hooks/use-appointment-types";

const SEX_LABELS: Record<string, string> = {
  [ContactSex.MALE]: "Male",
  [ContactSex.FEMALE]: "Female",
  [ContactSex.NON_BINARY]: "Non-binary",
  [ContactSex.PREFER_NOT_TO_SAY]: "Prefer not to say",
};

interface CustomerInfoCardProps {
  customer: CustomerResponse;
}

export function CustomerInfoCard({ customer }: CustomerInfoCardProps) {
  const { hasRole } = useAuth();
  const canEdit = hasRole(AdminRole.MANAGER);
  const updateCustomer = useUpdateCustomer();
  const { data: appointmentTypes } = useAppointmentTypes();

  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(customer.name ?? "");
  const [email, setEmail] = useState(customer.email ?? "");
  const [sex, setSex] = useState(customer.sex ?? "");

  function handleSave() {
    const body: CustomerUpdate = {
      name: name || undefined,
      email: email || undefined,
    };
    if (sex) {
      body.sex = sex;
    }
    updateCustomer.mutate(
      { phone: customer.phone, body },
      { onSuccess: () => setEditing(false) }
    );
  }

  const prefTypes = (appointmentTypes ?? []).filter((t) =>
    customer.preferred_appointment_type_ids?.includes(t.id)
  );

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
            <div className="space-y-1">
              <Label>Sex</Label>
              <Select
                value={sex}
                onValueChange={(next) => setSex(next ?? "")}
              >
                <SelectTrigger className="w-full min-w-0">
                  <SelectValue placeholder="Select...">
                    {(val) => {
                      const v = val as string | null | undefined;
                      if (v == null || v === "") return "Select...";
                      return SEX_LABELS[v] ?? v;
                    }}
                  </SelectValue>
                </SelectTrigger>
                <SelectContent>
                  {Object.entries(SEX_LABELS).map(([value, label]) => (
                    <SelectItem key={value} value={value}>
                      {label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="flex gap-2">
              <Button size="sm" onClick={handleSave} disabled={updateCustomer.isPending}>
                {updateCustomer.isPending ? "Saving..." : "Save"}
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => {
                  setName(customer.name ?? "");
                  setEmail(customer.email ?? "");
                  setSex(customer.sex ?? "");
                  setEditing(false);
                }}
              >
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
            <div>
              <Label className="text-muted-foreground">Sex</Label>
              <p className="font-medium">
                {customer.sex ? SEX_LABELS[customer.sex] || customer.sex : "—"}
              </p>
            </div>
            {prefTypes.length > 0 && (
              <div>
                <Label className="text-muted-foreground">Preferred Appointment Types</Label>
                <div className="flex flex-wrap gap-1 mt-1">
                  {prefTypes.map((t) => (
                    <Badge key={t.id} variant="secondary">{t.name}</Badge>
                  ))}
                </div>
              </div>
            )}
            {canEdit && (
              <Button
                size="sm"
                variant="outline"
                onClick={() => {
                  setName(customer.name ?? "");
                  setEmail(customer.email ?? "");
                  setSex(customer.sex ?? "");
                  setEditing(true);
                }}
              >
                Edit
              </Button>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}
