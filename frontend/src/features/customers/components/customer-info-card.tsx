import { Pencil } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { StatusBadge } from "@/components/shared/status-badge";
import { formatPhone } from "@/lib/utils";
import { useAuth } from "@/hooks/use-auth";
import { AdminRole, ContactSex } from "@/types/enums";
import type { CustomerResponse } from "@/types/api";
import { useAppointmentTypes } from "@/features/appointment-types/hooks/use-appointment-types";

const SEX_LABELS: Record<string, string> = {
  [ContactSex.MALE]: "Male",
  [ContactSex.FEMALE]: "Female",
  [ContactSex.NON_BINARY]: "Non-binary",
  [ContactSex.PREFER_NOT_TO_SAY]: "Prefer not to say",
};

interface CustomerInfoCardProps {
  customer: CustomerResponse;
  onEditClick?: () => void;
}

export function CustomerInfoCard({ customer, onEditClick }: CustomerInfoCardProps) {
  const { hasRole } = useAuth();
  const canEdit = hasRole(AdminRole.MANAGER);
  const { data: appointmentTypes } = useAppointmentTypes();

  const prefTypes = (appointmentTypes ?? []).filter((t) =>
    customer.preferred_appointment_type_ids?.includes(t.id)
  );

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>Contact Information</CardTitle>
        <div className="flex items-center gap-2">
          {customer.background_check_required && (
            <Badge variant="destructive">Background check required</Badge>
          )}
          {customer.consent_status && (
            <StatusBadge type="consent" value={customer.consent_status} />
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {customer.background_check_required && (
          <div className="rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-200">
            This volunteer is blocked from booking appointments until their
            background check is cleared. Toggle the flag off in Edit when ready.
          </div>
        )}
        <div>
          <Label className="text-muted-foreground">Phone</Label>
          <p className="font-medium">{formatPhone(customer.phone)}</p>
        </div>
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
        <div>
          <Label className="text-muted-foreground">Background check</Label>
          <p
            className={`font-medium ${customer.background_check_required ? "text-destructive" : ""}`}
          >
            {customer.background_check_required ? "Required" : "Not required"}
          </p>
        </div>
        {canEdit && onEditClick && (
          <Button size="sm" variant="outline" onClick={onEditClick}>
            <Pencil className="mr-1 h-3 w-3" />
            Edit
          </Button>
        )}
      </CardContent>
    </Card>
  );
}
