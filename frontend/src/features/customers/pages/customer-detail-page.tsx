import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { ArrowLeft, Send, Ban, Pencil, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { PageHeader } from "@/components/shared/page-header";
import { LoadingState } from "@/components/shared/loading-state";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { DataTable, type Column } from "@/components/shared/data-table";
import { StatusBadge } from "@/components/shared/status-badge";
import { formatDateTime, formatPhone, formatCurrency } from "@/lib/utils";
import { useAuth } from "@/hooks/use-auth";
import { AdminRole } from "@/types/enums";
import type { BookingResponse, ConversationResponse } from "@/types/api";
import { CustomerInfoCard } from "../components/customer-info-card";
import { CustomerPatternCard } from "../components/customer-pattern-card";
import { CustomerForm } from "../components/customer-form";
import {
  useCustomer,
  useCustomerBookings,
  useCustomerConversations,
  useCustomerPattern,
  useUpdateCustomer,
  useDeleteCustomer,
  useSendOptinOutreach,
  useManualOptout,
} from "../hooks/use-customers";

const bookingColumns: Column<BookingResponse>[] = [
  { key: "date", header: "Date", render: (b) => formatDateTime(b.scheduled_at) },
  { key: "status", header: "Status", render: (b) => <StatusBadge type="booking" value={b.status} /> },
  { key: "price", header: "Price", render: (b) => formatCurrency(b.price_at_booking), className: "text-right" },
];

const conversationColumns: Column<ConversationResponse>[] = [
  { key: "status", header: "Status", render: (c) => <StatusBadge type="conversation" value={c.status} /> },
  { key: "step", header: "Step", render: (c) => c.current_step || "—" },
  { key: "lastMsg", header: "Last Message", render: (c) => formatDateTime(c.last_message_at) },
  { key: "created", header: "Started", render: (c) => formatDateTime(c.created_at) },
];

export function CustomerDetailPage() {
  const { phone: rawPhone } = useParams<{ phone: string }>();
  const phone = rawPhone ? decodeURIComponent(rawPhone) : "";
  const navigate = useNavigate();
  const { hasRole } = useAuth();
  const canEdit = hasRole(AdminRole.MANAGER);

  const customer = useCustomer(phone);
  const bookings = useCustomerBookings(phone);
  const conversations = useCustomerConversations(phone);
  const patterns = useCustomerPattern(phone);
  const updateCustomer = useUpdateCustomer();
  const deleteCustomer = useDeleteCustomer();
  const optinOutreach = useSendOptinOutreach();
  const manualOptout = useManualOptout();

  const [showOptout, setShowOptout] = useState(false);
  const [optoutReason, setOptoutReason] = useState("");
  const [showEdit, setShowEdit] = useState(false);
  const [showDelete, setShowDelete] = useState(false);

  if (customer.isLoading) return <LoadingState />;
  if (!customer.data) return <p>Customer not found.</p>;

  const c = customer.data;

  return (
    <div className="space-y-6">
      <PageHeader
        title={c.name || formatPhone(c.phone)}
        description={formatPhone(c.phone)}
        actions={
          <div className="flex gap-2">
            {canEdit && (
              <>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => setShowEdit(true)}
                >
                  <Pencil className="mr-1 h-3 w-3" />
                  Edit
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => optinOutreach.mutate(phone)}
                  disabled={optinOutreach.isPending}
                >
                  <Send className="mr-1 h-3 w-3" />
                  {optinOutreach.isPending ? "Sending..." : "Send Opt-in"}
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  className="text-destructive"
                  onClick={() => setShowOptout(true)}
                >
                  <Ban className="mr-1 h-3 w-3" />
                  Opt Out
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  className="text-destructive"
                  onClick={() => setShowDelete(true)}
                >
                  <Trash2 className="mr-1 h-3 w-3" />
                  Delete
                </Button>
              </>
            )}
            <Button variant="ghost" size="sm" onClick={() => navigate("/customers")}>
              <ArrowLeft className="mr-1 h-3 w-3" />
              Back
            </Button>
          </div>
        }
      />

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-1">
          <CustomerInfoCard customer={c} />
        </div>

        <div className="lg:col-span-2">
          <Tabs defaultValue="bookings">
            <TabsList>
              <TabsTrigger value="bookings">Bookings</TabsTrigger>
              <TabsTrigger value="conversations">Conversations</TabsTrigger>
              <TabsTrigger value="pattern">Pattern</TabsTrigger>
            </TabsList>

            <TabsContent value="bookings" className="mt-4">
              <DataTable
                columns={bookingColumns}
                data={bookings.data ?? []}
                isLoading={bookings.isLoading}
                emptyMessage="No bookings."
                onRowClick={(b) => navigate(`/bookings/${b.id}`)}
              />
            </TabsContent>

            <TabsContent value="conversations" className="mt-4">
              <DataTable
                columns={conversationColumns}
                data={conversations.data ?? []}
                isLoading={conversations.isLoading}
                emptyMessage="No conversations."
                onRowClick={(conv) => navigate(`/conversations/${conv.id}`)}
              />
            </TabsContent>

            <TabsContent value="pattern" className="mt-4">
              <CustomerPatternCard
                patterns={patterns.data ?? []}
                phone={phone}
                isLoading={patterns.isLoading}
              />
            </TabsContent>
          </Tabs>
        </div>
      </div>

      <CustomerForm
        open={showEdit}
        onOpenChange={setShowEdit}
        editItem={c}
        onSubmit={(data) => {
          updateCustomer.mutate(
            {
              phone,
              body: {
                name: data.name,
                email: data.email,
                reminder_preference_days: data.reminder_preference_days,
              },
            },
            {
              onSuccess: () => {
                setShowEdit(false);
                void customer.refetch();
              },
            }
          );
        }}
        isLoading={updateCustomer.isPending}
      />

      <ConfirmDialog
        open={showDelete}
        onOpenChange={setShowDelete}
        title="Delete Customer"
        description={`Are you sure you want to delete ${c.name || formatPhone(c.phone)}? This cannot be undone. Customers with active bookings cannot be deleted.`}
        confirmLabel="Delete"
        variant="destructive"
        onConfirm={() => {
          deleteCustomer.mutate(phone, {
            onSuccess: () => navigate("/customers"),
          });
        }}
        isLoading={deleteCustomer.isPending}
      />

      <Dialog open={showOptout} onOpenChange={setShowOptout}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Manual Opt-Out</DialogTitle>
          </DialogHeader>
          <div className="py-2 space-y-2">
            <p className="text-sm text-muted-foreground">
              This will immediately opt out {formatPhone(phone)} from all reminders.
            </p>
            <Textarea
              placeholder="Reason for opt-out (required)"
              value={optoutReason}
              onChange={(e) => setOptoutReason(e.target.value)}
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowOptout(false)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              disabled={!optoutReason || manualOptout.isPending}
              onClick={() => {
                manualOptout.mutate(
                  { phone, body: { reason: optoutReason } },
                  {
                    onSuccess: () => {
                      setShowOptout(false);
                      setOptoutReason("");
                      void customer.refetch();
                    },
                  }
                );
              }}
            >
              {manualOptout.isPending ? "Processing..." : "Confirm Opt-Out"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
