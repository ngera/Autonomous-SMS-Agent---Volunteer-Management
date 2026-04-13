import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { TokenUsageSummary } from "../api";

function formatNumber(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return n.toString();
}

interface Props {
  summary: TokenUsageSummary | undefined;
  isLoading: boolean;
}

export function TokenSummaryCards({ summary, isLoading }: Props) {
  const cards = [
    { label: "Total Tokens", value: summary ? formatNumber(summary.total_tokens) : "-" },
    { label: "Input Tokens", value: summary ? formatNumber(summary.total_input_tokens) : "-" },
    { label: "Output Tokens", value: summary ? formatNumber(summary.total_output_tokens) : "-" },
    { label: "API Requests", value: summary ? formatNumber(summary.total_requests) : "-" },
    { label: "Est. Cost", value: summary ? `$${summary.estimated_cost_usd.toFixed(4)}` : "-" },
  ];

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
      {cards.map((card) => (
        <Card key={card.label}>
          <CardHeader className="pb-2">
            <CardTitle className="text-xs font-medium text-muted-foreground">
              {card.label}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="h-6 w-16 animate-pulse rounded bg-muted" />
            ) : (
              <p className="text-2xl font-bold">{card.value}</p>
            )}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
