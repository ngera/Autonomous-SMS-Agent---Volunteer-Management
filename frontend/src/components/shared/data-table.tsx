import type { ReactNode } from "react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import { Checkbox } from "@/components/ui/checkbox";

export interface Column<T> {
  key: string;
  header: string;
  render: (item: T) => ReactNode;
  className?: string;
}

interface SelectionProps<T> {
  /** Stable per-row identity used for selection state. */
  getRowId: (item: T) => string;
  /** Currently selected row IDs. */
  selectedIds: Set<string>;
  /** Called when a single row's checkbox is toggled. */
  onToggleRow: (id: string, item: T) => void;
  /** Called when the header checkbox is toggled — receives all currently-rendered row IDs. */
  onToggleAll: (checked: boolean, allIds: string[]) => void;
}

interface DataTableProps<T> {
  columns: Column<T>[];
  data: T[];
  isLoading?: boolean;
  skeletonRows?: number;
  emptyMessage?: string;
  onRowClick?: (item: T) => void;
  /** When provided, renders a leading checkbox column. */
  selection?: SelectionProps<T>;
}

export function DataTable<T>({
  columns,
  data,
  isLoading = false,
  skeletonRows = 5,
  emptyMessage = "No data found.",
  onRowClick,
  selection,
}: DataTableProps<T>) {
  const allRowIds = selection ? data.map((item) => selection.getRowId(item)) : [];
  const allSelected =
    selection && allRowIds.length > 0 &&
    allRowIds.every((id) => selection.selectedIds.has(id));
  const someSelected =
    selection && allRowIds.some((id) => selection.selectedIds.has(id));

  return (
    <div className="rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            {selection && (
              <TableHead className="w-10">
                <Checkbox
                  checked={
                    allSelected
                      ? true
                      : someSelected
                        ? "indeterminate"
                        : false
                  }
                  onCheckedChange={(checked) =>
                    selection.onToggleAll(checked === true, allRowIds)
                  }
                  aria-label="Select all rows"
                />
              </TableHead>
            )}
            {columns.map((col) => (
              <TableHead key={col.key} className={col.className}>
                {col.header}
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {isLoading
            ? Array.from({ length: skeletonRows }).map((_, i) => (
                <TableRow key={i}>
                  {selection && (
                    <TableCell>
                      <Skeleton className="h-5 w-5" />
                    </TableCell>
                  )}
                  {columns.map((col) => (
                    <TableCell key={col.key}>
                      <Skeleton className="h-5 w-full" />
                    </TableCell>
                  ))}
                </TableRow>
              ))
            : data.length === 0
              ? (
                <TableRow>
                  <TableCell
                    colSpan={columns.length + (selection ? 1 : 0)}
                    className="h-24 text-center text-muted-foreground"
                  >
                    {emptyMessage}
                  </TableCell>
                </TableRow>
              )
              : data.map((item, i) => {
                const rowId = selection ? selection.getRowId(item) : "";
                const isSelected = selection ? selection.selectedIds.has(rowId) : false;
                return (
                  <TableRow
                    key={selection ? rowId : i}
                    className={onRowClick ? "cursor-pointer hover:bg-muted/50" : ""}
                    onClick={() => onRowClick?.(item)}
                    data-state={isSelected ? "selected" : undefined}
                  >
                    {selection && (
                      <TableCell
                        onClick={(e) => e.stopPropagation()}
                        className="w-10"
                      >
                        <Checkbox
                          checked={isSelected}
                          onCheckedChange={() => selection.onToggleRow(rowId, item)}
                          aria-label="Select row"
                        />
                      </TableCell>
                    )}
                    {columns.map((col) => (
                      <TableCell key={col.key} className={col.className}>
                        {col.render(item)}
                      </TableCell>
                    ))}
                  </TableRow>
                );
              })}
        </TableBody>
      </Table>
    </div>
  );
}
