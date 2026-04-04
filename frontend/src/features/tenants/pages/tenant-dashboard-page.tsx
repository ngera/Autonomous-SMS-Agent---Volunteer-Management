import { useNavigate } from "react-router-dom";
import {
  Building2,
  Users,
  Calendar,
  MessageSquare,
  Bell,
  DollarSign,
  Play,
  Pause,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { PageHeader } from "@/components/shared/page-header";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useSuperAdminDashboard } from "../hooks/use-tenants";
import { useTenantFilter } from "@/context/tenant-filter-context";
import { formatCurrency } from "@/lib/utils";

function KpiCard({
  title,
  value,
  icon: Icon,
  isLoading,
}: {
  title: string;
  value: string | number;
  icon: React.ElementType;
  isLoading: boolean;
}) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">
          {title}
        </CardTitle>
        <Icon className="h-4 w-4 text-muted-foreground" />
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <Skeleton className="h-8 w-24" />
        ) : (
          <p className="text-2xl font-bold">{value}</p>
        )}
      </CardContent>
    </Card>
  );
}

export function TenantDashboardPage() {
  const navigate = useNavigate();
  const { selectedTenantIds } = useTenantFilter();
  const { data, isLoading } = useSuperAdminDashboard(
    selectedTenantIds.length > 0 ? selectedTenantIds : undefined
  );

  return (
    <div className="space-y-6">
      <PageHeader
        title="Tenant Dashboard"
        description="Cross-tenant overview of activity and performance this month."
      />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <KpiCard
          title="Total Tenants"
          value={data?.total_tenants ?? 0}
          icon={Building2}
          isLoading={isLoading}
        />
        <KpiCard
          title="Active Tenants"
          value={data?.active_tenants ?? 0}
          icon={Play}
          isLoading={isLoading}
        />
        <KpiCard
          title="Total Customers"
          value={data?.total_customers ?? 0}
          icon={Users}
          isLoading={isLoading}
        />
        <KpiCard
          title="Monthly Revenue"
          value={formatCurrency(data?.total_revenue ?? 0)}
          icon={DollarSign}
          isLoading={isLoading}
        />
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <KpiCard
          title="Bookings (This Month)"
          value={data?.total_bookings ?? 0}
          icon={Calendar}
          isLoading={isLoading}
        />
        <KpiCard
          title="Conversations (This Month)"
          value={data?.total_conversations ?? 0}
          icon={MessageSquare}
          isLoading={isLoading}
        />
        <KpiCard
          title="Reminders (This Month)"
          value={data?.total_reminders ?? 0}
          icon={Bell}
          isLoading={isLoading}
        />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Per-Tenant Breakdown</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Tenant</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Customers</TableHead>
                <TableHead className="text-right">Bookings</TableHead>
                <TableHead className="text-right">Conversations</TableHead>
                <TableHead className="text-right">Reminders</TableHead>
                <TableHead className="text-right">Revenue</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {isLoading ? (
                <TableRow>
                  <TableCell
                    colSpan={7}
                    className="text-center py-8 text-muted-foreground"
                  >
                    Loading...
                  </TableCell>
                </TableRow>
              ) : !data?.tenants.length ? (
                <TableRow>
                  <TableCell
                    colSpan={7}
                    className="text-center py-8 text-muted-foreground"
                  >
                    No tenants found
                  </TableCell>
                </TableRow>
              ) : (
                data.tenants.map((t) => (
                  <TableRow
                    key={t.id}
                    className="cursor-pointer"
                    onClick={() => navigate(`/tenants/${t.id}`)}
                  >
                    <TableCell className="font-medium">{t.name}</TableCell>
                    <TableCell>
                      {!t.is_active ? (
                        <Badge variant="destructive">Deactivated</Badge>
                      ) : t.is_paused ? (
                        <Badge
                          variant="secondary"
                          className="bg-yellow-100 text-yellow-800"
                        >
                          <Pause className="mr-1 h-3 w-3" />
                          Paused
                        </Badge>
                      ) : (
                        <Badge variant="default">Active</Badge>
                      )}
                    </TableCell>
                    <TableCell className="text-right">{t.customers}</TableCell>
                    <TableCell className="text-right">{t.bookings}</TableCell>
                    <TableCell className="text-right">
                      {t.conversations}
                    </TableCell>
                    <TableCell className="text-right">{t.reminders}</TableCell>
                    <TableCell className="text-right">
                      {formatCurrency(t.revenue)}
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
