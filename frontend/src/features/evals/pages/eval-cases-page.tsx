import { useEffect, useMemo, useState } from "react";
import {
  Beaker,
  CheckCircle2,
  FileJson,
  Loader2,
  Pencil,
  Plus,
  Save,
  Sparkles,
  Trash2,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import {
  useCases,
  useCreateCase,
  useDeleteCase,
  useDraftCase,
  useLayers,
  useUpdateCase,
} from "../hooks/use-evals";
import type { EvalCase, LayerSpec } from "../api";
import { RunsTab } from "./runs-tab";

function blankCase(spec: LayerSpec | undefined): EvalCase {
  return {
    id: "",
    input: "",
    target: spec?.target_examples?.[0] ?? "",
    metadata: {},
  };
}

export function EvalCasesPage() {
  return (
    <div className="space-y-4 p-6">
      <header>
        <h1 className="flex items-center gap-2 text-2xl font-semibold">
          <Beaker className="size-6 text-emerald-600" />
          AI Evals
        </h1>
        <p className="text-sm text-muted-foreground max-w-2xl">
          Author cases that gate AI changes, and browse run history. Each
          layer backs a JSONL dataset under <code>evals/datasets/</code>;
          runs land as .eval files under <code>logs/</code>.
        </p>
      </header>

      <Tabs defaultValue="cases" className="w-full">
        <TabsList>
          <TabsTrigger value="cases">Cases</TabsTrigger>
          <TabsTrigger value="runs">Runs</TabsTrigger>
        </TabsList>
        <TabsContent value="cases" className="mt-4">
          <CasesTab />
        </TabsContent>
        <TabsContent value="runs" className="mt-4">
          <RunsTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}

function CasesTab() {
  const layersQuery = useLayers();
  const layers = layersQuery.data ?? [];

  const [selectedLayer, setSelectedLayer] = useState<string | null>(null);

  // Auto-select the first layer once layers load.
  useEffect(() => {
    if (!selectedLayer && layers.length > 0) {
      setSelectedLayer(layers[0].key);
    }
  }, [layers, selectedLayer]);

  const currentSpec = useMemo(
    () => layers.find((l) => l.key === selectedLayer),
    [layers, selectedLayer]
  );

  const casesQuery = useCases(selectedLayer);
  const cases = casesQuery.data?.cases ?? [];

  const [activeCase, setActiveCase] = useState<EvalCase | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [draftOpen, setDraftOpen] = useState(false);

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-center gap-2">
          <Select
            value={selectedLayer ?? ""}
            onValueChange={(v) => {
              setSelectedLayer(v);
              setActiveCase(null);
              setIsEditing(false);
            }}
          >
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
          <Button
            onClick={() => setDraftOpen(true)}
            disabled={!currentSpec}
            size="sm"
          >
            <Sparkles className="size-4" />
            Author from prose
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={!currentSpec}
            onClick={() => {
              setActiveCase(blankCase(currentSpec));
              setIsEditing(true);
            }}
          >
            <Plus className="size-4" />
            Blank case
          </Button>
        </div>
      </header>

      {currentSpec && (
        <Card className="bg-slate-50/40 dark:bg-slate-900/30">
          <CardHeader className="py-3">
            <CardTitle className="text-base">{currentSpec.label}</CardTitle>
            <CardDescription>{currentSpec.description}</CardDescription>
          </CardHeader>
          <CardContent className="py-3">
            <div className="flex flex-wrap gap-2 text-xs">
              <span className="text-muted-foreground">Allowed targets:</span>
              {currentSpec.target_examples.map((t) => (
                <Badge key={t} variant="secondary" className="font-mono">
                  {t}
                </Badge>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center justify-between">
              Cases
              <span className="text-sm font-normal text-muted-foreground">
                {casesQuery.isLoading ? "…" : `${cases.length} total`}
              </span>
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            {casesQuery.isLoading && (
              <div className="p-6 text-sm text-muted-foreground">Loading…</div>
            )}
            {!casesQuery.isLoading && cases.length === 0 && (
              <div className="p-6 text-sm text-muted-foreground">
                No cases yet for this layer.
              </div>
            )}
            <ul className="divide-y max-h-[600px] overflow-y-auto">
              {cases.map((c) => (
                <li
                  key={c.id}
                  className={cn(
                    "px-4 py-3 hover:bg-muted/50 cursor-pointer text-sm",
                    activeCase?.id === c.id && "bg-muted/70"
                  )}
                  onClick={() => {
                    setActiveCase(c);
                    setIsEditing(false);
                  }}
                >
                  <div className="font-mono text-xs text-muted-foreground">
                    {c.id}
                  </div>
                  <div className="truncate">{c.input}</div>
                  <div className="mt-1">
                    <Badge variant="outline" className="font-mono text-[10px]">
                      {c.target}
                    </Badge>
                  </div>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>

        <CaseDetailPanel
          spec={currentSpec}
          activeCase={activeCase}
          isEditing={isEditing}
          onEdit={() => setIsEditing(true)}
          onCancelEdit={() => setIsEditing(false)}
          onClose={() => setActiveCase(null)}
          onSaved={(c) => {
            setActiveCase(c);
            setIsEditing(false);
          }}
        />
      </div>

      <DraftDialog
        open={draftOpen}
        onOpenChange={setDraftOpen}
        spec={currentSpec}
        onAccepted={(c) => {
          setActiveCase(c);
          setIsEditing(true);
          setDraftOpen(false);
        }}
      />
    </div>
  );
}

// ────────────────────────────────────────────────────────────────────

interface DetailProps {
  spec: LayerSpec | undefined;
  activeCase: EvalCase | null;
  isEditing: boolean;
  onEdit: () => void;
  onCancelEdit: () => void;
  onClose: () => void;
  onSaved: (c: EvalCase) => void;
}

function CaseDetailPanel({
  spec,
  activeCase,
  isEditing,
  onEdit,
  onCancelEdit,
  onClose,
  onSaved,
}: DetailProps) {
  const create = useCreateCase();
  const update = useUpdateCase();
  const del = useDeleteCase();

  const [draft, setDraft] = useState<EvalCase | null>(activeCase);
  const [metadataText, setMetadataText] = useState<string>(
    JSON.stringify(activeCase?.metadata ?? {}, null, 2)
  );
  const [error, setError] = useState<string | null>(null);

  // Reset when activeCase changes.
  useEffect(() => {
    setDraft(activeCase);
    setMetadataText(JSON.stringify(activeCase?.metadata ?? {}, null, 2));
    setError(null);
  }, [activeCase]);

  if (!spec) {
    return (
      <Card>
        <CardContent className="p-6 text-sm text-muted-foreground">
          Pick a layer to begin.
        </CardContent>
      </Card>
    );
  }

  if (!activeCase) {
    return (
      <Card>
        <CardContent className="p-6 text-sm text-muted-foreground">
          Select a case on the left to review, or click <b>Author from prose</b>
          {" "}to draft a new one.
        </CardContent>
      </Card>
    );
  }

  const isNewCase = !casesIncludesId(activeCase.id, spec);
  const titleText = isEditing
    ? isNewCase
      ? "New case"
      : `Editing ${activeCase.id}`
    : activeCase.id;

  const onSave = async () => {
    if (!draft) return;
    let parsedMetadata: Record<string, unknown>;
    try {
      parsedMetadata = metadataText.trim() ? JSON.parse(metadataText) : {};
    } catch (e) {
      setError(`Metadata is not valid JSON: ${(e as Error).message}`);
      return;
    }
    if (!draft.id.trim()) {
      setError("Case id is required.");
      return;
    }
    const body: EvalCase = { ...draft, metadata: parsedMetadata };
    try {
      const saved = isNewCase
        ? await create.mutateAsync({ layer: spec.key, body })
        : await update.mutateAsync({
            layer: spec.key,
            caseId: activeCase.id,
            body,
          });
      setError(null);
      onSaved(saved);
    } catch (e) {
      const err = e as { response?: { data?: { detail?: string } } };
      setError(
        err?.response?.data?.detail ?? (e as Error).message ?? "Save failed."
      );
    }
  };

  const onDelete = async () => {
    if (!confirm(`Delete case "${activeCase.id}"?`)) return;
    try {
      await del.mutateAsync({ layer: spec.key, caseId: activeCase.id });
      onClose();
    } catch (e) {
      const err = e as { response?: { data?: { detail?: string } } };
      setError(
        err?.response?.data?.detail ?? (e as Error).message ?? "Delete failed."
      );
    }
  };

  return (
    <Card>
      <CardHeader className="flex flex-row items-start justify-between space-y-0">
        <div>
          <CardTitle className="text-base">{titleText}</CardTitle>
          <CardDescription>
            {isEditing ? "Editing — unsaved changes are local." : "View only"}
          </CardDescription>
        </div>
        <div className="flex items-center gap-1">
          {!isEditing && (
            <Button variant="outline" size="sm" onClick={onEdit}>
              <Pencil className="size-3.5" />
              Edit
            </Button>
          )}
          {isEditing && (
            <>
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  onCancelEdit();
                  setDraft(activeCase);
                  setMetadataText(
                    JSON.stringify(activeCase.metadata ?? {}, null, 2)
                  );
                  setError(null);
                }}
              >
                <X className="size-3.5" />
                Cancel
              </Button>
              <Button
                size="sm"
                onClick={onSave}
                disabled={create.isPending || update.isPending}
              >
                {create.isPending || update.isPending ? (
                  <Loader2 className="size-3.5 animate-spin" />
                ) : (
                  <Save className="size-3.5" />
                )}
                Save
              </Button>
            </>
          )}
          {!isEditing && !isNewCase && (
            <Button
              variant="ghost"
              size="sm"
              onClick={onDelete}
              className="text-rose-600"
            >
              <Trash2 className="size-3.5" />
            </Button>
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {error && (
          <div className="rounded border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
            {error}
          </div>
        )}

        <div>
          <Label className="text-xs">Case id</Label>
          <Input
            value={draft?.id ?? ""}
            disabled={!isEditing}
            onChange={(e) =>
              setDraft((d) => (d ? { ...d, id: e.target.value } : d))
            }
            className="font-mono text-sm"
          />
        </div>

        <div>
          <Label className="text-xs">Input</Label>
          <Textarea
            value={draft?.input ?? ""}
            disabled={!isEditing}
            onChange={(e) =>
              setDraft((d) => (d ? { ...d, input: e.target.value } : d))
            }
            rows={3}
            className="font-mono text-sm"
          />
        </div>

        <div>
          <Label className="text-xs">Target</Label>
          {isEditing ? (
            <Select
              value={draft?.target ?? ""}
              onValueChange={(v) =>
                setDraft((d) => (d ? { ...d, target: v } : d))
              }
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {spec.target_examples.map((t) => (
                  <SelectItem key={t} value={t}>
                    {t}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          ) : (
            <Badge variant="outline" className="font-mono">
              {draft?.target}
            </Badge>
          )}
        </div>

        <div>
          <Label className="text-xs flex items-center gap-1">
            <FileJson className="size-3" />
            Metadata (JSON)
          </Label>
          <Textarea
            value={metadataText}
            disabled={!isEditing}
            onChange={(e) => setMetadataText(e.target.value)}
            rows={8}
            className="font-mono text-xs"
          />
        </div>

        <details className="text-xs">
          <summary className="cursor-pointer text-muted-foreground">
            Schema hint
          </summary>
          <pre className="mt-2 overflow-x-auto rounded bg-muted/50 p-2 text-[11px]">
            {JSON.stringify(spec.schema_hint, null, 2)}
          </pre>
        </details>
      </CardContent>
    </Card>
  );
}

function casesIncludesId(_id: string, _spec: LayerSpec | undefined) {
  // We can't determine "new vs existing" without the full case list — but
  // the caller manages that via state.  Treat any case whose id was
  // present when it landed in the panel as existing. For simplicity here:
  // an empty id means "new", anything else assumes existing (matches the
  // page-level logic where blank cases come in via the "Blank case"
  // button with id="" and drafted ones may have a real id but not yet be
  // in the dataset).
  return _id.trim() !== "" && _id !== "__draft__";
}

// ────────────────────────────────────────────────────────────────────

interface DraftDialogProps {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  spec: LayerSpec | undefined;
  onAccepted: (c: EvalCase) => void;
}

function DraftDialog({
  open,
  onOpenChange,
  spec,
  onAccepted,
}: DraftDialogProps) {
  const draft = useDraftCase();
  const [description, setDescription] = useState("");

  // Reset whenever the dialog opens for a new layer.
  useEffect(() => {
    if (open) {
      setDescription("");
      draft.reset();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, spec?.key]);

  const result = draft.data;

  const submit = async () => {
    if (!spec || !description.trim()) return;
    await draft.mutateAsync({ layer: spec.key, description: description.trim() });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Sparkles className="size-4 text-emerald-600" />
            Author eval case from prose
          </DialogTitle>
          <DialogDescription>
            Describe what behavior the test should exercise. Claude drafts
            the JSONL row — you then review + edit before saving.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3">
          <div>
            <Label className="text-xs">Layer</Label>
            <div className="rounded bg-muted/50 px-3 py-2 text-sm">
              {spec?.label ?? "—"}
            </div>
          </div>

          <div>
            <Label className="text-xs">
              Describe the test (plain English)
            </Label>
            <Textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="e.g. when admin types 'cancel the muster for the food drive on saturday', the classifier should return cancel_muster with event_reference containing 'food drive'."
              rows={5}
            />
          </div>

          {draft.isError && (
            <div className="rounded border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
              {(draft.error as Error).message}
            </div>
          )}

          {result && (
            <div className="space-y-2">
              <div className="flex items-center gap-2 text-sm text-emerald-700">
                <CheckCircle2 className="size-4" />
                Draft ready — review then load into the editor.
              </div>
              {result.reasoning && (
                <div className="rounded bg-emerald-50 px-3 py-2 text-xs text-emerald-900">
                  <b>Reasoning:</b> {result.reasoning}
                </div>
              )}
              {result.warnings.length > 0 && (
                <ul className="rounded bg-amber-50 px-3 py-2 text-xs text-amber-900 list-disc list-inside">
                  {result.warnings.map((w, i) => (
                    <li key={i}>{w}</li>
                  ))}
                </ul>
              )}
              <pre className="max-h-72 overflow-auto rounded bg-muted p-3 text-[11px] font-mono">
                {JSON.stringify(result.draft, null, 2)}
              </pre>
            </div>
          )}
        </div>

        <DialogFooter>
          {!result && (
            <Button
              onClick={submit}
              disabled={draft.isPending || !description.trim()}
            >
              {draft.isPending && <Loader2 className="size-4 animate-spin" />}
              Draft with Claude
            </Button>
          )}
          {result && (
            <Button onClick={() => onAccepted(result.draft)}>
              Load into editor
            </Button>
          )}
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Close
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
