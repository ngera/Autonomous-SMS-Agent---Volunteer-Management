import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface WindowPickerProps {
  value: number;
  onChange: (days: number) => void;
}

const OPTIONS = [
  { label: "7d", value: 7 },
  { label: "30d", value: 30 },
  { label: "90d", value: 90 },
];

export function WindowPicker({ value, onChange }: WindowPickerProps) {
  return (
    <div className="inline-flex rounded-md border border-border bg-card p-1">
      {OPTIONS.map((opt) => (
        <Button
          key={opt.value}
          type="button"
          size="sm"
          variant="ghost"
          className={cn(
            "px-3 py-1 text-xs font-medium",
            value === opt.value && "bg-primary text-primary-foreground"
          )}
          onClick={() => onChange(opt.value)}
        >
          {opt.label}
        </Button>
      ))}
    </div>
  );
}
