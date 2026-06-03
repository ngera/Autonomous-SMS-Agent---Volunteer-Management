import { useState } from "react";
import { format, parseISO } from "date-fns";
import { Award, Plus, Sparkles, Trophy } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import {
  useDefinitions,
  useGrantRecognition,
  useRecognitionsForContact,
} from "../hooks/use-recognition";
import { useAuth } from "@/hooks/use-auth";
import { AdminRole } from "@/types/enums";
import type { AwardKind } from "@/types/api";

const KIND_ICON: Record<AwardKind, React.ComponentType<{ className?: string }>> = {
  milestone: Sparkles,
  badge: Award,
  award: Trophy,
};

const KIND_VARIANT: Record<AwardKind, "default" | "secondary" | "outline"> = {
  milestone: "secondary",
  badge: "outline",
  award: "default",
};

interface ContactRecognitionTabProps {
  contactId: string;
}

export function ContactRecognitionTab({ contactId }: ContactRecognitionTabProps) {
  const { hasRole } = useAuth();
  const canGrant = hasRole(AdminRole.MANAGER);
  const recognitions = useRecognitionsForContact(contactId);
  const [grantOpen, setGrantOpen] = useState(false);

  if (recognitions.isLoading) {
    return <Skeleton className="h-32 w-full" />;
  }

  const rows = recognitions.data ?? [];

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          {rows.length === 0
            ? "No recognitions yet."
            : `${rows.length} recognition${rows.length === 1 ? "" : "s"} earned.`}
        </p>
        {canGrant && (
          <Button size="sm" onClick={() => setGrantOpen(true)}>
            <Plus className="mr-1 h-3 w-3" />
            Grant
          </Button>
        )}
      </div>

      {rows.length > 0 && (
        <ul className="space-y-2">
          {rows.map((r) => {
            const Icon = KIND_ICON[r.definition_kind];
            return (
              <li
                key={r.id}
                className="flex items-start gap-3 rounded-md border p-3"
              >
                <Icon className="mt-0.5 h-5 w-5 shrink-0 text-muted-foreground" />
                <div className="flex-1 space-y-1">
                  <div className="flex items-center gap-2">
                    <p className="font-medium">{r.definition_label}</p>
                    <Badge variant={KIND_VARIANT[r.definition_kind]} className="text-xs">
                      {r.definition_kind}
                    </Badge>
                    {r.granted_by_admin_id && (
                      <Badge variant="outline" className="text-xs">
                        manual
                      </Badge>
                    )}
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Earned {format(parseISO(r.earned_at), "MMM d, yyyy")}
                    {r.period_key && ` · period ${r.period_key}`}
                  </p>
                  {r.notes && (
                    <p className="text-xs italic text-muted-foreground">
                      “{r.notes}”
                    </p>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      )}

      <GrantDialog
        open={grantOpen}
        onOpenChange={setGrantOpen}
        contactId={contactId}
      />
    </div>
  );
}

interface GrantDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  contactId: string;
}

function GrantDialog({ open, onOpenChange, contactId }: GrantDialogProps) {
  const definitions = useDefinitions(false);
  const grant = useGrantRecognition();
  const [definitionId, setDefinitionId] = useState("");
  const [notes, setNotes] = useState("");

  // Manual grants are limited to badge + award kinds. Milestones are auto.
  const grantable = (definitions.data ?? []).filter(
    (d) => d.kind !== "milestone"
  );

  function reset() {
    setDefinitionId("");
    setNotes("");
  }

  function close() {
    onOpenChange(false);
    reset();
  }

  function handleSubmit() {
    if (!definitionId) return;
    grant.mutate(
      {
        contact_id: contactId,
        definition_id: definitionId,
        notes: notes.trim() || null,
      },
      { onSuccess: close }
    );
  }

  return (
    <Dialog open={open} onOpenChange={(o) => (o ? onOpenChange(true) : close())}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Grant recognition</DialogTitle>
          <DialogDescription>
            Manually grant a badge or award. Milestones are auto-evaluated
            after review approval and can't be granted by hand.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <div className="space-y-1">
            <Label>Recognition</Label>
            <Select value={definitionId} onValueChange={setDefinitionId}>
              <SelectTrigger>
                <SelectValue placeholder="Choose a badge or award" />
              </SelectTrigger>
              <SelectContent>
                {grantable.length === 0 ? (
                  <div className="p-2 text-xs text-muted-foreground">
                    No badges or awards defined yet.
                  </div>
                ) : (
                  grantable.map((d) => (
                    <SelectItem key={d.id} value={d.id}>
                      {d.label} ({d.kind})
                    </SelectItem>
                  ))
                )}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1">
            <Label htmlFor="grant-notes">Notes (optional)</Label>
            <Textarea
              id="grant-notes"
              rows={2}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Why are you granting this?"
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={close}>
            Cancel
          </Button>
          <Button
            disabled={!definitionId || grant.isPending}
            onClick={handleSubmit}
          >
            {grant.isPending ? "Granting…" : "Grant"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
