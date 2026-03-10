import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useRetentionMetrics, useReminderAnalytics } from "../hooks/use-analytics";

export function RetentionCards() {
  const retention = useRetentionMetrics();
  const reminders = useReminderAnalytics();

  const cards = [
    {
      label: "Recurring Customer Rate",
      value: retention.data ? `${retention.data.recurring_customer_rate}%` : "—",
    },
    {
      label: "Recurring Customers",
      value: retention.data?.total_recurring_customers ?? "—",
    },
    {
      label: "Reminder Conversion",
      value: reminders.data ? `${reminders.data.conversion_rate}%` : "—",
    },
    {
      label: "Reminders Sent",
      value: reminders.data?.total_sent ?? "—",
    },
  ];

  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      {cards.map((c) => (
        <Card key={c.label}>
          <CardHeader className="pb-1">
            <CardTitle className="text-xs text-muted-foreground">
              {c.label}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">{c.value}</p>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
