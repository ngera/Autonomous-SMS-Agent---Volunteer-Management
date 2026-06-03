import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { TokenUsageByTool } from "../api";

const TOOL_LABELS: Record<string, string> = {
  check_availability: "Check Availability",
  book_appointment: "Book Appointment",
  cancel_appointment: "Cancel Appointment",
  reschedule_appointment: "Reschedule",
  lookup_customer: "Lookup Customer",
  list_appointments: "List Appointments",
  get_business_info: "Business Info",
  send_announcement: "Send Announcement",
  list_customers: "List Customers",
  manage_suspension: "Manage Suspension",
  screener: "Screener (Pre-filter)",
};

interface Props {
  data: TokenUsageByTool[] | undefined;
  isLoading: boolean;
}

export function ToolUsageTable({ data, isLoading }: Props) {
  const chartData = (data || []).map((t) => ({
    ...t,
    label: TOOL_LABELS[t.tool_name] ?? t.tool_name.replace(/_/g, " "),
  }));

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">AI Tool Calls</CardTitle>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="h-64 flex items-center justify-center text-sm text-muted-foreground">
            Loading...
          </div>
        ) : !chartData.length ? (
          <p className="text-sm text-muted-foreground">No tool usage data yet.</p>
        ) : (
          <ResponsiveContainer width="100%" height={Math.max(200, chartData.length * 36)}>
            <BarChart data={chartData} layout="vertical" margin={{ left: 120 }}>
              <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
              <XAxis type="number" className="text-xs" allowDecimals={false} />
              <YAxis
                type="category"
                dataKey="label"
                className="text-xs"
                width={110}
                tick={{ fontSize: 12 }}
              />
              <Tooltip
                formatter={(value, name) => [
                  Number(value),
                  name === "call_count" ? "Calls" : "Requests",
                ]}
                contentStyle={{
                  backgroundColor: "var(--popover)",
                  border: "1px solid var(--border)",
                  borderRadius: 6,
                  color: "var(--popover-foreground)",
                }}
                labelStyle={{ color: "var(--popover-foreground)" }}
                itemStyle={{ color: "var(--popover-foreground)" }}
                cursor={{ fill: "var(--muted)", fillOpacity: 0.3 }}
              />
              <Bar
                dataKey="call_count"
                fill="var(--chart-1)"
                fillOpacity={0.85}
                radius={[0, 4, 4, 0]}
                name="Calls"
              />
            </BarChart>
          </ResponsiveContainer>
        )}
      </CardContent>
    </Card>
  );
}
