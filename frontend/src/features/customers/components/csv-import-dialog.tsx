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
          <DialogTitle>Import Customers (CSV)</DialogTitle>
        </DialogHeader>
        {result ? (
          <div className="space-y-2 py-2">
            <p className="text-sm">
              Imported: <strong>{result.imported}</strong> | Skipped:{" "}
              <strong>{result.skipped}</strong>
            </p>
            {result.errors.length > 0 && (
              <div className="text-sm text-destructive space-y-1">
                {result.errors.slice(0, 10).map((e, i) => (
                  <p key={i}>{e}</p>
                ))}
              </div>
            )}
          </div>
        ) : (
          <div className="py-2">
            <p className="text-sm text-muted-foreground mb-3">
              CSV columns: phone (required), name (optional), email (optional)
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
