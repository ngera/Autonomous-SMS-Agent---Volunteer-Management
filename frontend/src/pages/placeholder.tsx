import { useLocation } from "react-router-dom";
import { Construction } from "lucide-react";
import { EmptyState } from "@/components/shared/empty-state";

export function PlaceholderPage() {
  const location = useLocation();
  const pageName = location.pathname.slice(1).replace(/-/g, " ");

  return (
    <EmptyState
      icon={Construction}
      title={`${pageName.charAt(0).toUpperCase() + pageName.slice(1)}`}
      description="This page is under construction and will be available soon."
    />
  );
}
