import { useState } from "react";
import { useParams } from "react-router-dom";
import { format, parseISO } from "date-fns";
import { AlertTriangle, Check, Lock, Unlock } from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { useAuth } from "@/hooks/use-auth";
import { AdminRole } from "@/types/enums";
import {
  useApproveReview,
  useFlipNoShow,
  useReviewsForEvent,
  useSkipReview,
  useUnlockReview,
} from "../hooks/use-reviews";
import { GradeSelector } from "../components/grade-selector";
import type { BookingReviewRow, ReviewStatus } from "@/types/api";

/**
 * Event review page — per-volunteer cards with grade selector,
 * "Consider striking?" flag on grade=1, Skip action, no_show → pending
 * flip, and OWNER/SUPER_ADMIN unlock for approved reviews.
 *
 * Filterable by status via tabs; default to "pending" so admins land
 * on what needs their attention.
 */
export function EventReviewPage() {
  const { slotId } = useParams<{ slotId: string }>();
  const { data, isLoading } = useReviewsForEvent(slotId);
  const [tab, setTab] = useState<ReviewStatus | "all">("pending");

  const filtered = (data ?? []).filter((r) =>
    tab === "all" ? true : r.status === tab
  );

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Event review</CardTitle>
          <CardDescription>
            Grade volunteers, flag concerns, and lock the event history.
            Approved grades feed the recruiter quality-weight signal.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Tabs value={tab} onValueChange={(v) => setTab(v as ReviewStatus | "all")}>
            <TabsList>
              <TabsTrigger value="pending">Pending</TabsTrigger>
              <TabsTrigger value="approved">Approved</TabsTrigger>
              <TabsTrigger value="no_show">No-shows</TabsTrigger>
              <TabsTrigger value="skipped">Skipped</TabsTrigger>
              <TabsTrigger value="all">All</TabsTrigger>
            </TabsList>

            <TabsContent value={tab} className="mt-4 space-y-3">
              {isLoading ? (
                <Skeleton className="h-48 w-full" />
              ) : filtered.length === 0 ? (
                <p className="rounded-md border border-dashed p-8 text-center text-sm text-muted-foreground">
                  No reviews in this state.
                </p>
              ) : (
                filtered.map((r) => (
                  <ReviewCard key={r.id} review={r} slotId={slotId} />
                ))
              )}
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>
    </div>
  );
}

interface ReviewCardProps {
  review: BookingReviewRow;
  slotId: string | undefined;
}

