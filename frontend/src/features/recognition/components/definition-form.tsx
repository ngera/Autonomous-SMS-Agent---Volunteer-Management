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
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useCreateDefinition } from "../hooks/use-recognition";
import type {
  AwardKind,
  AwardScope,
  DefinitionCreatePayload,
  PeriodUnit,
} from "@/types/api";

interface DefinitionFormProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const METRICS = [
  { value: "hours", label: "Total hours volunteered" },
  { value: "events_completed", label: "Events completed" },
  { value: "service_count", label: "Times performing a specific service" },
  { value: "avg_grade_over_last_n", label: "Average grade over last N reviews" },
];

export function DefinitionForm({ open, onOpenChange }: DefinitionFormProps) {
  const [kind, setKind] = useState<AwardKind>("milestone");
  const [scope, setScope] = useState<AwardScope>("lifetime");
  const [periodUnit, setPeriodUnit] = useState<PeriodUnit>("month");
  const [key, setKey] = useState("");
  const [label, setLabel] = useState("");
  const [description, setDescription] = useState("");
  const [iconKey, setIconKey] = useState("");
  // Auto-criteria fields
  const [metric, setMetric] = useState("hours");
  const [threshold, setThreshold] = useState("");
  const [serviceId, setServiceId] = useState("");
  const [nGrades, setNGrades] = useState("10");

  const create = useCreateDefinition();

  function close() {
    onOpenChange(false);
    setKind("milestone");
    setScope("lifetime");
    setPeriodUnit("month");
    setKey("");
    setLabel("");
    setDescription("");
    setIconKey("");
    setMetric("hours");
    setThreshold("");
    setServiceId("");
    setNGrades("10");
  }

  function buildPayload(): DefinitionCreatePayload | null {
    const trimmedKey = key.trim();
    const trimmedLabel = label.trim();
    if (!trimmedKey || !trimmedLabel) return null;

    let auto_criteria: Record<string, unknown> | null = null;
    // Milestone requires criteria; badges/awards optional.
    const hasCriteria = kind === "milestone" || threshold.trim().length > 0;
    if (hasCriteria) {
      const t = parseFloat(threshold);
      if (Number.isNaN(t)) return null;
      if (metric === "service_count") {
        if (!serviceId.trim()) return null;
        auto_criteria = {
          metric,
          service_id: serviceId.trim(),
          threshold: t,
        };
      } else if (metric === "avg_grade_over_last_n") {
        auto_criteria = {
          metric,
          n: parseInt(nGrades, 10) || 10,
          threshold: t,
        };
      } else {
        auto_criteria = { metric, threshold: t };
      }
    }

    return {
      kind,
      key: trimmedKey,
      label: trimmedLabel,
      description: description.trim() || null,
      icon_key: iconKey.trim() || null,
      auto_criteria,
      uniqueness_scope: scope,
      period_unit: scope === "per_period" ? periodUnit : null,
    };
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const payload = buildPayload();
    if (!payload) return;
    create.mutate(payload, { onSuccess: close });
  }

  const requiresCriteria = kind === "milestone";

  return (
    <Dialog open={open} onOpenChange={(o) => (o ? onOpenChange(true) : close())}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Create recognition</DialogTitle>
          <DialogDescription>
            Defines a new milestone (auto), award (admin-granted), or badge
            (either). Once created, the kind, key, and scope are immutable —
            other fields can be edited later.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label>Kind</Label>
              <Select value={kind} onValueChange={(v) => setKind(v as AwardKind)}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="milestone">Milestone (auto)</SelectItem>
                  <SelectItem value="badge">Badge (auto or manual)</SelectItem>
                  <SelectItem value="award">Award (manual)</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <Label>Uniqueness scope</Label>
              <Select
                value={scope}
                onValueChange={(v) => setScope(v as AwardScope)}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="lifetime">Lifetime</SelectItem>
                  <SelectItem value="per_event">Per event</SelectItem>
                  <SelectItem value="per_period">Per period</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          {scope === "per_period" && (
            <div className="space-y-1">
              <Label>Period unit</Label>
              <Select
                value={periodUnit}
                onValueChange={(v) => setPeriodUnit(v as PeriodUnit)}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="month">Month</SelectItem>
                  <SelectItem value="quarter">Quarter</SelectItem>
                  <SelectItem value="year">Year</SelectItem>
                </SelectContent>
              </Select>
            </div>
          )}

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label htmlFor="rec-key">Key (stable id)</Label>
              <Input
                id="rec-key"
                value={key}
                onChange={(e) => setKey(e.target.value)}
                placeholder="e.g. 10_hour_milestone"
                required
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="rec-icon">Icon key (optional)</Label>
              <Input
                id="rec-icon"
                value={iconKey}
                onChange={(e) => setIconKey(e.target.value)}
                placeholder="e.g. trophy"
              />
            </div>
          </div>

          <div className="space-y-1">
            <Label htmlFor="rec-label">Display label</Label>
            <Input
              id="rec-label"
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              placeholder="e.g. 10-Hour Milestone"
              required
            />
          </div>

          <div className="space-y-1">
            <Label htmlFor="rec-desc">Description (optional)</Label>
            <Textarea
              id="rec-desc"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={2}
            />
          </div>

          {(requiresCriteria || threshold.trim().length > 0) && (
            <div className="space-y-3 rounded-md border bg-muted/30 p-3">
              <Label className="text-sm font-semibold">
                Auto-criteria {requiresCriteria && "(required for milestones)"}
              </Label>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <Label className="text-xs">Metric</Label>
                  <Select value={metric} onValueChange={setMetric}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {METRICS.map((m) => (
                        <SelectItem key={m.value} value={m.value}>
                          {m.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-1">
                  <Label className="text-xs">Threshold</Label>
                  <Input
                    type="number"
                    step="any"
                    value={threshold}
                    onChange={(e) => setThreshold(e.target.value)}
                    placeholder="e.g. 10"
                    required={requiresCriteria}
                  />
                </div>
              </div>
              {metric === "service_count" && (
                <div className="space-y-1">
                  <Label className="text-xs">Service UUID</Label>
                  <Input
                    value={serviceId}
                    onChange={(e) => setServiceId(e.target.value)}
                    placeholder="appointment_type_id"
                  />
                </div>
              )}
              {metric === "avg_grade_over_last_n" && (
                <div className="space-y-1">
                  <Label className="text-xs">N (most recent reviews)</Label>
                  <Input
                    type="number"
                    value={nGrades}
                    onChange={(e) => setNGrades(e.target.value)}
                    placeholder="10"
                  />
                </div>
              )}
            </div>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={close}>
              Cancel
            </Button>
            <Button type="submit" disabled={create.isPending}>
              {create.isPending ? "Creating…" : "Create"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
