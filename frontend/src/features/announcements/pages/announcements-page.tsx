import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Megaphone, Plus, Trash2 } from "lucide-react";
import { format } from "date-fns";
import { AnnouncementForm } from "../components/announcement-form";
import {
  useAnnouncements,
  useCreateAnnouncement,
  useCancelAnnouncement,
} from "../hooks/use-announcements";
import { AnnouncementStatus } from "@/types/enums";
import { useAppointmentTypes } from "@/features/appointment-types/hooks/use-appointment-types";

const STATUS_VARIANT: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  [AnnouncementStatus.DRAFT]: "outline",
  [AnnouncementStatus.SCHEDULED]: "secondary",
  [AnnouncementStatus.SENDING]: "default",
  [AnnouncementStatus.SENT]: "default",
  [AnnouncementStatus.FAILED]: "destructive",
};

export default function AnnouncementsPage() {
  const [page, setPage] = useState(1);
  const [formOpen, setFormOpen] = useState(false);

  const { data, isLoading } = useAnnouncements(page);
  const { data: appointmentTypes } = useAppointmentTypes();
  const createAnnouncement = useCreateAnnouncement();
  const cancelAnnouncement = useCancelAnnouncement();

  const items = data?.items ?? [];
  const total = data?.total ?? 0;
  const totalPages = Math.ceil(total / 20);

  function getTypeNames(ids: string[] | null) {
    if (!ids || !appointmentTypes) return "All customers";
    const names = ids
      .map((id) => appointmentTypes.find((t) => t.id === id)?.name)
      .filter(Boolean);
    return names.length > 0 ? names.join(", ") : "All customers";
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Megaphone className="h-6 w-6" />
          <h1 className="text-2xl font-bold">Announcements</h1>
        </div>
        <Button onClick={() => setFormOpen(true)}>
          <Plus className="h-4 w-4 mr-2" />
          New Announcement
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Announcement History</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <p className="text-muted-foreground py-4">Loading...</p>
          ) : items.length === 0 ? (
            <p className="text-muted-foreground py-4">
              No announcements yet
            </p>
          ) : (
            <>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Message</TableHead>
                    <TableHead>Audience</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Recipients</TableHead>
                    <TableHead>Created</TableHead>
                    <TableHead />
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {items.map((ann) => (
                    <TableRow key={ann.id}>
                      <TableCell className="max-w-[300px] truncate">
                        {ann.message}
                      </TableCell>
                      <TableCell className="text-sm">
                        {getTypeNames(ann.filter_appointment_type_ids)}
                      </TableCell>
                      <TableCell>
                        <Badge variant={STATUS_VARIANT[ann.status] ?? "outline"}>
                          {ann.status}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        {ann.status === AnnouncementStatus.SENT ||
                        ann.status === AnnouncementStatus.FAILED
                          ? `${ann.sent_count}/${ann.total_recipients}`
                          : "—"}
                      </TableCell>
                      <TableCell className="text-sm">
                        {format(new Date(ann.created_at), "MMM d, yyyy HH:mm")}
                      </TableCell>
                      <TableCell>
                        {ann.status === AnnouncementStatus.SCHEDULED && (
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-8 w-8 text-destructive"
                            onClick={() => cancelAnnouncement.mutate(ann.id)}
                            disabled={cancelAnnouncement.isPending}
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>

              {totalPages > 1 && (
                <div className="flex justify-center gap-2 pt-4">
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={page <= 1}
                    onClick={() => setPage((p) => p - 1)}
                  >
                    Previous
                  </Button>
                  <span className="text-sm py-1">
                    Page {page} of {totalPages}
                  </span>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={page >= totalPages}
                    onClick={() => setPage((p) => p + 1)}
                  >
                    Next
                  </Button>
                </div>
              )}
            </>
          )}
        </CardContent>
      </Card>

      <AnnouncementForm
        open={formOpen}
        onOpenChange={setFormOpen}
        onSubmit={(data) => {
          createAnnouncement.mutate(data, {
            onSuccess: () => setFormOpen(false),
          });
        }}
        isLoading={createAnnouncement.isPending}
      />
    </div>
  );
}
