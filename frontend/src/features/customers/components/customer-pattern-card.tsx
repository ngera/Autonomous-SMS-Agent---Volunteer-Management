import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { StatusBadge } from "@/components/shared/status-badge";
import { formatDate } from "@/lib/utils";
import { useAuth } from "@/hooks/use-auth";
import { AdminRole } from "@/types/enums";
import type { PatternResponse } from "@/types/api";
import {
  useSetPatternOverride,
  useClearPatternOverride,
} from "../hooks/use-customers";

interface CustomerPatternCardProps {
  patterns: PatternResponse[];
  phone: string;
  isLoading: boolean;
}

export function CustomerPatternCard({
  patterns,
  phone,
  isLoading,
}: CustomerPatternCardProps) {
  const { hasRole } = useAuth();
  const canEdit = hasRole(AdminRole.MANAGER);
  const setOverride = useSetPatternOverride();
  const clearOverride = useClearPatternOverride();

  const [overrideDays, setOverrideDays] = useState("");

  if (isLoading) return <p className="text-sm text-muted-foreground">Loading patterns...</p>;
  if (patterns.length === 0) return <p className="text-sm text-muted-foreground">No patterns recorded yet.</p>;

  return (
    <div className="space-y-4">
      {patterns.map((p) => (
        <Card key={p.id}>
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardTitle className="text-base">Pattern</CardTitle>
              <StatusBadge type="confidence" value={p.confidence} />
            </div>
          </CardHeader>
          <CardContent className="grid gap-3 sm:grid-cols-2 text-sm">
            <div>
              <span className="text-muted-foreground">Completed Bookings:</span>{" "}
              <span className="font-medium">{p.completed_booking_count}</span>
            </div>
            <div>
              <span className="text-muted-foreground">Calculated Interval:</span>{" "}
              <span className="font-medium">
                {p.calculated_interval_days != null ? `${p.calculated_interval_days} days` : "—"}
              </span>
            </div>
            <div>
              <span className="text-muted-foreground">Blended Interval:</span>{" "}
              <span className="font-medium">
                {p.blended_interval_days != null ? `${p.blended_interval_days} days` : "—"}
              </span>
            </div>
            <div>
              <span className="text-muted-foreground">Admin Default:</span>{" "}
              <span className="font-medium">
                {p.admin_default_days != null ? `${p.admin_default_days} days` : "—"}
              </span>
            </div>
            <div>
              <span className="text-muted-foreground">Next Due:</span>{" "}
              <span className="font-medium">
                {p.next_due_date ? formatDate(p.next_due_date) : "—"}
              </span>
            </div>
            <div>
              <span className="text-muted-foreground">Manual Override:</span>{" "}
              <span className="font-medium">
                {p.manual_override_days != null ? `${p.manual_override_days} days` : "None"}
              </span>
            </div>
            {p.outliers_removed > 0 && (
              <div>
                <span className="text-muted-foreground">Outliers Removed:</span>{" "}
                <span className="font-medium">{p.outliers_removed}</span>
              </div>
            )}

            {canEdit && (
              <div className="sm:col-span-2 flex items-end gap-2 pt-2 border-t">
                <div className="space-y-1">
                  <Label className="text-xs">Override (days)</Label>
                  <Input
                    type="number"
                    value={overrideDays}
                    onChange={(e) => setOverrideDays(e.target.value)}
                    className="w-24 h-8"
                    min={1}
                    placeholder="e.g. 28"
                  />
                </div>
                <Button
                  size="sm"
                  onClick={() => {
                    if (overrideDays) {
                      setOverride.mutate({
                        phone,
                        body: { manual_override_days: Number(overrideDays) },
                      });
                    }
                  }}
                  disabled={!overrideDays || setOverride.isPending}
                >
                  Set
                </Button>
                {p.manual_override_days != null && (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => clearOverride.mutate(phone)}
                    disabled={clearOverride.isPending}
                  >
                    Clear
                  </Button>
                )}
              </div>
            )}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
