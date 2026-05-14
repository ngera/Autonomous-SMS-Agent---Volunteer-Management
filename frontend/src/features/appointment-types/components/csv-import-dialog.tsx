import { useRef, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { useCreateAppointmentType } from "../hooks/use-appointment-types";
import {
  parseAppointmentTypesCsv,
  type CsvParseResult,
} from "../lib/csv";

interface CsvImportDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

interface ImportSummary {
  succeeded: number;
  failed: { row: number; message: string }[];
}

export function CsvImportDialog({ open, onOpenChange }: CsvImportDialogProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [parsed, setParsed] = useState<CsvParseResult | null>(null);
  const [filename, setFilename] = useState<string>("");
  const [isImporting, setIsImporting] = useState(false);
  const [summary, setSummary] = useState<ImportSummary | null>(null);
  const createType = useCreateAppointmentType();

  function reset() {
    setParsed(null);
    setFilename("");
    setSummary(null);
    setIsImporting(false);
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  function handleClose(next: boolean) {
    if (!next) reset();
    onOpenChange(next);
  }

  async function handleFile(file: File) {
    setSummary(null);
    setFilename(file.name);
    const text = await file.text();
    setParsed(parseAppointmentTypesCsv(text));
  }

  async function handleImport() {
    if (!parsed || parsed.rows.length === 0) return;
    setIsImporting(true);
    const failed: ImportSummary["failed"] = [];
    let succeeded = 0;
    for (let i = 0; i < parsed.rows.length; i++) {
      const row = parsed.rows[i];
      try {
        await createType.mutateAsync(row);
        succeeded++;
      } catch (err) {
        const detail =
          (err as { response?: { data?: { detail?: string } } })?.response?.data
            ?.detail || (err as Error)?.message || "Unknown error";
        failed.push({ row: i + 2, message: `${row.name}: ${detail}` });
      }
    }
    setSummary({ succeeded, failed });
    setIsImporting(false);
  }

  const canImport =
    parsed !== null && parsed.rows.length > 0 && parsed.errors.length === 0;

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Import Appointment Types from CSV</DialogTitle>
        </DialogHeader>
        <div className="space-y-4 py-2">
          <div className="text-sm text-muted-foreground">
            CSV must include columns:{" "}
            <code className="rounded bg-muted px-1">name</code>,{" "}
            <code className="rounded bg-muted px-1">category</code>,{" "}
            <code className="rounded bg-muted px-1">duration_minutes</code>,{" "}
            <code className="rounded bg-muted px-1">price</code>. Optional:{" "}
            <code className="rounded bg-muted px-1">description</code>,{" "}
            <code className="rounded bg-muted px-1">is_active</code>.
          </div>

          <input
            ref={fileInputRef}
            type="file"
            accept=".csv,text/csv"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) void handleFile(file);
            }}
            disabled={isImporting}
            className="block w-full text-sm file:mr-3 file:rounded file:border-0 file:bg-secondary file:px-3 file:py-1.5 file:text-sm file:font-medium hover:file:bg-secondary/80"
          />

          {filename && (
            <div className="text-sm">
              <span className="text-muted-foreground">File:</span> {filename}
            </div>
          )}

          {parsed && (
            <div className="space-y-2 text-sm">
              <div>
                <span className="font-medium">{parsed.rows.length}</span> valid
                row{parsed.rows.length === 1 ? "" : "s"} ready to import.
              </div>
              {parsed.errors.length > 0 && (
                <div className="space-y-1">
                  <div className="font-medium text-destructive">
                    {parsed.errors.length} error
                    {parsed.errors.length === 1 ? "" : "s"} — fix before
                    importing:
                  </div>
                  <ul className="max-h-40 list-disc overflow-auto pl-5 text-destructive">
                    {parsed.errors.map((err, idx) => (
                      <li key={idx}>
                        Row {err.row}: {err.message}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}

          {summary && (
            <div className="space-y-2 text-sm">
              <div>
                Imported{" "}
                <span className="font-medium text-green-600">
                  {summary.succeeded}
                </span>{" "}
                row{summary.succeeded === 1 ? "" : "s"}.
              </div>
              {summary.failed.length > 0 && (
                <div className="space-y-1">
                  <div className="font-medium text-destructive">
                    {summary.failed.length} failed:
                  </div>
                  <ul className="max-h-40 list-disc overflow-auto pl-5 text-destructive">
                    {summary.failed.map((f, idx) => (
                      <li key={idx}>
                        Row {f.row}: {f.message}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>
        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => handleClose(false)}
            disabled={isImporting}
          >
            {summary ? "Close" : "Cancel"}
          </Button>
          {!summary && (
            <Button
              onClick={handleImport}
              disabled={!canImport || isImporting}
            >
              {isImporting
                ? "Importing..."
                : `Import ${parsed?.rows.length ?? 0}`}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
