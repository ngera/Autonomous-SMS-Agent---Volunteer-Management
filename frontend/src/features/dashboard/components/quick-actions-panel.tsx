import { useNavigate } from "react-router-dom";
import { CalendarPlus, MessageSquarePlus, RefreshCcw } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

interface QuickAction {
  label: string;
  icon: typeof CalendarPlus;
  to: string;
}

const ACTIONS: QuickAction[] = [
  { label: "Schedule event", icon: CalendarPlus, to: "/availability" },
  { label: "Send announcement", icon: MessageSquarePlus, to: "/announcements" },
  { label: "Edit recurring template", icon: RefreshCcw, to: "/availability" },
];

export function QuickActionsPanel() {
  const navigate = useNavigate();

  return (
    <Card>
      <CardHeader>
        <CardTitle>Quick actions</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {ACTIONS.map((action) => (
          <Button
            key={action.label}
            variant="outline"
            className="w-full justify-start"
            onClick={() => navigate(action.to)}
          >
            <action.icon className="mr-2 h-4 w-4" />
            {action.label}
          </Button>
        ))}
      </CardContent>
    </Card>
  );
}
