import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { StatusBadge } from "@/components/shared/status-badge";
import { formatDateTime } from "@/lib/utils";
import type { SuspensionResponse } from "@/types/api";

interface SuspensionDetailCardProps {
  suspension: SuspensionResponse;
}

export function SuspensionDetailCard({ suspension }: SuspensionDetailCardProps) {
  const fields = [
    { label: "Phone", value: suspension.contact_phone },
    {
      label: "Type",
      value: <StatusBadge type="suspension" value={suspension.suspension_type} />,
    },
    { label: "Reason", value: suspension.reason },
    {
      label: "Triggering Message",
      value: suspension.triggering_message ? (
        <span className="italic">"{suspension.triggering_message}"</span>
      ) : "—",
    },
    { label: "Suspended At", value: formatDateTime(suspension.suspended_at) },
    {
      label: "Notification Sent",
      value: suspension.notification_sent_at
        ? formatDateTime(suspension.notification_sent_at)
        : "Not sent",
    },
    {
      label: "Review Decision",
      value: suspension.review_decision ? (
        <StatusBadge type="review" value={suspension.review_decision} />
      ) : (
        "Pending"
      ),
    },
    {
      label: "Reviewed At",
      value: suspension.reviewed_at
        ? formatDateTime(suspension.reviewed_at)
        : "—",
    },
    {
      label: "Review Notes",
      value: suspension.review_notes || "—",
    },
    {
      label: "Lifted At",
      value: suspension.lifted_at ? formatDateTime(suspension.lifted_at) : "—",
    },
  ];

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Suspension Details</CardTitle>
      </CardHeader>
      <CardContent>
        <dl className="grid grid-cols-2 gap-x-6 gap-y-3">
          {fields.map((f) => (
            <div key={f.label}>
              <dt className="text-xs text-muted-foreground">{f.label}</dt>
              <dd className="text-sm mt-0.5">{f.value}</dd>
            </div>
          ))}
        </dl>
      </CardContent>
    </Card>
  );
}
