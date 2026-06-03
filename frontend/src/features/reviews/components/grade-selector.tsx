import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface GradeSelectorProps {
  value: number | null;
  onChange: (grade: number) => void;
  disabled?: boolean;
}

/**
 * Grade scale 1-5 per decision #6.
 * 1 = problem (triggers Consider Striking? flag)
 * 3 = met expectations (neutral / cold-start default for targeting)
 * 5 = exceptional
 */
const GRADE_LABELS: Record<number, string> = {
  1: "Problem",
  2: "Below",
  3: "Met",
  4: "Strong",
  5: "Exceptional",
};

export function GradeSelector({ value, onChange, disabled }: GradeSelectorProps) {
  return (
    <div className="flex gap-2">
      {[1, 2, 3, 4, 5].map((g) => (
        <Button
          key={g}
          type="button"
          size="sm"
          variant={value === g ? "default" : "outline"}
          onClick={() => onChange(g)}
          disabled={disabled}
          className={cn(
            "flex-1 flex-col gap-1 py-3",
            value === g && g === 1 && "border-rose-500 bg-rose-500"
          )}
        >
          <span className="text-lg font-bold">{g}</span>
          <span className="text-xs font-normal opacity-80">
            {GRADE_LABELS[g]}
          </span>
        </Button>
      ))}
    </div>
  );
}
