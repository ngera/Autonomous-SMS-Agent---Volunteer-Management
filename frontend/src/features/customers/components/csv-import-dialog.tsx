import { useState, useRef } from "react";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useImportCsv } from "../hooks/use-customers";
import type { CsvImportResponse } from "@/types/api";

interface CsvImportDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function CsvImportDialog({ open, onOpenChange }: CsvImportDialogProps) {
  const importCsv = useImportCsv();
  const fileRef = useRef<HTMLInputElement>(null);
  const [result, setResult] = useState<CsvImportResponse | null>(null);

  function handleImport() {
    const file = fileRef.current?.files?.[0];
    if (!file) return;
    importCsv.mutate(file, {
      onSuccess: (data) => setResult(data),
    });
  }

  function handleClose() {
    setResult(null);
    onOpenChange(false);
  }

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Import Volunteers (CSV)</DialogTitle>
        </DialogHeader>
        {result ? (
          <div className="space-y-2 py-2">
            <p className="text-sm">
              Created: <strong>{result.imported}</strong> | Updated:{" "}
              <strong>{result.updated}</strong> | Skipped:{" "}
              <strong>{result.skipped}</strong>
            </p>
            {result.errors.length > 0 && (
              <div className="text-sm text-destructive space-y-1 max-h-40 overflow-y-auto">
                {result.errors.slice(0, 20).map((e, i) => (
                  <p key={i}>{e}</p>
                ))}
                {result.errors.length > 20 && (
                  <p className="text-muted-foreground">
                    …{result.errors.length - 20} more error(s) suppressed.
                  </p>
                )}
              </div>
            )}
          </div>
        ) : (
          <div className="py-2 space-y-2">
            <p className="text-sm text-muted-foreground">
              Required column: <code>phone</code>. Existing volunteers (matched
              by phone) are <strong>updated in place</strong>; new phones are
              created. Files exported from this page round-trip.
            </p>
            <p className="text-xs text-muted-foreground">
              Recognized columns: <code>phone</code>, <code>name</code>,{" "}
              <code>email</code>, <code>sex</code>, <code>status</code>,{" "}
              <code>consent</code>, <code>background_check_required</code>,{" "}
              <code>all_services_enabled</code>, <code>services</code>,{" "}
              <code>availability</code>, <code>weekly_hours</code>,{" "}
              <code>unavailable_dates</code>,{" "}
              <code>reminder_preference_days</code>. The <code>hours</code>{" "}
              column is computed and ignored on import.
            </p>
            <Input ref={fileRef} type="file" accept=".csv" />
          </div>
        )}
        <DialogFooter>
          {result ? (
            <Button onClick={handleClose}>Done</Button>
          ) : (
            <>
              <Button variant="outline" onClick={handleClose}>
                Cancel
              </Button>
              <Button onClick={handleImport} disabled={importCsv.isPending}>
                {importCsv.isPending ? "Importing..." : "Import"}
              </Button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
