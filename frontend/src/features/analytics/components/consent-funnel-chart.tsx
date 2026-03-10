import {
  PieChart,
  Pie,
  Cell,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useConsentFunnel } from "../hooks/use-analytics";

const COLORS = ["#94a3b8", "#f59e0b", "#22c55e", "#ef4444"];

export function ConsentFunnelChart() {
  const { data, isLoading } = useConsentFunnel();

  const chartData = data
    ? [
        { name: "Uncontacted", value: data.uncontacted },
        { name: "Pending", value: data.pending },
        { name: "Opted In", value: data.opted_in },
        { name: "Opted Out", value: data.opted_out },
      ].filter((d) => d.value > 0)
    : [];

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Consent Funnel</CardTitle>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="h-64 flex items-center justify-center text-sm text-muted-foreground">
            Loading...
          </div>
        ) : chartData.length === 0 ? (
          <div className="h-64 flex items-center justify-center text-sm text-muted-foreground">
            No consent data yet.
          </div>
        ) : (
          <div className="space-y-2">
            <ResponsiveContainer width="100%" height={240}>
              <PieChart>
                <Pie
                  data={chartData}
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={90}
                  dataKey="value"
                  label={(props) =>
                    `${props.name ?? ""} ${(((props.percent as number) ?? 0) * 100).toFixed(0)}%`
                  }
                >
                  {chartData.map((_, i) => (
                    <Cell key={i} fill={COLORS[i % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
            {data && (
              <p className="text-center text-sm text-muted-foreground">
                Opt-in rate: <span className="font-medium">{data.opt_in_rate}%</span>{" "}
                of {data.total_contacts} contacts
              </p>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
