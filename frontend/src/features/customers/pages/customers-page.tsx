import { useState } from "react";
import { Upload, Plus } from "lucide-react";
import { PageHeader } from "@/components/shared/page-header";
import { Pagination } from "@/components/shared/pagination";
import { SearchInput } from "@/components/shared/search-input";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/hooks/use-auth";
import { AdminRole } from "@/types/enums";
import { CustomersTable } from "../components/customers-table";
import { CsvImportDialog } from "../components/csv-import-dialog";
import { CustomerForm } from "../components/customer-form";
import { useCustomers, useCreateCustomer } from "../hooks/use-customers";

export function CustomersPage() {
  const { hasRole } = useAuth();
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [showImport, setShowImport] = useState(false);
  const [showCreate, setShowCreate] = useState(false);

  const customers = useCustomers({
    page,
    page_size: 20,
    search: search || undefined,
  });

  const createCustomer = useCreateCustomer();

  return (
    <div>
      <PageHeader
        title="Customers"
        description="View and manage customer contacts."
        actions={
          hasRole(AdminRole.MANAGER) ? (
            <div className="flex gap-2">
              <Button onClick={() => setShowCreate(true)}>
                <Plus className="mr-2 h-4 w-4" />
                New Customer
              </Button>
              <Button variant="outline" onClick={() => setShowImport(true)}>
                <Upload className="mr-2 h-4 w-4" />
                Import CSV
              </Button>
            </div>
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

      <CustomerForm
        open={showCreate}
        onOpenChange={setShowCreate}
        onSubmit={(data) => {
          createCustomer.mutate(data, {
            onSuccess: () => setShowCreate(false),
          });
        }}
        isLoading={createCustomer.isPending}
      />
    </div>
  );
}
