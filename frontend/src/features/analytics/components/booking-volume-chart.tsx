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
import { useBookingAnalytics } from "../hooks/use-analytics";

export function BookingVolumeChart() {
  const { data, isLoading } = useBookingAnalytics();

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Booking Volume</CardTitle>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="h-64 flex items-center justify-center text-sm text-muted-foreground">
            Loading...
          </div>
        ) : !data || data.length === 0 ? (
          <div className="h-64 flex items-center justify-center text-sm text-muted-foreground">
            No booking data yet.
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={data}>
              <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
              <XAxis dataKey="period" className="text-xs" />
              <YAxis className="text-xs" allowDecimals={false} />
              <Tooltip />
              <Bar dataKey="count" fill="var(--primary)" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        )}
      </CardContent>
    </Card>
  );
}
