import { useNavigate } from "react-router-dom";
import { AlertTriangle, ShieldAlert, Users } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import type { DashboardSummary } from "@/types/api";

interface PendingAlertsProps {
  data?: DashboardSummary;
  isLoading: boolean;
}

export function PendingAlerts({ data, isLoading }: PendingAlertsProps) {
  const navigate = useNavigate();

  const alerts = [
    {
      label: "Total Volunteers",
      count: data?.total_volunteers ?? 0,
      icon: Users,
      to: "/customers",
      urgent: false,
    },
    {
      label: "Slots Needing Volunteers",
      count: data?.slots_needing_bookings ?? 0,
      icon: AlertTriangle,
      to: "/availability",
      urgent: true,
    },
    {
      label: "Unreviewed Suspensions",
      count: data?.unreviewed_suspensions_count ?? 0,
      icon: ShieldAlert,
      to: "/suspensions",
      urgent: true,
    },
  ];

  return (
    <div className="grid gap-4 sm:grid-cols-3">
      {alerts.map((alert) => (
        <Card
          key={alert.label}
          className={cn(
            "cursor-pointer transition-colors hover:bg-muted/50",
            alert.urgent && alert.count > 0 && "border-destructive"
          )}
          onClick={() => navigate(alert.to)}
        >
          <CardContent className="flex items-center gap-3 pt-6">
            <alert.icon
              className={cn(
                "h-5 w-5",
                alert.urgent && alert.count > 0
                  ? "text-destructive"
                  : "text-muted-foreground"
              )}
            />
            <div>
              {isLoading ? (
                <Skeleton className="h-6 w-8" />
              ) : (
                <p
                  className={cn(
                    "text-xl font-bold",
                    alert.urgent && alert.count > 0 && "text-destructive"
                  )}
                >
                  {alert.count}
                </p>
              )}
              <p className="text-xs text-muted-foreground">{alert.label}</p>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
