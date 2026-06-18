import api from "@/lib/api";

export interface EvalCase {
  id: string;
  input: string;
  target: string;
  metadata: Record<string, unknown>;
}

export interface LayerSpec {
  key: string;
  label: string;
  dataset_file: string;
  target_examples: string[];
  description: string;
  schema_hint: Record<string, unknown>;
}

export interface EvalCaseListResponse {
  layer: string;
  count: number;
  cases: EvalCase[];
}

export interface DraftResponse {
  layer: string;
  draft: EvalCase;
  reasoning: string | null;
  warnings: string[];
}

export async function listLayers(): Promise<LayerSpec[]> {
  const { data } = await api.get<{ layers: LayerSpec[] }>(
    "/eval-cases/layers"
  );
  return data.layers;
}

export async function listCases(layer: string): Promise<EvalCaseListResponse> {
  const { data } = await api.get<EvalCaseListResponse>("/eval-cases", {
    params: { layer },
  });
  return data;
}

export async function getCase(layer: string, caseId: string): Promise<EvalCase> {
  const { data } = await api.get<EvalCase>(
    `/eval-cases/cases/${layer}/${encodeURIComponent(caseId)}`
  );
  return data;
}

export async function createCase(
  layer: string,
  body: EvalCase
): Promise<EvalCase> {
  const { data } = await api.post<EvalCase>(
    `/eval-cases/cases/${layer}`,
    body
  );
  return data;
}

export async function updateCase(
  layer: string,
  caseId: string,
  body: EvalCase
): Promise<EvalCase> {
  const { data } = await api.put<EvalCase>(
    `/eval-cases/cases/${layer}/${encodeURIComponent(caseId)}`,
    body
  );
  return data;
}

export async function deleteCase(layer: string, caseId: string): Promise<void> {
  await api.delete(`/eval-cases/cases/${layer}/${encodeURIComponent(caseId)}`);
}

export async function draftCaseFromProse(
  layer: string,
  description: string
): Promise<DraftResponse> {
  const { data } = await api.post<DraftResponse>("/eval-cases/draft", {
    layer,
    description,
  });
  return data;
}

// ── Runs ────────────────────────────────────────────────────────────

export interface RunSummary {
  run_id: string;
  task: string;
  layer_key: string | null;
  model: string;
  created_at: string;
  status: string; // 'success' | 'error' | 'cancelled' | 'started'
  log_path: string;
  bucket: string; // pr | nightly | weekly | smoke | ui | other
  total_samples: number;
  scores: Record<string, Record<string, number>>;
}

export interface RunSample {
  id: string;
  input: string;
  target: string;
  output: string | null;
  scores: Record<string, { value: unknown; explanation: string | null; answer: string | null }>;
}

export interface RunDetail extends RunSummary {
  samples: RunSample[];
  error: string | null;
}

export interface ActiveRun {
  run_id: string;
  layer: string;
  status: "queued" | "running" | "done" | "error";
  started_at: string;
  finished_at: string | null;
  log_path: string | null;
  error: string | null;
}

export async function listRuns(params: {
  layer?: string;
  bucket?: string;
  limit?: number;
} = {}): Promise<RunSummary[]> {
  const { data } = await api.get<RunSummary[]>("/eval-cases/runs", { params });
  return data;
}

export async function getRun(runId: string): Promise<RunDetail> {
  const { data } = await api.get<RunDetail>(
    `/eval-cases/runs/${encodeURIComponent(runId)}`
  );
  return data;
}

export async function listActiveRuns(): Promise<ActiveRun[]> {
  const { data } = await api.get<ActiveRun[]>("/eval-cases/runs/active");
  return data;
}

export async function startRun(
  layer: string,
  model?: string
): Promise<ActiveRun> {
  const { data } = await api.post<ActiveRun>("/eval-cases/runs", {
    layer,
    model,
  });
  return data;
}
