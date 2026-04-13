import { useState } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { PageHeader } from "@/components/shared/page-header";
import { TokenSummaryCards } from "../components/token-summary-cards";
import { DailyUsageChart } from "../components/daily-usage-chart";
import { UsageBreakdownTables } from "../components/usage-breakdown-tables";
import { VolunteerUsageTable } from "../components/volunteer-usage-table";
import { ToolUsageTable } from "../components/tool-usage-table";
import { RecentUsageTable } from "../components/recent-usage-table";
import { useTokenUsageDashboard } from "../hooks/use-token-usage";

const PERIOD_OPTIONS = [
  { label: "7 days", value: 7 },
  { label: "30 days", value: 30 },
  { label: "90 days", value: 90 },
];

export function TokenUsagePage() {
  const [days, setDays] = useState(30);
  const { data, isLoading } = useTokenUsageDashboard(days);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <PageHeader
          title="Token Usage"
          description="Track and analyze AI token consumption and estimated costs."
        />
        <div className="flex gap-1 rounded-md border p-1">
          {PERIOD_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              onClick={() => setDays(opt.value)}
              className={`rounded px-3 py-1 text-xs font-medium transition-colors ${
                days === opt.value
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:bg-accent"
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      <TokenSummaryCards summary={data?.summary} isLoading={isLoading} />

      <Tabs defaultValue="overview">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="volunteers">By Volunteer</TabsTrigger>
          <TabsTrigger value="tools">By Tool</TabsTrigger>
          <TabsTrigger value="recent">Recent Calls</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-6 mt-4">
          <DailyUsageChart data={data?.daily} isLoading={isLoading} />
          <UsageBreakdownTables
            bySource={data?.by_source}
            byModel={data?.by_model}
            isLoading={isLoading}
          />
        </TabsContent>

        <TabsContent value="volunteers" className="mt-4">
          <VolunteerUsageTable data={data?.by_volunteer} isLoading={isLoading} />
        </TabsContent>

        <TabsContent value="tools" className="mt-4">
          <ToolUsageTable data={data?.by_tool} isLoading={isLoading} />
        </TabsContent>

        <TabsContent value="recent" className="mt-4">
          <RecentUsageTable data={data?.recent} isLoading={isLoading} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
