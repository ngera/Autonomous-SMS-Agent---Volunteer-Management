// Group alerts by user-facing category for the donut + filter UI.
// One category per backend `source`. The donut chart slices map 1:1
// to filter buttons under the alerts feed.

import type { AlertItem } from "../api";

export type AlertCategory =
  | "service_change"
  | "review"
  | "suspension"
  | "candidate"
  | "at_risk_event"
  | "rule_changed"
  | "complaint"
  | "hallucination"
  | "feedback";

export const ALERT_CATEGORY_META: Record<
  AlertCategory,
  { label: string; color: string; description: string }
> = {
  service_change: {
    label: "Service changes",
    color: "#F59E0B", // amber-500
    description: "Pending SWITCH / ALSO approvals",
  },
  review: {
    label: "Reviews to grade",
    color: "#8B5CF6", // violet-500
    description: "Post-event reviews awaiting your grade",
  },
  suspension: {
    label: "Suspensions",
    color: "#F43F5E", // rose-500
    description: "Auto-suspensions awaiting OWNER review",
  },
  candidate: {
    label: "Walk-ups",
    color: "#0EA5E9", // sky-500
    description: "Unknown phones awaiting promote / dismiss",
  },
  at_risk_event: {
    label: "At-risk events",
    color: "#EF4444", // red-500
    description: "Under-filled events in the next 7 days",
  },
  rule_changed: {
    label: "Rule changes",
    color: "#D97706", // amber-600
    description:
      "Recurring rule edits that couldn't auto-apply to a materialized event",
  },
  complaint: {
    label: "Complaints",
    color: "#E11D48", // rose-600
    description: "Volunteer complaints",
  },
  hallucination: {
    label: "Hallucinations",
    color: "#7C3AED", // violet-600
    description: "AI replies flagged by volunteers",
  },
  feedback: {
    label: "Feedback",
    color: "#3B82F6", // blue-500
    description: "Volunteer feedback (informational)",
  },
};

export function categoryFor(alert: AlertItem): AlertCategory {
  const s = alert.source;
  if (s === "service_switch") return "service_change";
  if (s === "review") return "review";
  if (s === "suspension") return "suspension";
  if (s === "candidate") return "candidate";
  if (s === "at_risk_event") return "at_risk_event";
  if (s === "rule_changed") return "rule_changed";
  if (s === "issue_complaint") return "complaint";
  if (s === "issue_hallucination") return "hallucination";
  if (s === "issue_feedback") return "feedback";
  // Defensive default — surface as "complaint" so unknown sources still appear.
  return "complaint";
}

export interface AlertCategoryCount {
  category: AlertCategory;
  label: string;
  color: string;
  count: number;
}

export function countByCategory(alerts: AlertItem[]): AlertCategoryCount[] {
  const counts = new Map<AlertCategory, number>();
  for (const a of alerts) {
    const cat = categoryFor(a);
    counts.set(cat, (counts.get(cat) ?? 0) + 1);
  }
  return (Object.keys(ALERT_CATEGORY_META) as AlertCategory[]).map((cat) => ({
    category: cat,
    label: ALERT_CATEGORY_META[cat].label,
    color: ALERT_CATEGORY_META[cat].color,
    count: counts.get(cat) ?? 0,
  }));
}
