import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { ArrowLeft, RefreshCw, XCircle, CheckCircle } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/shared/page-header";
import { StatusBadge } from "@/components/shared/status-badge";
import { LoadingState } from "@/components/shared/loading-state";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import {
  formatDateTime,
  formatPhone,
  formatCurrency,
} from "@/lib/utils";
import { useAuth } from "@/hooks/use-auth";
import { AdminRole, BookingStatus } from "@/types/enums";
import {
  useBooking,
  useBookingHistory,
  useRescheduleBooking,
  useUpdateBookingStatus,
  useCancelBooking,
} from "../hooks/use-bookings";
import { BookingHistoryTimeline } from "../components/booking-history-timeline";
import { RescheduleDialog } from "../components/reschedule-dialog";
import { StatusUpdateDialog } from "../components/status-update-dialog";

export function BookingDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { hasRole } = useAuth();
  const booking = useBooking(id!);
  const history = useBookingHistory(id!);
  const reschedule = useRescheduleBooking();
  const statusUpdate = useUpdateBookingStatus();
  const cancel = useCancelBooking();

  const [showReschedule, setShowReschedule] = useState(false);
  const [showStatusUpdate, setShowStatusUpdate] = useState(false);
  const [showCancel, setShowCancel] = useState(false);

  if (booking.isLoading) return <LoadingState />;
  if (!booking.data) return <p>Booking not found.</p>;

  const b = booking.data;
  const isActive = b.status === BookingStatus.SCHEDULED || b.status === BookingStatus.RESCHEDULED;
  const canModify = hasRole(AdminRole.MANAGER);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Booking Detail"
        actions={
          <Button variant="ghost" onClick={() => navigate("/bookings")}>
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back
          </Button>
        }
      />

      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>Booking Information</CardTitle>
          <StatusBadge type="booking" value={b.status} />
        </CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-2">
          <div>
            <p className="text-sm text-muted-foreground">Customer</p>
            <p className="font-medium">{formatPhone(b.contact_phone)}</p>
          </div>
          <div>
            <p className="text-sm text-muted-foreground">Scheduled</p>
            <p className="font-medium">{formatDateTime(b.scheduled_at)}</p>
          </div>
          <div>
            <p className="text-sm text-muted-foreground">Price</p>
            <p className="font-medium">{formatCurrency(b.price_at_booking)}</p>
          </div>
          <div>
            <p className="text-sm text-muted-foreground">Created</p>
            <p className="font-medium">{formatDateTime(b.created_at)}</p>
          </div>
          {b.completed_at && (
            <div>
              <p className="text-sm text-muted-foreground">Completed</p>
              <p className="font-medium">{formatDateTime(b.completed_at)}</p>
            </div>
          )}
        </CardContent>
      </Card>

      {canModify && isActive && (
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => setShowReschedule(true)}>
            <RefreshCw className="mr-2 h-4 w-4" />
            Reschedule
          </Button>
          <Button variant="outline" onClick={() => setShowStatusUpdate(true)}>
            <CheckCircle className="mr-2 h-4 w-4" />
            Update Status
          </Button>
          <Button variant="destructive" onClick={() => setShowCancel(true)}>
            <XCircle className="mr-2 h-4 w-4" />
            Cancel
          </Button>
        </div>
      )}

      <Card>
        <CardHeader>
          <CardTitle>History</CardTitle>
        </CardHeader>
        <CardContent>
          <BookingHistoryTimeline
            history={history.data ?? []}
            isLoading={history.isLoading}
          />
        </CardContent>
      </Card>

      <RescheduleDialog
        open={showReschedule}
        onOpenChange={setShowReschedule}
        appointmentTypeId={b.appointment_type_id}
        isLoading={reschedule.isPending}
        onConfirm={(newScheduledAt) => {
          reschedule.mutate(
            { id: b.id, body: { new_scheduled_at: newScheduledAt } },
            {
              onSuccess: () => {
                setShowReschedule(false);
                void booking.refetch();
                void history.refetch();
              },
            }
          );
        }}
      />

      <StatusUpdateDialog
        open={showStatusUpdate}
        onOpenChange={setShowStatusUpdate}
        currentStatus={b.status}
        isLoading={statusUpdate.isPending}
        onConfirm={(status, notes) => {
          statusUpdate.mutate(
            { id: b.id, body: { status, notes } },
            {
              onSuccess: () => {
                setShowStatusUpdate(false);
                void booking.refetch();
                void history.refetch();
              },
            }
          );
        }}
      />

      <ConfirmDialog
        open={showCancel}
        onOpenChange={setShowCancel}
        title="Cancel Booking"
        description="Are you sure you want to cancel this booking? The customer will be notified via SMS."
        confirmLabel="Cancel Booking"
        variant="destructive"
        isLoading={cancel.isPending}
        onConfirm={() => {
          cancel.mutate(b.id, {
            onSuccess: () => {
              setShowCancel(false);
              navigate("/bookings");
            },
          });
        }}
      />
    </div>
  );
}
