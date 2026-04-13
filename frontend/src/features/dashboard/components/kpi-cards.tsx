import {
  Calendar,
  TrendingUp,
  UserCheck,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import type { DashboardSummary } from "@/types/api";

interface KpiCardsProps {
  data?: DashboardSummary;
  isLoading: boolean;
}

export function KpiCards({ data, isLoading }: KpiCardsProps) {
  const cards = [
    {
      title: "Monthly Bookings",
      value: data?.monthly_bookings ?? 0,
      format: (v: number) => v.toString(),
      icon: Calendar,
    },
    {
      title: "Opt-in Rate",
      value: data?.opt_in_rate ?? 0,
      format: (v: number) => `${v.toFixed(1)}%`,
      icon: UserCheck,
    },
    {
      title: "Reminder Conversion",
      value: data?.reminder_conversion_rate ?? 0,
      format: (v: number) => `${v.toFixed(1)}%`,
      icon: TrendingUp,
    },
  ];

  return (
    <div className="grid gap-4 sm:grid-cols-3">
      {cards.map((card) => (
        <Card key={card.title}>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              {card.title}
            </CardTitle>
            <card.icon className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <Skeleton className="h-8 w-24" />
            ) : (
              <p className="text-2xl font-bold">{card.format(card.value)}</p>
            )}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
