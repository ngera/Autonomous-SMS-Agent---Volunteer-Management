import { useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  useRelatedServices,
  useCreateRelatedService,
  useDeleteRelatedService,
} from "../hooks/use-appointment-types";
import type { AppointmentTypeResponse } from "@/types/api";

interface RelatedServicesPanelProps {
  typeId: string;
  allTypes: AppointmentTypeResponse[];
}

export function RelatedServicesPanel({
  typeId,
  allTypes,
}: RelatedServicesPanelProps) {
  const related = useRelatedServices(typeId);
  const createRelated = useCreateRelatedService();
  const deleteRelated = useDeleteRelatedService();

  const [showAdd, setShowAdd] = useState(false);
  const [relatedTypeId, setRelatedTypeId] = useState("");
  const [message, setMessage] = useState("");

  const availableTypes = allTypes.filter(
    (t) =>
      t.id !== typeId &&
      !related.data?.some((r) => r.related_appointment_type_id === t.id)
  );

  function handleAdd() {
    if (!relatedTypeId || !message) return;
    createRelated.mutate(
      { typeId, body: { related_appointment_type_id: relatedTypeId, suggestion_message: message } },
      {
        onSuccess: () => {
          setShowAdd(false);
          setRelatedTypeId("");
          setMessage("");
        },
      }
    );
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle className="text-base">Related Services</CardTitle>
        <Button size="sm" variant="outline" onClick={() => setShowAdd(!showAdd)}>
          <Plus className="mr-1 h-3 w-3" />
          Add
        </Button>
      </CardHeader>
      <CardContent className="space-y-3">
        {showAdd && (
          <div className="space-y-2 rounded-md border p-3">
            <div className="space-y-1">
              <Label className="text-xs">Related Type</Label>
              <Select value={relatedTypeId} onValueChange={(v) => setRelatedTypeId(v ?? "")}>
                <SelectTrigger>
                  <SelectValue placeholder="Select type" />
                </SelectTrigger>
                <SelectContent>
                  {availableTypes.map((t) => (
                    <SelectItem key={t.id} value={t.id}>
                      {t.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <Label className="text-xs">Suggestion Message</Label>
              <Input
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                placeholder="You might also be interested in..."
              />
            </div>
            <Button size="sm" onClick={handleAdd} disabled={createRelated.isPending}>
              {createRelated.isPending ? "Adding..." : "Add"}
            </Button>
          </div>
        )}

        {related.isLoading ? (
          <p className="text-sm text-muted-foreground">Loading...</p>
        ) : !related.data || related.data.length === 0 ? (
          <p className="text-sm text-muted-foreground">No related services.</p>
        ) : (
          related.data.map((r) => {
            const relatedType = allTypes.find(
              (t) => t.id === r.related_appointment_type_id
            );
            return (
              <div
                key={r.id}
                className="flex items-center justify-between rounded-md border p-2"
              >
                <div>
                  <p className="text-sm font-medium">
                    {relatedType?.name ?? "Unknown"}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {r.suggestion_message}
                  </p>
                </div>
                <Button
                  size="icon"
                  variant="ghost"
                  onClick={() =>
                    deleteRelated.mutate({ typeId, relatedId: r.id })
                  }
                >
                  <Trash2 className="h-4 w-4 text-destructive" />
                </Button>
              </div>
            );
          })
        )}
      </CardContent>
    </Card>
  );
}
