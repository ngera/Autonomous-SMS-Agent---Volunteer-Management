import { format } from "date-fns";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/hooks/use-auth";
import { useNavigate } from "react-router-dom";

interface DashboardGreetingProps {
  eventsThisWeek?: number;
  needingVolunteers?: number;
  isLoading: boolean;
}

function greetingForHour(hour: number): string {
  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";
  return "Good evening";
}

function nameFromEmail(email: string): string {
  const local = email.split("@")[0] ?? "";
  const first = local.split(/[._-]/)[0] ?? "";
  if (!first) return "";
  return first.charAt(0).toUpperCase() + first.slice(1);
}

export function DashboardGreeting({
  eventsThisWeek,
  needingVolunteers,
  isLoading,
}: DashboardGreetingProps) {
  const { user } = useAuth();
  const navigate = useNavigate();
  const now = new Date();
  const greet = greetingForHour(now.getHours());
  const name = user?.email ? nameFromEmail(user.email) : "";

  return (
    <div className="flex flex-wrap items-start justify-between gap-4">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">
          {greet}{name ? `, ${name}` : ""}
        </h2>
        <div className="mt-1 text-sm text-muted-foreground">
          {format(now, "EEEE, MMMM d")}
          {isLoading ? (
            <>
              {" · "}
              <Skeleton className="inline-block h-4 w-40" />
            </>
          ) : (
            <>
              {typeof eventsThisWeek === "number" && (
                <> · {eventsThisWeek} {eventsThisWeek === 1 ? "event" : "events"} scheduled this week</>
              )}
              {typeof needingVolunteers === "number" && needingVolunteers > 0 && (
                <> · {needingVolunteers} need volunteer{needingVolunteers === 1 ? "" : "s"}</>
              )}
            </>
          )}
        </div>
      </div>
      <Button variant="outline" onClick={() => navigate("/availability")}>
        <Plus className="mr-2 h-4 w-4" />
        New event
      </Button>
    </div>
  );
}
