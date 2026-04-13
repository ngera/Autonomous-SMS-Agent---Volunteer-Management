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

interface Props {
  data: TokenUsageDetail[] | undefined;
  isLoading: boolean;
}

export function RecentUsageTable({ data, isLoading }: Props) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Recent API Calls</CardTitle>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="h-32 flex items-center justify-center text-sm text-muted-foreground">
            Loading...
          </div>
        ) : !data || data.length === 0 ? (
          <p className="text-sm text-muted-foreground">No recent usage data.</p>
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
                {data.map((row) => (
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
  );
}
