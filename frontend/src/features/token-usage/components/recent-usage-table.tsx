import { useState, useMemo } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { TokenUsageDetail } from "../api";
import { format } from "date-fns";

function formatNumber(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return n.toString();
}

const SOURCE_LABELS: Record<string, string> = {
  conversation: "Conversation",
  screener: "Screener",
  test_tool: "Test Tool",
};

const SOURCE_OPTIONS = [
  { value: "all", label: "All Sources" },
  { value: "conversation", label: "Conversation" },
  { value: "screener", label: "Screener" },
  { value: "test_tool", label: "Test Tool" },
];

interface Props {
  data: TokenUsageDetail[] | undefined;
  isLoading: boolean;
}

export function RecentUsageTable({ data, isLoading }: Props) {
  const [sourceFilter, setSourceFilter] = useState("all");
  const [volunteerFilter, setVolunteerFilter] = useState("");

  // Unique volunteers for filter dropdown
  const volunteers = useMemo(() => {
    if (!data) return [];
    const seen = new Map<string, string>();
    for (const row of data) {
      const key = row.contact_phone || row.contact_name || "";
      if (key && !seen.has(key)) {
        seen.set(key, row.contact_name || row.contact_phone || "");
      }
    }
    return Array.from(seen.entries()).map(([key, label]) => ({ value: key, label }));
  }, [data]);

  // Filtered data
  const filtered = useMemo(() => {
    if (!data) return [];
    return data.filter((row) => {
      if (sourceFilter !== "all" && row.source !== sourceFilter) return false;
      if (volunteerFilter && (row.contact_phone || row.contact_name || "") !== volunteerFilter) return false;
      return true;
    });
  }, [data, sourceFilter, volunteerFilter]);

  // Aggregate filtered data by hour for the chart
  const chartData = useMemo(() => {
    const buckets = new Map<string, { hour: string; input_tokens: number; output_tokens: number; requests: number }>();
    for (const row of filtered) {
      const hour = format(new Date(row.created_at), "MMM d, ha");
      const existing = buckets.get(hour);
      if (existing) {
        existing.input_tokens += row.input_tokens;
        existing.output_tokens += row.output_tokens;
        existing.requests += 1;
      } else {
        buckets.set(hour, {
          hour,
          input_tokens: row.input_tokens,
          output_tokens: row.output_tokens,
          requests: 1,
        });
      }
    }
    return Array.from(buckets.values());
  }, [filtered]);

  return (
    <div className="space-y-4">
      {/* Filters */}
      <Card>
        <CardContent className="py-3">
          <div className="flex items-center gap-4 flex-wrap">
            <div className="flex items-center gap-2">
              <label className="text-sm font-medium whitespace-nowrap">Source</label>
              <select
                value={sourceFilter}
                onChange={(e) => setSourceFilter(e.target.value)}
                className="h-8 rounded-md border border-input bg-background px-2 text-sm"
              >
                {SOURCE_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>{opt.label}</option>
                ))}
              </select>
            </div>
            <div className="flex items-center gap-2">
              <label className="text-sm font-medium whitespace-nowrap">Volunteer</label>
              <select
                value={volunteerFilter}
                onChange={(e) => setVolunteerFilter(e.target.value)}
                className="h-8 rounded-md border border-input bg-background px-2 text-sm"
              >
                <option value="">All Volunteers</option>
                {volunteers.map((v) => (
                  <option key={v.value} value={v.value}>{v.label}</option>
                ))}
              </select>
            </div>
            <div className="text-xs text-muted-foreground ml-auto">
              {filtered.length} of {data?.length ?? 0} calls
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Chart */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Token Usage Over Time</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="h-48 flex items-center justify-center text-sm text-muted-foreground">
              Loading...
            </div>
          ) : chartData.length === 0 ? (
            <div className="h-48 flex items-center justify-center text-sm text-muted-foreground">
              No data matching filters.
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
                <XAxis dataKey="hour" className="text-xs" tick={{ fontSize: 11 }} />
                <YAxis
                  className="text-xs"
                  tickFormatter={(v) => (v >= 1000 ? `${(v / 1000).toFixed(0)}K` : v)}
                />
                <Tooltip
                  formatter={(value, name) => [
                    Number(value).toLocaleString(),
                    name === "input_tokens" ? "Input Tokens" : "Output Tokens",
                  ]}
                />
                <Legend />
                <Bar
                  dataKey="input_tokens"
                  stackId="1"
                  fill="hsl(var(--primary))"
                  name="Input Tokens"
                  radius={[0, 0, 0, 0]}
                />
                <Bar
                  dataKey="output_tokens"
                  stackId="1"
                  fill="hsl(var(--chart-2, 220 70% 50%))"
                  name="Output Tokens"
                  radius={[4, 4, 0, 0]}
                />
              </BarChart>
            </ResponsiveContainer>
          )}
        </CardContent>
      </Card>

      {/* Table */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Call Details</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="h-32 flex items-center justify-center text-sm text-muted-foreground">
              Loading...
            </div>
          ) : filtered.length === 0 ? (
            <p className="text-sm text-muted-foreground">No data matching filters.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-muted-foreground">
                    <th className="pb-2 font-medium">Time</th>
                    <th className="pb-2 font-medium">Source</th>
                    <th className="pb-2 font-medium">Volunteer</th>
                    <th className="pb-2 font-medium text-right">Input</th>
                    <th className="pb-2 font-medium text-right">Output</th>
                    <th className="pb-2 font-medium">Tools Used</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((row) => (
                    <tr key={row.id} className="border-b last:border-0">
                      <td className="py-2 text-xs text-muted-foreground whitespace-nowrap">
                        {format(new Date(row.created_at), "MMM d, h:mm a")}
                      </td>
                      <td className="py-2">
                        <span className="inline-flex items-center rounded-full bg-accent px-2 py-0.5 text-xs">
                          {SOURCE_LABELS[row.source] ?? row.source}
                        </span>
                      </td>
                      <td className="py-2 text-xs">
                        {row.contact_name || row.contact_phone || "-"}
                      </td>
                      <td className="py-2 text-right">{formatNumber(row.input_tokens)}</td>
                      <td className="py-2 text-right">{formatNumber(row.output_tokens)}</td>
                      <td className="py-2">
                        {row.tool_names.length > 0 ? (
                          <div className="flex flex-wrap gap-1">
                            {row.tool_names.map((t, i) => (
                              <span
                                key={i}
                                className="inline-flex items-center rounded bg-muted px-1.5 py-0.5 text-xs font-mono"
                              >
                                {t}
                              </span>
                            ))}
                          </div>
                        ) : (
                          <span className="text-xs text-muted-foreground">-</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
