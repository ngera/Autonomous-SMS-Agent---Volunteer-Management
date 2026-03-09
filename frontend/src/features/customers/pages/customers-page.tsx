import { useState } from "react";
import { Upload } from "lucide-react";
import { PageHeader } from "@/components/shared/page-header";
import { Pagination } from "@/components/shared/pagination";
import { SearchInput } from "@/components/shared/search-input";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/hooks/use-auth";
import { AdminRole } from "@/types/enums";
import { CustomersTable } from "../components/customers-table";
import { CsvImportDialog } from "../components/csv-import-dialog";
import { useCustomers } from "../hooks/use-customers";

export function CustomersPage() {
  const { hasRole } = useAuth();
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [showImport, setShowImport] = useState(false);

  const customers = useCustomers({
    page,
    page_size: 20,
    search: search || undefined,
  });

  return (
    <div>
      <PageHeader
        title="Customers"
        description="View and manage customer contacts."
        actions={
          hasRole(AdminRole.MANAGER) ? (
            <Button variant="outline" onClick={() => setShowImport(true)}>
              <Upload className="mr-2 h-4 w-4" />
              Import CSV
            </Button>
          ) : undefined
        }
      />

      <div className="mb-4 max-w-sm">
        <SearchInput
          value={search}
          onChange={(v) => {
            setSearch(v);
            setPage(1);
          }}
          placeholder="Search by phone, name, or email..."
        />
      </div>

      <CustomersTable
        data={customers.data?.items ?? []}
        isLoading={customers.isLoading}
      />

      {customers.data && (
        <Pagination
          page={page}
          pageSize={20}
          total={customers.data.total}
          onPageChange={setPage}
        />
      )}

      <CsvImportDialog open={showImport} onOpenChange={setShowImport} />
    </div>
  );
}
