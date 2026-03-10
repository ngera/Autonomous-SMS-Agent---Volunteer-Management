import { useState } from "react";
import { ArrowLeft, ShieldBan, ShieldCheck, ShieldOff, UserX } from "lucide-react";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/shared/page-header";
import { useAuth } from "@/hooks/use-auth";
import { AdminRole } from "@/types/enums";
import type { SuspensionResponse } from "@/types/api";
import {
  useSuspensions,
  useLiftSuspension,
  useConfirmSuspension,
  useBanUser,
} from "../hooks/use-suspensions";
import { SuspensionsTable } from "../components/suspensions-table";
import { SuspensionDetailCard } from "../components/suspension-detail-card";
import { ReviewDialog } from "../components/review-dialog";
import { ManualSuspendDialog } from "../components/manual-suspend-dialog";

type ReviewAction = "lift" | "confirm" | "ban";

export function SuspensionsPage() {
  const { hasRole } = useAuth();
  const canEdit = hasRole(AdminRole.MANAGER);
  const canBan = hasRole(AdminRole.OWNER);
  const { data, isLoading } = useSuspensions();

  const [selected, setSelected] = useState<SuspensionResponse | null>(null);
  const [reviewAction, setReviewAction] = useState<ReviewAction | null>(null);
  const [showManualSuspend, setShowManualSuspend] = useState(false);

  const lift = useLiftSuspension();
  const confirm = useConfirmSuspension();
  const ban = useBanUser();

  function handleReview(notes: string) {
    if (!selected || !reviewAction) return;
    const mutation =
      reviewAction === "lift" ? lift : reviewAction === "confirm" ? confirm : ban;
    mutation.mutate(
      { id: selected.id, body: { notes } },
      {
        onSuccess: () => {
          setReviewAction(null);
          setSelected(null);
        },
      }
    );
  }

  if (selected) {
    const needsReview = !selected.review_decision;
    return (
      <div className="space-y-4">
        <Button variant="ghost" size="sm" onClick={() => setSelected(null)}>
          <ArrowLeft className="mr-1 h-3 w-3" />
          Back to list
        </Button>

        <SuspensionDetailCard suspension={selected} />

        {needsReview && canEdit && (
          <div className="flex gap-2">
            <Button
              size="sm"
              onClick={() => setReviewAction("lift")}
            >
              <ShieldOff className="mr-1 h-3 w-3" />
              Lift
            </Button>
            <Button
              size="sm"
              variant="destructive"
              onClick={() => setReviewAction("confirm")}
            >
              <ShieldCheck className="mr-1 h-3 w-3" />
              Confirm
            </Button>
            {canBan && (
              <Button
                size="sm"
                variant="destructive"
                onClick={() => setReviewAction("ban")}
              >
                <ShieldBan className="mr-1 h-3 w-3" />
                Ban
              </Button>
            )}
          </div>
        )}

        {reviewAction && (
          <ReviewDialog
            open
            action={reviewAction}
            phone={selected.contact_phone}
            onClose={() => setReviewAction(null)}
            onSubmit={handleReview}
            isPending={lift.isPending || confirm.isPending || ban.isPending}
          />
        )}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Suspensions"
        description="Review and manage customer suspensions."
        actions={
          canEdit ? (
            <Button
              size="sm"
              variant="destructive"
              onClick={() => setShowManualSuspend(true)}
            >
              <UserX className="mr-1 h-3 w-3" />
              Manual Suspend
            </Button>
          ) : undefined
        }
      />

      <SuspensionsTable
        suspensions={data?.items ?? []}
        isLoading={isLoading}
        onSelect={setSelected}
      />

      <ManualSuspendDialog
        open={showManualSuspend}
        onClose={() => setShowManualSuspend(false)}
      />
    </div>
  );
}
