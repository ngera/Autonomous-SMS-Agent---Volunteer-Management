import { Eye, EyeOff, Pencil, UserCircle2 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { StatusBadge } from "@/components/shared/status-badge";
import { cn, formatPhone } from "@/lib/utils";
import { useAuth } from "@/hooks/use-auth";
import { AdminRole, ContactSex } from "@/types/enums";
import type {
  CustomerResponse,
  RosterVisibility,
  RosterVisibilityHistoryEntry,
} from "@/types/api";
import { useAppointmentTypes } from "@/features/appointment-types/hooks/use-appointment-types";

const SEX_LABELS: Record<string, string> = {
  [ContactSex.MALE]: "Male",
  [ContactSex.FEMALE]: "Female",
  [ContactSex.NON_BINARY]: "Non-binary",
  [ContactSex.PREFER_NOT_TO_SAY]: "Prefer not to say",
};

interface CustomerInfoCardProps {
  customer: CustomerResponse;
  onEditClick?: () => void;
}

export function CustomerInfoCard({ customer, onEditClick }: CustomerInfoCardProps) {
  const { hasRole } = useAuth();
  const canEdit = hasRole(AdminRole.MANAGER);
  const { data: appointmentTypes } = useAppointmentTypes();

  const prefTypes = (appointmentTypes ?? []).filter((t) =>
    customer.preferred_appointment_type_ids?.includes(t.id)
  );

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>Contact Information</CardTitle>
        <div className="flex items-center gap-2">
          {customer.background_check_required && (
            <Badge variant="destructive">Background check required</Badge>
          )}
          {customer.consent_status && (
            <StatusBadge type="consent" value={customer.consent_status} />
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {customer.background_check_required && (
          <div className="rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-200">
            This volunteer is blocked from booking appointments until their
            background check is cleared. Toggle the flag off in Edit when ready.
          </div>
        )}
        <div>
          <Label className="text-muted-foreground">Phone</Label>
          <p className="font-medium">{formatPhone(customer.phone)}</p>
        </div>
        <div>
          <Label className="text-muted-foreground">Name</Label>
          <p className="font-medium">{customer.name || "—"}</p>
        </div>
        <div>
          <Label className="text-muted-foreground">Email</Label>
          <p className="font-medium">{customer.email || "—"}</p>
        </div>
        <div>
          <Label className="text-muted-foreground">Sex</Label>
          <p className="font-medium">
            {customer.sex ? SEX_LABELS[customer.sex] || customer.sex : "—"}
          </p>
        </div>
        {prefTypes.length > 0 && (
          <div>
            <Label className="text-muted-foreground">Preferred Appointment Types</Label>
            <div className="flex flex-wrap gap-1 mt-1">
              {prefTypes.map((t) => (
                <Badge key={t.id} variant="secondary">{t.name}</Badge>
              ))}
            </div>
          </div>
        )}
        <div>
          <Label className="text-muted-foreground">Background check</Label>
          <p
            className={`font-medium ${customer.background_check_required ? "text-destructive" : ""}`}
          >
            {customer.background_check_required ? "Required" : "Not required"}
          </p>
        </div>
        <RosterVisibilityBlock
          current={customer.default_roster_visibility}
          history={customer.roster_visibility_history}
        />
        {canEdit && onEditClick && (
          <Button size="sm" variant="outline" onClick={onEditClick}>
            <Pencil className="mr-1 h-3 w-3" />
            Edit
          </Button>
        )}
      </CardContent>
    </Card>
  );
}

const VISIBILITY_META: Record<
  RosterVisibility | "unset",
  { label: string; Icon: React.ComponentType<{ className?: string }>; color: string }
> = {
  hidden: {
    label: "Hidden",
    Icon: EyeOff,
    color: "text-muted-foreground",
  },
  first_name: {
    label: "First name",
    Icon: Eye,
    color: "text-sky-600 dark:text-sky-400",
  },
  full_name: {
    label: "Full name",
    Icon: UserCircle2,
    color: "text-emerald-600 dark:text-emerald-400",
  },
  unset: {
    label: "Hidden (default)",
    Icon: EyeOff,
    color: "text-muted-foreground/70",
  },
};

function RosterVisibilityBlock({
  current,
  history,
}: {
  current: RosterVisibility | null;
  history: RosterVisibilityHistoryEntry[];
}) {
  // `null` means the volunteer has never stated a preference; the
  // backend treats that as hidden by default, so we surface "Hidden
  // (default)" to make the distinction visible (volunteer never opted
  // in vs. volunteer explicitly picked hidden).
  const kind: RosterVisibility | "unset" = current ?? "unset";
  const meta = VISIBILITY_META[kind];
  const Icon = meta.Icon;
  return (
    <div>
      <Label className="text-muted-foreground">Roster visibility</Label>
      <p className={cn("flex items-center gap-1.5 font-medium", meta.color)}>
        <Icon className="h-4 w-4 shrink-0" />
        {meta.label}
      </p>
      <p className="mt-0.5 text-xs text-muted-foreground">
        Admins always see the full name + phone regardless of this setting.
        The choice above only affects what other volunteers see on shared
        rosters.
      </p>
      {history.length > 0 && (
        <details className="mt-2">
          <summary className="cursor-pointer text-xs text-muted-foreground hover:text-foreground">
            {history.length} change{history.length === 1 ? "" : "s"} on
            record
          </summary>
          <ul className="mt-1.5 space-y-1 border-l pl-3 text-xs">
            {history.map((h, i) => (
              <RosterHistoryRow key={`${h.changed_at}:${i}`} entry={h} />
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}

function RosterHistoryRow({ entry }: { entry: RosterVisibilityHistoryEntry }) {
  const fromLabel = entry.previous_value
    ? VISIBILITY_META[entry.previous_value].label
    : VISIBILITY_META.unset.label;
  const toLabel = VISIBILITY_META[entry.new_value].label;
  const actor =
    entry.source === "admin" ? "admin update" : "via SMS";
  const when = (() => {
    try {
      return new Date(entry.changed_at).toLocaleString(undefined, {
        month: "short",
        day: "numeric",
        year: "numeric",
        hour: "numeric",
        minute: "2-digit",
      });
    } catch {
      return entry.changed_at;
    }
  })();
  return (
    <li className="text-muted-foreground">
      <span className="text-foreground">{fromLabel}</span>
      {" → "}
      <span className="text-foreground">{toLabel}</span>
      <span className="ml-1.5">· {when} · {actor}</span>
    </li>
  );
}
