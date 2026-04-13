import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { TokenUsageByDay } from "../api";

interface Props {
  data: TokenUsageByDay[] | undefined;
  isLoading: boolean;
}

export function DailyUsageChart({ data, isLoading }: Props) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Daily Token Usage</CardTitle>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="h-64 flex items-center justify-center text-sm text-muted-foreground">
            Loading...
          </div>
        ) : !data || data.length === 0 ? (
          <div className="h-64 flex items-center justify-center text-sm text-muted-foreground">
            No usage data yet.
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={300}>
            <AreaChart data={data}>
              <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
              <XAxis dataKey="date" className="text-xs" tickFormatter={(v) => v.slice(5)} />
              <YAxis className="text-xs" tickFormatter={(v) => v >= 1000 ? `${(v / 1000).toFixed(0)}K` : v} />
              <Tooltip
                formatter={(value: number, name: string) => [
                  value.toLocaleString(),
                  name === "input_tokens" ? "Input" : name === "output_tokens" ? "Output" : name,
                ]}
                labelFormatter={(label) => `Date: ${label}`}
              />
              <Legend />
              <Area
                type="monotone"
                dataKey="input_tokens"
                stackId="1"
                stroke="hsl(var(--primary))"
                fill="hsl(var(--primary))"
                fillOpacity={0.6}
                name="Input"
              />
              <Area
                type="monotone"
                dataKey="output_tokens"
                stackId="1"
                stroke="hsl(var(--chart-2, 220 70% 50%))"
                fill="hsl(var(--chart-2, 220 70% 50%))"
                fillOpacity={0.4}
                name="Output"
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </CardContent>
    </Card>
  );
}
