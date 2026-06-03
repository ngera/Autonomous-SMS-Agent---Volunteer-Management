import api from "@/lib/api";
import type { ObservabilityMetric } from "@/types/api";

export async function getPhase1Metrics(
  days: number = 30
): Promise<ObservabilityMetric[]> {
  const { data } = await api.get<ObservabilityMetric[]>(
    "/observability/phase1",
    { params: { days } }
  );
  return data;
}

export async function getPhase2Metrics(
  days: number = 30
): Promise<ObservabilityMetric[]> {
  const { data } = await api.get<ObservabilityMetric[]>(
    "/observability/phase2",
    { params: { days } }
  );
  return data;
}

export async function getPhase3Metrics(
  days: number = 30
): Promise<ObservabilityMetric[]> {
  const { data } = await api.get<ObservabilityMetric[]>(
    "/observability/phase3",
    { params: { days } }
  );
  return data;
}

export async function getPhase4Metrics(
  days: number = 30
): Promise<ObservabilityMetric[]> {
  const { data } = await api.get<ObservabilityMetric[]>(
    "/observability/phase4",
    { params: { days } }
  );
  return data;
}

export async function getPhase5Metrics(
  days: number = 30
): Promise<ObservabilityMetric[]> {
  const { data } = await api.get<ObservabilityMetric[]>(
    "/observability/phase5",
    { params: { days } }
  );
  return data;
}
