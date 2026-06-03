import { useMemo, useState } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { format, parseISO } from "date-fns";
import {
  useCandidates,
  useDismissCandidate,
} from "../hooks/use-candidates";
import { InviteCandidateModal } from "../components/invite-candidate-modal";
import type { CandidateStatus, VolunteerCandidate } from "@/types/api";

const STATUS_LABELS: Record<CandidateStatus, string> = {
  new: "New",
  invited: "Invited",
  dismissed: "Dismissed",
};

const STATUS_VARIANTS: Record<CandidateStatus, "default" | "secondary" | "outline"> = {
  new: "default",
  invited: "secondary",
  dismissed: "outline",
};

export function CandidatesListPage() {
  const [statusFilter, setStatusFilter] = useState<CandidateStatus | "all">("new");
  const filterParam = statusFilter === "all" ? undefined : statusFilter;
  const { data, isLoading } = useCandidates(filterParam);
  const dismiss = useDismissCandidate();

  const [inviteTarget, setInviteTarget] = useState<VolunteerCandidate | null>(null);

  const sortedData = useMemo(
    () =>
      (data ?? []).slice().sort((a, b) => {
        // 'new' first by recency; everything else by recency.
        return (
          new Date(b.last_seen_at).getTime() -
          new Date(a.last_seen_at).getTime()
        );
      }),
    [data]
  );

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Walk-up candidates</CardTitle>
          <CardDescription>
            Unknown phones that texted in during a live event. Invite them to
            promote to a real volunteer, or dismiss the signal.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Tabs
            value={statusFilter}
            onValueChange={(v) =>
              setStatusFilter(v as CandidateStatus | "all")
            }
          >
            <TabsList>
              <TabsTrigger value="new">New</TabsTrigger>
              <TabsTrigger value="invited">Invited</TabsTrigger>
              <TabsTrigger value="dismissed">Dismissed</TabsTrigger>
              <TabsTrigger value="all">All</TabsTrigger>
            </TabsList>

            <TabsContent value={statusFilter} className="mt-4">
              {isLoading ? (
                <Skeleton className="h-32 w-full" />
              ) : sortedData.length === 0 ? (
                <p className="rounded-md border border-dashed p-8 text-center text-sm text-muted-foreground">
                  No candidates in this state.
                </p>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Phone</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Last seen</TableHead>
                      <TableHead>Signals</TableHead>
                      <TableHead>Last message</TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {sortedData.map((c) => (
                      <TableRow key={c.id}>
                        <TableCell className="font-mono">{c.phone}</TableCell>
                        <TableCell>
                          <Badge variant={STATUS_VARIANTS[c.status]}>
                            {STATUS_LABELS[c.status]}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-sm text-muted-foreground">
                          {format(parseISO(c.last_seen_at), "MMM d, h:mm a")}
                        </TableCell>
                        <TableCell className="tabular-nums">
                          {c.occurrence_count}
                        </TableCell>
                        <TableCell className="max-w-xs truncate text-sm text-muted-foreground">
                          {c.last_message_body ?? "—"}
                        </TableCell>
                        <TableCell className="text-right">
                          {c.status === "new" ? (
                            <div className="flex justify-end gap-2">
                              <Button
                                size="sm"
                                onClick={() => setInviteTarget(c)}
                              >
                                Invite
                              </Button>
                              <Button
                                size="sm"
                                variant="outline"
                                disabled={dismiss.isPending}
                                onClick={() => {
                                  if (
                                    confirm(
                                      `Dismiss the signal from ${c.phone}? This is preserved for audit but won't trigger more notifications.`
                                    )
                                  ) {
                                    dismiss.mutate({ id: c.id });
                                  }
                                }}
                              >
                                Dismiss
                              </Button>
                            </div>
                          ) : (
                            <span className="text-xs text-muted-foreground">
                              {c.status === "invited" ? "Promoted" : "Closed"}
                            </span>
                          )}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>

      <InviteCandidateModal
        candidate={inviteTarget}
        open={!!inviteTarget}
        onOpenChange={(open) => {
          if (!open) setInviteTarget(null);
        }}
      />
    </div>
  );
}
