import { useEffect, useMemo, useState } from "react";
import {
  AlertCircle,
  CheckCircle2,
  Clock,
  Loader2,
  Play,
  PlayCircle,
  XCircle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";
import {
  useActiveRuns,
  useLayers,
  useRun,
  useRuns,
  useStartRun,
} from "../hooks/use-evals";
import type { LayerSpec, RunSample, RunSummary } from "../api";

const BUCKET_COLORS: Record<string, string> = {
  pr: "bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-200",
  nightly:
    "bg-violet-100 text-violet-800 dark:bg-violet-900/40 dark:text-violet-200",
  weekly:
    "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-200",
  ui: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-200",
  smoke:
    "bg-slate-100 text-slate-700 dark:bg-slate-800/60 dark:text-slate-200",
};

function bucketBadge(bucket: string) {
  return (
    <Badge
      variant="outline"
      className={cn(
        "uppercase tracking-wide text-[10px] font-medium",
        BUCKET_COLORS[bucket] ?? BUCKET_COLORS.smoke
      )}
    >
      {bucket}
    </Badge>
  );
}

function formatDate(iso: string) {
  const d = new Date(iso);
  if (isNaN(d.getTime())) return iso;
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function statusIcon(status: string) {
  if (status === "success" || status === "done")
    return <CheckCircle2 className="size-3.5 text-emerald-600" />;
  if (status === "error" || status === "cancelled")
    return <XCircle className="size-3.5 text-rose-600" />;
  if (status === "running")
    return <Loader2 className="size-3.5 text-sky-600 animate-spin" />;
  return <Clock className="size-3.5 text-amber-600" />;
}

function headlineScore(summary: RunSummary): {
  label: string;
  value: number | null;
} {
  // Prefer 'accuracy' if present (Layers 1, 2, 5), else 'mean' (Layer 4).
  for (const [scorer, metrics] of Object.entries(summary.scores)) {
    if ("accuracy" in metrics) return { label: scorer, value: metrics.accuracy };
    if ("mean" in metrics) return { label: scorer, value: metrics.mean };
  }
  return { label: "—", value: null };
}

export function RunsTab() {
  const layersQuery = useLayers();
  const layers = layersQuery.data ?? [];

  const [filterLayer, setFilterLayer] = useState<string>("__all__");
  const [activeRunId, setActiveRunId] = useState<string | null>(null);

  const runsQuery = useRuns(
    filterLayer === "__all__" ? null : filterLayer
  );
  const runs = runsQuery.data ?? [];

  const runDetailQuery = useRun(activeRunId);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="flex items-end gap-2">
          <div>
            <label className="text-xs text-muted-foreground block">
              Filter by layer
            </label>
            <Select value={filterLayer} onValueChange={setFilterLayer}>
              <SelectTrigger className="w-[280px]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="__all__">All layers</SelectItem>
                {layers.map((l) => (
                  <SelectItem key={l.key} value={l.key}>
                    {l.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        <RunNowControl layers={layers} />
      </div>

      <ActiveRunsBanner
        onRunFinished={() => {
          runsQuery.refetch();
        }}
      />

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)]">
        <Card>
          <CardHeader className="py-3">
            <CardTitle className="text-base flex items-center justify-between">
              Run history
              <span className="text-sm font-normal text-muted-foreground">
                {runsQuery.isLoading ? "…" : `${runs.length} runs`}
              </span>
            </CardTitle>
            <CardDescription>
              Reads from logs/. Newest first.
            </CardDescription>
          </CardHeader>
          <CardContent className="p-0">
            {runsQuery.isLoading && (
              <div className="p-6 text-sm text-muted-foreground">Loading…</div>
            )}
            {!runsQuery.isLoading && runs.length === 0 && (
              <div className="p-6 text-sm text-muted-foreground">
                No runs yet. Click <b>Run now</b> to launch the first one.
              </div>
            )}
            <ul className="divide-y max-h-[600px] overflow-y-auto">
              {runs.map((r) => {
                const headline = headlineScore(r);
                const headlinePct =
                  headline.value !== null
                    ? `${(headline.value * 100).toFixed(0)}%`
                    : "—";
                return (
                  <li
                    key={r.run_id}
                    className={cn(
                      "px-4 py-3 hover:bg-muted/50 cursor-pointer text-sm",
                      activeRunId === r.run_id && "bg-muted/70"
                    )}
                    onClick={() => setActiveRunId(r.run_id)}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-2 min-w-0">
                        {statusIcon(r.status)}
                        <span className="font-mono text-xs truncate">
                          {r.task}
                        </span>
                        {bucketBadge(r.bucket)}
                      </div>
                      <div
                        className={cn(
                          "font-mono text-sm font-semibold",
                          headline.value !== null && headline.value < 0.9
                            ? "text-rose-600"
                            : "text-emerald-700"
                        )}
                      >
                        {headlinePct}
                      </div>
                    </div>
                    <div className="mt-1 flex items-center justify-between gap-2 text-xs text-muted-foreground">
                      <span>{formatDate(r.created_at)}</span>
                      <span>{r.total_samples} samples · {r.model}</span>
                    </div>
                  </li>
                );
              })}
            </ul>
          </CardContent>
        </Card>

        <RunDetailPanel
          run={runDetailQuery.data ?? null}
          loading={runDetailQuery.isLoading}
        />
      </div>
    </div>
  );
}

// ────────────────────────────────────────────────────────────────────

function RunNowControl({ layers }: { layers: LayerSpec[] }) {
  const [chosen, setChosen] = useState<string>(layers[0]?.key ?? "");
  const start = useStartRun();
  const [err, setErr] = useState<string | null>(null);

  // Keep chosen in sync if layers load late.
  useEffect(() => {
    if (!chosen && layers.length > 0) setChosen(layers[0].key);
  }, [layers, chosen]);

  const onClick = async () => {
    if (!chosen) return;
    setErr(null);
    try {
      await start.mutateAsync({ layer: chosen });
    } catch (e) {
      const r = e as { response?: { data?: { detail?: string } } };
      setErr(r?.response?.data?.detail ?? (e as Error).message ?? "Failed.");
    }
  };

  return (
    <div className="flex items-end gap-2">
      <div>
        <label className="text-xs text-muted-foreground block">
          Run a layer now
        </label>
        <Select value={chosen} onValueChange={setChosen}>
          <SelectTrigger className="w-[280px]">
            <SelectValue placeholder="Choose a layer" />
          </SelectTrigger>
          <SelectContent>
            {layers.map((l) => (
              <SelectItem key={l.key} value={l.key}>
                {l.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      <Button onClick={onClick} disabled={start.isPending || !chosen}>
        {start.isPending ? (
          <Loader2 className="size-4 animate-spin" />
        ) : (
          <Play className="size-4" />
        )}
        Run now
      </Button>
      {err && (
        <div className="text-xs text-rose-600 ml-2 max-w-[280px]">{err}</div>
      )}
    </div>
  );
}

// ────────────────────────────────────────────────────────────────────

function ActiveRunsBanner({
  onRunFinished,
}: {
  onRunFinished: () => void;
}) {
  // We always poll if the user is on this tab — cheap (in-memory dict).
  const activeQuery = useActiveRuns(true);
  const active = activeQuery.data ?? [];

  // Detect transitions so we can refresh the history once a run finishes.
  const [prevFinished, setPrevFinished] = useState<Set<string>>(new Set());
  useEffect(() => {
    const nowFinished = new Set(
      active
        .filter((r) => r.status === "done" || r.status === "error")
        .map((r) => r.run_id)
    );
    let added = false;
    for (const id of nowFinished) {
      if (!prevFinished.has(id)) {
        added = true;
        break;
      }
    }
    if (added) {
      onRunFinished();
      setPrevFinished(nowFinished);
    } else if (nowFinished.size !== prevFinished.size) {
      setPrevFinished(nowFinished);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active]);

  if (active.length === 0) return null;

  return (
    <Card className="border-sky-200 bg-sky-50/50 dark:bg-sky-950/30">
      <CardContent className="p-3 space-y-2">
        <div className="flex items-center gap-2 text-sm font-medium">
          <PlayCircle className="size-4 text-sky-600" />
          In-flight runs ({active.length})
        </div>
        <ul className="space-y-1.5">
          {active.map((r) => (
            <li key={r.run_id} className="text-xs flex items-center gap-2">
              {statusIcon(r.status)}
              <span className="font-mono">{r.layer}</span>
              <span className="text-muted-foreground">·</span>
              <span className="text-muted-foreground">{r.status}</span>
              {r.error && (
                <span className="text-rose-600 truncate max-w-[400px]">
                  · {r.error}
                </span>
              )}
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}

// ────────────────────────────────────────────────────────────────────

interface DetailProps {
  run: import("../api").RunDetail | null;
  loading: boolean;
}

function RunDetailPanel({ run, loading }: DetailProps) {
  if (loading) {
    return (
      <Card>
        <CardContent className="p-6 text-sm text-muted-foreground">
          Loading…
        </CardContent>
      </Card>
    );
  }
  if (!run) {
    return (
      <Card>
        <CardContent className="p-6 text-sm text-muted-foreground">
          Pick a run on the left to see per-sample scores.
        </CardContent>
      </Card>
    );
  }

  const passing = run.samples.filter((s) => firstScoreIsCorrect(s)).length;

  return (
    <Card>
      <CardHeader className="py-3">
        <CardTitle className="text-base flex flex-wrap items-center gap-2">
          {statusIcon(run.status)}
          <span className="font-mono text-sm">{run.task}</span>
          {bucketBadge(run.bucket)}
          <span className="text-xs font-normal text-muted-foreground ml-auto">
            {formatDate(run.created_at)}
          </span>
        </CardTitle>
        <CardDescription className="flex flex-wrap items-center gap-3 text-xs">
          <span>{run.model}</span>
          <span>·</span>
          <span>
            {passing}/{run.samples.length} passing
          </span>
          {Object.entries(run.scores).map(([scorer, metrics]) =>
            Object.entries(metrics).map(([m, v]) => (
              <span key={`${scorer}.${m}`}>
                · {scorer}.{m}={(v as number).toFixed(3)}
              </span>
            ))
          )}
        </CardDescription>
      </CardHeader>
      <CardContent className="p-0">
        {run.error && (
          <div className="mx-4 mb-3 rounded border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700">
            {run.error}
          </div>
        )}
        <ul className="divide-y max-h-[600px] overflow-y-auto">
          {run.samples.map((s) => (
            <SampleRow key={s.id} sample={s} />
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}

function firstScoreIsCorrect(s: RunSample): boolean {
  for (const v of Object.values(s.scores)) {
    const raw = v.value;
    if (raw === "C" || raw === 1 || raw === 1.0 || raw === true) return true;
    if (typeof raw === "number" && raw >= 4) return true; // rubric 1-5
    return false;
  }
  return false;
}

function SampleRow({ sample }: { sample: RunSample }) {
  const ok = firstScoreIsCorrect(sample);
  const [open, setOpen] = useState(false);

  return (
    <li className="px-4 py-3 text-sm">
      <button
        type="button"
        className="w-full flex items-start gap-2 text-left"
        onClick={() => setOpen((v) => !v)}
      >
        {ok ? (
          <CheckCircle2 className="size-3.5 text-emerald-600 mt-0.5 shrink-0" />
        ) : (
          <AlertCircle className="size-3.5 text-rose-600 mt-0.5 shrink-0" />
        )}
        <div className="min-w-0 flex-1">
          <div className="font-mono text-xs text-muted-foreground">
            {sample.id}
          </div>
          <div className="truncate">{sample.input}</div>
        </div>
        <Badge variant="outline" className="font-mono text-[10px]">
          {sample.target}
        </Badge>
      </button>
      {open && (
        <div className="mt-2 ml-5 space-y-1.5 text-xs">
          <div>
            <span className="text-muted-foreground">Output: </span>
            <span className="font-mono">{sample.output ?? "(none)"}</span>
          </div>
          {Object.entries(sample.scores).map(([scorer, sc]) => (
            <div key={scorer}>
              <span className="text-muted-foreground">{scorer}: </span>
              <span className="font-mono">{String(sc.value)}</span>
              {sc.explanation && (
                <span className="text-muted-foreground">
                  {" — "}
                  {sc.explanation}
                </span>
              )}
            </div>
          ))}
        </div>
      )}
    </li>
  );
}
