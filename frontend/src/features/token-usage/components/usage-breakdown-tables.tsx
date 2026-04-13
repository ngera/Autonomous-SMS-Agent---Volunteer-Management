import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { TokenUsageBySource, TokenUsageByModel } from "../api";

function formatNumber(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return n.toString();
}

const SOURCE_LABELS: Record<string, string> = {
  conversation: "Conversations",
  screener: "Screener",
  test_tool: "Test Tool",
};

interface Props {
  bySource: TokenUsageBySource[] | undefined;
  byModel: TokenUsageByModel[] | undefined;
  isLoading: boolean;
}

export function UsageBreakdownTables({ bySource, byModel, isLoading }: Props) {
  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Usage by Source</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="h-32 flex items-center justify-center text-sm text-muted-foreground">
              Loading...
            </div>
          ) : !bySource || bySource.length === 0 ? (
            <p className="text-sm text-muted-foreground">No data yet.</p>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-muted-foreground">
                  <th className="pb-2 font-medium">Source</th>
                  <th className="pb-2 font-medium text-right">Input</th>
                  <th className="pb-2 font-medium text-right">Output</th>
                  <th className="pb-2 font-medium text-right">Total</th>
                  <th className="pb-2 font-medium text-right">Requests</th>
                </tr>
              </thead>
              <tbody>
                {bySource.map((row) => (
                  <tr key={row.source} className="border-b last:border-0">
                    <td className="py-2">{SOURCE_LABELS[row.source] ?? row.source}</td>
                    <td className="py-2 text-right">{formatNumber(row.input_tokens)}</td>
                    <td className="py-2 text-right">{formatNumber(row.output_tokens)}</td>
                    <td className="py-2 text-right font-medium">{formatNumber(row.total_tokens)}</td>
                    <td className="py-2 text-right">{row.request_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Usage by Model</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="h-32 flex items-center justify-center text-sm text-muted-foreground">
              Loading...
            </div>
          ) : !byModel || byModel.length === 0 ? (
            <p className="text-sm text-muted-foreground">No data yet.</p>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-muted-foreground">
                  <th className="pb-2 font-medium">Model</th>
                  <th className="pb-2 font-medium text-right">Input</th>
                  <th className="pb-2 font-medium text-right">Output</th>
                  <th className="pb-2 font-medium text-right">Total</th>
                  <th className="pb-2 font-medium text-right">Requests</th>
                </tr>
              </thead>
              <tbody>
                {byModel.map((row) => (
                  <tr key={row.model} className="border-b last:border-0">
                    <td className="py-2 font-mono text-xs">{row.model}</td>
                    <td className="py-2 text-right">{formatNumber(row.input_tokens)}</td>
                    <td className="py-2 text-right">{formatNumber(row.output_tokens)}</td>
                    <td className="py-2 text-right font-medium">{formatNumber(row.total_tokens)}</td>
                    <td className="py-2 text-right">{row.request_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
