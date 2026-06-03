import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { VolunteerCandidate } from "@/types/api";
import { useInviteCandidate } from "../hooks/use-candidates";

interface InviteCandidateModalProps {
  candidate: VolunteerCandidate | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

/**
 * Walk-up candidate invite modal (Phase 1 step 5d).
 *
 * Name is required (per the locked Row 4 Invite decision — admin
 * supplies the name; no SMS round-trip to ask for it). On submit,
 * the candidate is promoted to a real Contact + ContactConsent
 * (PENDING) and the candidate row is stamped as 'invited'.
 */
export function InviteCandidateModal({
  candidate,
  open,
  onOpenChange,
}: InviteCandidateModalProps) {
  const [name, setName] = useState("");
  const invite = useInviteCandidate();

  function close() {
    onOpenChange(false);
    setName("");
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!candidate || !name.trim()) return;
    invite.mutate(
      { id: candidate.id, name: name.trim() },
      { onSuccess: close }
    );
  }

  return (
    <Dialog open={open} onOpenChange={(o) => (o ? onOpenChange(true) : close())}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Invite candidate</DialogTitle>
          <DialogDescription>
            {candidate && (
              <>
                Promote <span className="font-mono">{candidate.phone}</span> to a
                real volunteer. The recruiter will send the standard opt-in
                invite once you provide a name.
              </>
            )}
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1">
            <Label htmlFor="candidate-name">Volunteer name (required)</Label>
            <Input
              id="candidate-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Maya Chen"
              required
              autoFocus
            />
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={close}>
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={!name.trim() || invite.isPending}
            >
              {invite.isPending ? "Sending invite…" : "Send invite"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
