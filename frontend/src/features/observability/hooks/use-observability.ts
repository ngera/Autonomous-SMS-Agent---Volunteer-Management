import { useQuery } from "@tanstack/react-query";
import {
  getPhase1Metrics,
  getPhase2Metrics,
  getPhase3Metrics,
  getPhase4Metrics,
  getPhase5Metrics,
} from "../api";
import { useActiveTenantId } from "@/hooks/use-active-tenant";

export function usePhase1Metrics(days: number = 30) {
  const tenantId = useActiveTenantId();
  return useQuery({
    queryKey: ["observability", "phase1", tenantId, days],
    queryFn: () => getPhase1Metrics(days),
    enabled: tenantId !== "none",
    // 5-min stale: matches decision #33's "hourly aggregations cached
    // for 5 min" guidance on the backend side.
    staleTime: 5 * 60 * 1000,
  });
}

export function usePhase2Metrics(days: number = 30) {
  const tenantId = useActiveTenantId();
  return useQuery({
    queryKey: ["observability", "phase2", tenantId, days],
    queryFn: () => getPhase2Metrics(days),
    enabled: tenantId !== "none",
    staleTime: 5 * 60 * 1000,
  });
}

export function usePhase3Metrics(days: number = 30) {
  const tenantId = useActiveTenantId();
  return useQuery({
    queryKey: ["observability", "phase3", tenantId, days],
    queryFn: () => getPhase3Metrics(days),
    enabled: tenantId !== "none",
    staleTime: 5 * 60 * 1000,
  });
}

export function usePhase4Metrics(days: number = 30) {
  const tenantId = useActiveTenantId();
  return useQuery({
    queryKey: ["observability", "phase4", tenantId, days],
    queryFn: () => getPhase4Metrics(days),
    enabled: tenantId !== "none",
    staleTime: 5 * 60 * 1000,
  });
}

export function usePhase5Metrics(days: number = 30) {
  const tenantId = useActiveTenantId();
  return useQuery({
    queryKey: ["observability", "phase5", tenantId, days],
    queryFn: () => getPhase5Metrics(days),
    enabled: tenantId !== "none",
    staleTime: 5 * 60 * 1000,
  });
}
