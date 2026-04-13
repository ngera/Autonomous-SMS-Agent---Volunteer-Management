import { useQuery } from "@tanstack/react-query";
import { getTokenUsageDashboard } from "../api";
import { useActiveTenantId } from "@/hooks/use-active-tenant";

export function useTokenUsageDashboard(days = 30) {
  const tenantId = useActiveTenantId();
  return useQuery({
    queryKey: ["token-usage", "dashboard", tenantId, days],
    queryFn: () => getTokenUsageDashboard(days),
    enabled: tenantId !== "none",
  });
}
