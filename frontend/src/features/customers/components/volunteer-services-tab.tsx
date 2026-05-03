import { useState, useEffect, useMemo } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Check, AlertTriangle } from "lucide-react";
import { listAppointmentTypes } from "@/features/appointment-types/api";
import { updateCustomer } from "../api";
import type { CustomerResponse } from "@/types/api";

interface VolunteerServicesTabProps {
  customer: CustomerResponse;
  canEdit: boolean;
  onUpdated: () => void;
}

export function VolunteerServicesTab({ customer, canEdit, onUpdated }: VolunteerServicesTabProps) {
  const qc = useQueryClient();
  const { data: appointmentTypes, isLoading } = useQuery({
    queryKey: ["appointment-types-volunteer-tab"],
    queryFn: listAppointmentTypes,
  });

  const activeTypes = useMemo(
    () => (appointmentTypes ?? []).filter((t) => t.is_active),
    [appointmentTypes]
  );

  const [selectedIds, setSelectedIds] = useState<string[]>(customer.preferred_appointment_type_ids ?? []);
  const [allServicesEnabled, setAllServicesEnabled] = useState(customer.all_services_enabled ?? false);
  const [dirty, setDirty] = useState(false);

  useEffect(() => {
    setSelectedIds(customer.preferred_appointment_type_ids ?? []);
    setAllServicesEnabled(customer.all_services_enabled ?? false);
    setDirty(false);
  }, [customer]);

  function toggle(id: string) {
    setSelectedIds((prev) => {
      const next = prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id];
      return next;
    });
    setDirty(true);
  }

  function handleAllServicesToggle(checked: boolean) {
    setAllServicesEnabled(checked);
    setDirty(true);
  }

  const saveMutation = useMutation({
    mutationFn: () =>
      updateCustomer(customer.phone, {
        all_services_enabled: allServicesEnabled,
        preferred_appointment_type_ids: selectedIds,
      }),
    onSuccess: () => {
      setDirty(false);
      onUpdated();
      void qc.invalidateQueries({ queryKey: ["customers"] });
    },
  });

  const hasNoAccess = !allServicesEnabled && selectedIds.length === 0;

  if (isLoading) {
    return <p className="text-sm text-muted-foreground p-4">Loading services...</p>;
  }

  if (activeTypes.length === 0) {
    return <p className="text-sm text-muted-foreground p-4">No appointment types configured.</p>;
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle className="text-base">Services this volunteer participates in</CardTitle>
        {canEdit && dirty && (
          <Button size="sm" onClick={() => saveMutation.mutate()} disabled={saveMutation.isPending}>
            {saveMutation.isPending ? "Saving..." : "Save"}
          </Button>
        )}
      </CardHeader>
      <CardContent className="space-y-4">
        {/* All Services Toggle */}
        <div className="flex items-center justify-between rounded-lg border p-3">
          <div>
            <Label className="text-sm font-medium">All Services</Label>
            <p className="text-xs text-muted-foreground">
              Allow this volunteer to book any active service
            </p>
          </div>
          <Switch
            checked={allServicesEnabled}
            onCheckedChange={handleAllServicesToggle}
            disabled={!canEdit}
          />
        </div>

        {/* Warning when no access */}
        {hasNoAccess && (
          <div className="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 p-3 dark:border-amber-900 dark:bg-amber-950">
            <AlertTriangle className="h-4 w-4 text-amber-600 mt-0.5 shrink-0" />
            <p className="text-sm text-amber-800 dark:text-amber-200">
              This volunteer cannot book any services. Enable "All Services" above or assign specific services below.
            </p>
          </div>
        )}

        {/* Individual services (disabled when all services is on) */}
        <div>
          <p className="text-xs text-muted-foreground mb-2">
            {allServicesEnabled
              ? "Individual assignments are ignored when All Services is enabled."
              : "Select specific services this volunteer can book:"}
          </p>
          <div className={`grid gap-2 sm:grid-cols-2 ${allServicesEnabled ? "opacity-50 pointer-events-none" : ""}`}>
            {activeTypes.map((type) => {
              const selected = selectedIds.includes(type.id);
              return (
                <div
                  key={type.id}
                  className={`flex items-center justify-between rounded-lg border p-3 transition-colors ${
                    selected ? "border-primary bg-primary/5" : "border-muted"
                  } ${canEdit && !allServicesEnabled ? "cursor-pointer hover:bg-muted/50" : ""}`}
                  onClick={() => canEdit && !allServicesEnabled && toggle(type.id)}
                >
                  <div>
                    <p className="text-sm font-medium">{type.name}</p>
                    <p className="text-xs text-muted-foreground">
                      {type.duration_minutes} min
                      {type.price > 0 ? ` · $${type.price}` : ""}
                    </p>
                  </div>
                  {selected ? (
                    <Badge variant="default" className="gap-1">
                      <Check className="h-3 w-3" /> Active
                    </Badge>
                  ) : (
                    <Badge variant="outline" className="text-muted-foreground">
                      Not assigned
                    </Badge>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
