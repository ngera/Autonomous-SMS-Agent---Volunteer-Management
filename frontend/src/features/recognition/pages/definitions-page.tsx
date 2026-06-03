import { useState } from "react";
import { format, parseISO } from "date-fns";
import { Award, Plus, Trophy, Sparkles } from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  useDefinitions,
  useDeactivateDefinition,
  useUpdateDefinition,
} from "../hooks/use-recognition";
import { DefinitionForm } from "../components/definition-form";
import type { AwardDefinitionRow, AwardKind } from "@/types/api";

const KIND_ICON: Record<AwardKind, React.ComponentType<{ className?: string }>> = {
  milestone: Sparkles,
  badge: Award,
  award: Trophy,
};

const KIND_LABELS: Record<AwardKind, string> = {
  milestone: "Milestone",
  badge: "Badge",
  award: "Award",
};

export function RecognitionDefinitionsPage() {
  const [showInactive, setShowInactive] = useState(false);
  const [formOpen, setFormOpen] = useState(false);
  const { data, isLoading } = useDefinitions(showInactive);
  const update = useUpdateDefinition();
  const deactivate = useDeactivateDefinition();

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <CardTitle>Recognition definitions</CardTitle>
            <CardDescription>
              Milestones (auto), awards (admin-granted), and badges. Auto-criteria
              evaluate after every review approval; the matching scope rule
              prevents duplicate grants.
            </CardDescription>
          </div>
          <div className="flex items-center gap-3">
            <label className="flex items-center gap-2 text-sm">
              <Switch
                checked={showInactive}
                onCheckedChange={setShowInactive}
              />
              Show inactive
            </label>
            <Button onClick={() => setFormOpen(true)}>
              <Plus className="mr-1 h-4 w-4" /> New
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <Skeleton className="h-48 w-full" />
          ) : data && data.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Recognition</TableHead>
                  <TableHead>Kind</TableHead>
                  <TableHead>Scope</TableHead>
                  <TableHead>Auto-criteria</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.map((d) => (
                  <DefinitionRow
                    key={d.id}
                    definition={d}
                    onToggleActive={(active) =>
                      update.mutate({ id: d.id, body: { is_active: active } })
                    }
                    onDeactivate={() => {
                      if (
                        confirm(
                          `Deactivate "${d.label}"? Historical recognitions stay; new evaluations will skip it.`
                        )
                      ) {
                        deactivate.mutate(d.id);
                      }
                    }}
                    busy={update.isPending || deactivate.isPending}
                  />
                ))}
              </TableBody>
            </Table>
          ) : (
            <p className="rounded-md border border-dashed p-8 text-center text-sm text-muted-foreground">
              No definitions yet. Create your first milestone to start
              rewarding volunteers automatically.
            </p>
          )}
        </CardContent>
      </Card>

      <DefinitionForm open={formOpen} onOpenChange={setFormOpen} />
    </div>
  );
}

interface DefinitionRowProps {
  definition: AwardDefinitionRow;
  onToggleActive: (active: boolean) => void;
  onDeactivate: () => void;
  busy: boolean;
}

function DefinitionRow({
  definition,
  onToggleActive,
  onDeactivate,
  busy,
}: DefinitionRowProps) {
  const Icon = KIND_ICON[definition.kind];
  const criteriaSummary = formatCriteria(definition.auto_criteria);
  return (
    <TableRow className={definition.is_active ? "" : "opacity-60"}>
      <TableCell>
        <div className="flex items-center gap-2">
          <Icon className="h-4 w-4 text-muted-foreground" />
          <div>
            <p className="font-medium">{definition.label}</p>
            <p className="text-xs text-muted-foreground">
              <code className="rounded bg-muted px-1 text-[10px]">
                {definition.key}
              </code>{" "}
              · created {format(parseISO(definition.created_at), "MMM d")}
            </p>
          </div>
        </div>
      </TableCell>
      <TableCell>
        <Badge variant="outline">{KIND_LABELS[definition.kind]}</Badge>
      </TableCell>
      <TableCell className="text-xs">
        <Badge variant="secondary">{definition.uniqueness_scope}</Badge>
        {definition.period_unit && (
          <span className="ml-1 text-muted-foreground">
            / {definition.period_unit}
          </span>
        )}
      </TableCell>
      <TableCell className="text-xs text-muted-foreground">
        {criteriaSummary || "—"}
      </TableCell>
      <TableCell className="text-right">
        <div className="flex justify-end gap-2">
          <Switch
            checked={definition.is_active}
            onCheckedChange={onToggleActive}
            disabled={busy}
          />
          {definition.is_active && (
            <Button
              size="sm"
              variant="outline"
              onClick={onDeactivate}
              disabled={busy}
            >
              Deactivate
            </Button>
          )}
        </div>
      </TableCell>
    </TableRow>
  );
}

function formatCriteria(criteria: Record<string, unknown> | null): string {
  if (!criteria) return "";
  const metric = String(criteria.metric ?? "");
  const t = criteria.threshold;
  switch (metric) {
    case "hours":
      return `≥ ${t}h volunteered`;
    case "events_completed":
      return `≥ ${t} events`;
    case "service_count":
      return `≥ ${t} of service ${String(criteria.service_id ?? "?").slice(0, 8)}…`;
    case "avg_grade_over_last_n":
      return `Avg grade ≥ ${t} over last ${criteria.n ?? 10}`;
    default:
      return metric ? `${metric}: ${t ?? "?"}` : "";
  }
}
