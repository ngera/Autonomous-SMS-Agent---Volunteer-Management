import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useCustomerVolunteerStats } from "../hooks/use-customers";

function formatHours(minutes: number): string {
  if (minutes <= 0) return "0h";
  const hours = Math.floor(minutes / 60);
  const mins = minutes % 60;
  if (hours === 0) return `${mins}m`;
  if (mins === 0) return `${hours}h`;
  return `${hours}h ${mins}m`;
}

interface VolunteerHoursTabProps {
  phone: string;
}

export function VolunteerHoursTab({ phone }: VolunteerHoursTabProps) {
  const { data, isLoading } = useCustomerVolunteerStats(phone);

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Time volunteered</CardTitle>
        </CardHeader>
        <CardContent>
          <Skeleton className="h-24 w-full" />
        </CardContent>
      </Card>
    );
  }

  const totalHours = data ? formatHours(data.total_minutes) : "0h";
  const totalBookings = data?.total_completed_bookings ?? 0;
  const rows = data?.by_service ?? [];

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Time volunteered</CardTitle>
        <p className="text-xs text-muted-foreground">
          Based on completed bookings × the service's configured duration.
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <div className="rounded-lg border p-3">
            <p className="text-xs text-muted-foreground">Total time</p>
            <p className="text-2xl font-semibold">{totalHours}</p>
          </div>
          <div className="rounded-lg border p-3">
            <p className="text-xs text-muted-foreground">Completed bookings</p>
            <p className="text-2xl font-semibold">{totalBookings}</p>
          </div>
        </div>

        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Service</TableHead>
                <TableHead>Category</TableHead>
                <TableHead className="text-right">Bookings</TableHead>
                <TableHead className="text-right">Time</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.length === 0 ? (
                <TableRow>
                  <TableCell
                    colSpan={4}
                    className="h-24 text-center text-muted-foreground"
                  >
                    No completed bookings yet.
                  </TableCell>
                </TableRow>
              ) : (
                rows.map((r) => (
                  <TableRow key={r.appointment_type_id}>
                    <TableCell className="font-medium">{r.name}</TableCell>
                    <TableCell>
                      {r.category ?? (
                        <span className="text-muted-foreground">—</span>
                      )}
                    </TableCell>
                    <TableCell className="text-right">
                      {r.completed_bookings}
                    </TableCell>
                    <TableCell className="text-right">
                      {formatHours(r.total_minutes)}
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </div>
      </CardContent>
    </Card>
  );
}
