import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useReminderAnalytics } from "../hooks/use-reminders";

export function ReminderAnalyticsCards() {
  const { data, isLoading } = useReminderAnalytics();

  if (isLoading || !data) return null;

  const cards = [
    { label: "Total Sent", value: data.total_sent },
    { label: "Converted", value: data.total_converted },
    { label: "Conversion Rate", value: `${data.conversion_rate}%` },
    { label: "Personal Rate", value: `${data.personal_conversion_rate}%` },
  ];

  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      {cards.map((c) => (
        <Card key={c.label}>
          <CardHeader className="pb-1">
            <CardTitle className="text-xs text-muted-foreground">{c.label}</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">{c.value}</p>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
