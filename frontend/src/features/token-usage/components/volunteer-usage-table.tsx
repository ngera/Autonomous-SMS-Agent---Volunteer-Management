import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { TokenUsageByVolunteer } from "../api";

function formatNumber(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return n.toString();
}

interface Props {
  data: TokenUsageByVolunteer[] | undefined;
  isLoading: boolean;
}

export function VolunteerUsageTable({ data, isLoading }: Props) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Usage by Volunteer</CardTitle>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="h-32 flex items-center justify-center text-sm text-muted-foreground">
            Loading...
          </div>
        ) : !data || data.length === 0 ? (
          <p className="text-sm text-muted-foreground">No volunteer usage data yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-muted-foreground">
                  <th className="pb-2 font-medium">Volunteer</th>
                  <th className="pb-2 font-medium">Phone</th>
                  <th className="pb-2 font-medium text-right">Input</th>
                  <th className="pb-2 font-medium text-right">Output</th>
                  <th className="pb-2 font-medium text-right">Total</th>
                  <th className="pb-2 font-medium text-right">Requests</th>
                  <th className="pb-2 font-medium text-right">Est. Cost</th>
                </tr>
              </thead>
              <tbody>
                {data.map((row) => (
                  <tr key={row.contact_id ?? row.contact_phone} className="border-b last:border-0">
                    <td className="py-2">{row.contact_name || "Unknown"}</td>
                    <td className="py-2 font-mono text-xs text-muted-foreground">
                      {row.contact_phone || "-"}
                    </td>
                    <td className="py-2 text-right">{formatNumber(row.input_tokens)}</td>
                    <td className="py-2 text-right">{formatNumber(row.output_tokens)}</td>
                    <td className="py-2 text-right font-medium">{formatNumber(row.total_tokens)}</td>
                    <td className="py-2 text-right">{row.request_count}</td>
                    <td className="py-2 text-right">${row.estimated_cost_usd.toFixed(4)}</td>
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
