import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createCase,
  deleteCase,
  draftCaseFromProse,
  getRun,
  listActiveRuns,
  listCases,
  listLayers,
  listRuns,
  startRun,
  updateCase,
  type EvalCase,
} from "../api";

export function useLayers() {
  return useQuery({
    queryKey: ["eval-cases", "layers"],
    queryFn: listLayers,
    staleTime: 5 * 60 * 1000,
  });
}

export function useCases(layer: string | null) {
  return useQuery({
    queryKey: ["eval-cases", "list", layer],
    queryFn: () => listCases(layer!),
    enabled: !!layer,
  });
}

export function useCreateCase() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ layer, body }: { layer: string; body: EvalCase }) =>
      createCase(layer, body),
    onSuccess: (_data, { layer }) => {
      qc.invalidateQueries({ queryKey: ["eval-cases", "list", layer] });
    },
  });
}

export function useUpdateCase() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      layer,
      caseId,
      body,
    }: {
      layer: string;
      caseId: string;
      body: EvalCase;
    }) => updateCase(layer, caseId, body),
    onSuccess: (_data, { layer }) => {
      qc.invalidateQueries({ queryKey: ["eval-cases", "list", layer] });
    },
  });
}

export function useDeleteCase() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ layer, caseId }: { layer: string; caseId: string }) =>
      deleteCase(layer, caseId),
    onSuccess: (_data, { layer }) => {
      qc.invalidateQueries({ queryKey: ["eval-cases", "list", layer] });
    },
  });
}

export function useDraftCase() {
  return useMutation({
    mutationFn: ({
      layer,
      description,
    }: {
      layer: string;
      description: string;
    }) => draftCaseFromProse(layer, description),
  });
}

// ── Runs ────────────────────────────────────────────────────────────

export function useRuns(layer: string | null) {
  return useQuery({
    queryKey: ["eval-cases", "runs", layer],
    queryFn: () => listRuns({ layer: layer ?? undefined }),
    staleTime: 15 * 1000,
  });
}

export function useRun(runId: string | null) {
  return useQuery({
    queryKey: ["eval-cases", "runs", "detail", runId],
    queryFn: () => getRun(runId!),
    enabled: !!runId,
  });
}

// Polls every 2s while there's at least one in-flight run. The poll is
// cheap (in-memory dict on the server); useful so the Run-now flow
// shows live status without manual refresh.
export function useActiveRuns(enabled: boolean) {
  return useQuery({
    queryKey: ["eval-cases", "runs", "active"],
    queryFn: listActiveRuns,
    refetchInterval: enabled ? 2000 : false,
    enabled,
  });
}

export function useStartRun() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ layer, model }: { layer: string; model?: string }) =>
      startRun(layer, model),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["eval-cases", "runs", "active"] });
    },
  });
}