function ReviewCard({ review, slotId }: ReviewCardProps) {
  const { user } = useAuth();
  const [grade, setGrade] = useState<number | null>(review.grade);
  const [notes, setNotes] = useState<string>(review.grade_notes ?? "");
  const approve = useApproveReview(slotId);
  const skip = useSkipReview(slotId);
  const flip = useFlipNoShow(slotId);
  const unlock = useUnlockReview(slotId);

  const isLocked = review.status === "approved";
  const isNoShow = review.status === "no_show";
  const isSkipped = review.status === "skipped";
  const isEditable = review.status === "pending";

  const canUnlock =
    user?.role === AdminRole.SUPER_ADMIN || user?.role === AdminRole.OWNER;
  const showStrikeFlag = isEditable && grade === 1;

  function handleApprove() {
    if (!grade) return;
    approve.mutate({
      reviewId: review.id,
      grade,
      notes: notes.trim() || null,
    });
  }

  function handleSkip() {
    skip.mutate({ reviewId: review.id, notes: notes.trim() || null });
  }

  return (
    <Card
      className={
        isLocked
          ? "border-emerald-300 dark:border-emerald-900"
          : isNoShow
            ? "border-amber-300 dark:border-amber-900"
            : isSkipped
              ? "opacity-70"
              : undefined
      }
    >
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between gap-3">
          <CardTitle className="text-base">
            {review.contact_name ?? "(unnamed)"}
          </CardTitle>
          <StatusBadge review={review} />
        </div>
        <CardDescription className="text-xs">
          {review.final_check_in_at && (
            <>Checked in {format(parseISO(review.final_check_in_at), "h:mm a")}</>
          )}
          {review.final_check_out_at && (
            <> · out {format(parseISO(review.final_check_out_at), "h:mm a")}</>
          )}
          {review.total_hours != null && <> · {review.total_hours.toFixed(2)}h</>}
          {review.segments && review.segments.length > 1 && (
            <> · {review.segments.length} segments</>
          )}
        </CardDescription>
      </CardHeader>

      <CardContent className="space-y-3">
        {isNoShow && (
          <div className="rounded-md border border-amber-300 bg-amber-50 p-3 text-sm dark:border-amber-900 dark:bg-amber-950/30">
            <p className="font-medium">Marked as no-show.</p>
            <p className="text-xs text-muted-foreground">
              If the volunteer actually showed up and an admin checked them in
              retroactively, flip back to pending to grade them.
            </p>
            <Button
              size="sm"
              variant="outline"
              className="mt-2"
              onClick={() => flip.mutate(review.id)}
              disabled={flip.isPending}
            >
              Flip to pending
            </Button>
          </div>
        )}

        {isEditable && (
          <>
            <GradeSelector value={grade} onChange={setGrade} disabled={false} />
            {showStrikeFlag && (
              <div className="flex items-center gap-2 rounded-md border border-rose-300 bg-rose-50 p-2 text-xs dark:border-rose-900 dark:bg-rose-950/30">
                <AlertTriangle className="h-4 w-4 text-rose-600" />
                <span>
                  Grade 1 — consider filing a strike (manually, via the strikes flow).
                </span>
              </div>
            )}
            <Textarea
              placeholder="Notes (optional)"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              className="text-sm"
              rows={2}
            />
            <div className="flex justify-end gap-2">
              <Button
                size="sm"
                variant="outline"
                onClick={handleSkip}
                disabled={skip.isPending}
              >
                Skip review
              </Button>
              <Button
                size="sm"
                onClick={handleApprove}
                disabled={!grade || approve.isPending}
              >
                <Check className="mr-1 h-4 w-4" /> Approve
              </Button>
            </div>
          </>
        )}

        {isLocked && (
          <div className="space-y-2 text-sm">
            <p>
              <span className="text-muted-foreground">Grade:</span>{" "}
              <span className="font-semibold">{review.grade}</span> ·{" "}
              <span className="text-muted-foreground">
                Reviewed{" "}
                {review.reviewed_at
                  ? format(parseISO(review.reviewed_at), "MMM d, h:mm a")
                  : "—"}
              </span>
            </p>
            {review.grade_notes && (
              <p className="text-xs text-muted-foreground">
                "{review.grade_notes}"
              </p>
            )}
            {review.unlock_count > 0 && (
              <p className="text-xs text-muted-foreground">
                Unlocked {review.unlock_count}× · most recent{" "}
                {review.unlocked_at
                  ? format(parseISO(review.unlocked_at), "MMM d, h:mm a")
                  : "—"}
              </p>
            )}
            {canUnlock && (
              <Button
                size="sm"
                variant="outline"
                onClick={() => unlock.mutate(review.id)}
                disabled={unlock.isPending}
              >
                <Unlock className="mr-1 h-4 w-4" /> Unlock to edit
              </Button>
            )}
          </div>
        )}

        {isSkipped && (
          <div className="text-sm text-muted-foreground">
            Closed without grade. {review.grade_notes && `"${review.grade_notes}"`}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function StatusBadge({ review }: { review: BookingReviewRow }) {
  switch (review.status) {
    case "approved":
      return (
        <Badge className="bg-emerald-600 hover:bg-emerald-700">
          <Lock className="mr-1 h-3 w-3" /> Approved
        </Badge>
      );
    case "no_show":
      return <Badge variant="outline">No-show</Badge>;
    case "skipped":
      return <Badge variant="outline">Skipped</Badge>;
    case "pending":
    default:
      return <Badge>Pending</Badge>;
  }
}
