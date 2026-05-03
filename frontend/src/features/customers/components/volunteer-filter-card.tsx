import { Search, X } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import {
  ContactStatus,
  ConsentStatus,
  AvailabilitySlot,
  AVAILABILITY_OPTIONS,
} from "@/types/enums";

const STATUS_CHIPS: { value: ContactStatus; label: string }[] = [
  { value: ContactStatus.ACTIVE, label: "Active" },
  { value: ContactStatus.SUSPENDED, label: "Suspended" },
  { value: ContactStatus.BANNED, label: "Banned" },
];

const CONSENT_CHIPS: { value: ConsentStatus; label: string }[] = [
  { value: ConsentStatus.OPTED_IN, label: "Opted in" },
  { value: ConsentStatus.PENDING, label: "Pending" },
  { value: ConsentStatus.UNCONTACTED, label: "Uncontacted" },
  { value: ConsentStatus.OPTED_OUT, label: "Opted out" },
  { value: ConsentStatus.BLOCKED, label: "Blocked" },
];

interface VolunteerFilterCardProps {
  search: string;
  onSearchChange: (v: string) => void;
  status?: ContactStatus;
  onStatusChange: (s: ContactStatus | undefined) => void;
  consent?: ConsentStatus;
  onConsentChange: (c: ConsentStatus | undefined) => void;
  bgCheckRequired?: boolean;
  onBgCheckChange: (v: boolean | undefined) => void;
  availability?: AvailabilitySlot;
  onAvailabilityChange: (v: AvailabilitySlot | undefined) => void;
}

interface ChipProps {
  label: string;
  selected: boolean;
  onClick: () => void;
}

function Chip({ label, selected, onClick }: ChipProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-3 py-1 text-xs transition-colors",
        selected
          ? "border-emerald-500 bg-emerald-50 text-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-200"
          : "border-border bg-background hover:bg-muted"
      )}
    >
      {label}
      {selected && <X className="h-3 w-3" />}
    </button>
  );
}

export function VolunteerFilterCard({
  search,
  onSearchChange,
  status,
  onStatusChange,
  consent,
  onConsentChange,
  bgCheckRequired,
  onBgCheckChange,
  availability,
  onAvailabilityChange,
}: VolunteerFilterCardProps) {
  const activeCount =
    (search ? 1 : 0) +
    (status ? 1 : 0) +
    (consent ? 1 : 0) +
    (bgCheckRequired === true ? 1 : 0) +
    (availability ? 1 : 0);

  function clearAll() {
    onSearchChange("");
    onStatusChange(undefined);
    onConsentChange(undefined);
    onBgCheckChange(undefined);
    onAvailabilityChange(undefined);
  }

  return (
    <div className="rounded-lg border bg-emerald-50/30 p-4 dark:bg-emerald-950/10">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="relative w-full max-w-sm">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={search}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder="Search by name or email"
            className="pl-9"
          />
        </div>
        {activeCount > 0 && (
          <Button
            variant="ghost"
            size="sm"
            className="text-emerald-700 hover:text-emerald-900 dark:text-emerald-300"
            onClick={clearAll}
          >
            Clear all ({activeCount})
          </Button>
        )}
      </div>

      <div className="mt-4 space-y-2.5">
        <FilterRow label="status">
          {STATUS_CHIPS.map((chip) => (
            <Chip
              key={chip.value}
              label={chip.label}
              selected={status === chip.value}
              onClick={() =>
                onStatusChange(status === chip.value ? undefined : chip.value)
              }
            />
          ))}
        </FilterRow>

        <FilterRow label="consent">
          {CONSENT_CHIPS.map((chip) => (
            <Chip
              key={chip.value}
              label={chip.label}
              selected={consent === chip.value}
              onClick={() =>
                onConsentChange(consent === chip.value ? undefined : chip.value)
              }
            />
          ))}
        </FilterRow>

        <FilterRow label="available">
          {AVAILABILITY_OPTIONS.map((opt) => (
            <Chip
              key={opt.value}
              label={opt.label}
              selected={availability === opt.value}
              onClick={() =>
                onAvailabilityChange(
                  availability === opt.value ? undefined : opt.value
                )
              }
            />
          ))}
        </FilterRow>

        <FilterRow label="background check">
          <Chip
            label="Required"
            selected={bgCheckRequired === true}
            onClick={() =>
              onBgCheckChange(bgCheckRequired === true ? undefined : true)
            }
          />
        </FilterRow>
      </div>
    </div>
  );
}

function FilterRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="w-24 shrink-0 text-xs text-muted-foreground">{label}</span>
      <div className="flex flex-wrap gap-1.5">{children}</div>
    </div>
  );
}
