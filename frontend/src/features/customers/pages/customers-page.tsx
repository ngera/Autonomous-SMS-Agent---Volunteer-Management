import { useState } from "react";
import { Upload, Plus } from "lucide-react";
import { PageHeader } from "@/components/shared/page-header";
import { Pagination } from "@/components/shared/pagination";
import { SearchInput } from "@/components/shared/search-input";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/hooks/use-auth";
import { AdminRole } from "@/types/enums";
import { useTenantFilter } from "@/context/tenant-filter-context";
import { useTenants } from "@/features/tenants/hooks/use-tenants";
import { CustomersTable } from "../components/customers-table";
import { CsvImportDialog } from "../components/csv-import-dialog";
import { CustomerForm, type CustomerFormData } from "../components/customer-form";
import {
  useCustomers,
  useMultiTenantCustomers,
  useCreateCustomer,
  useCreateCustomerForTenant,
} from "../hooks/use-customers";

export function CustomersPage() {
  const { hasRole } = useAuth();
  const { selectedTenantIds, isSuperAdmin } = useTenantFilter();
  const { data: tenantsData } = useTenants();
  const tenants = tenantsData?.items ?? [];

  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [showImport, setShowImport] = useState(false);
  const [showCreate, setShowCreate] = useState(false);

  // Determine if multi-tenant view (super admin with 0 or 2+ tenants selected)
  const isMultiTenant = isSuperAdmin && selectedTenantIds.length !== 1;
  const tenantIdsToQuery = isMultiTenant
    ? selectedTenantIds.length > 0
      ? selectedTenantIds
      : tenants.map((t) => t.id)
    : [];

  // Single-tenant query (regular users or super admin with 1 tenant)
  const singleTenantResult = useCustomers({
    page,
    page_size: 20,
    search: search || undefined,
  });

  // Multi-tenant query (super admin with 0 or 2+ tenants)
  const multiTenantResult = useMultiTenantCustomers(
    tenantIdsToQuery,
    tenants,
    { page: 1, page_size: 100, search: search || undefined }
  );

  const createCustomer = useCreateCustomer();
  const createCustomerForTenant = useCreateCustomerForTenant();

  const tableData = isMultiTenant
    ? multiTenantResult.data
    : singleTenantResult.data?.items ?? [];
  const tableLoading = isMultiTenant
    ? multiTenantResult.isLoading
    : singleTenantResult.isLoading;

  function handleCreate(data: CustomerFormData) {
    const { tenantId, ...body } = data;

    if (isSuperAdmin && tenantId) {
      createCustomerForTenant.mutate(
        { tenantId, body },
        {
          onSuccess: () => setShowCreate(false),
          onError: (error: unknown) => {
            const msg =
              (error as { response?: { data?: { detail?: string } } })
                ?.response?.data?.detail || "Failed to create customer";
            alert(msg);
          },
        }
      );
    } else {
      createCustomer.mutate(body, {
        onSuccess: () => setShowCreate(false),
        onError: (error: unknown) => {
          const msg =
            (error as { response?: { data?: { detail?: string } } })?.response
              ?.data?.detail || "Failed to create customer";
          alert(msg);
        },
      });
    }
  }

  const isSaving =
    createCustomer.isPending || createCustomerForTenant.isPending;

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
        data={tableData}
        isLoading={tableLoading}
        showTenantColumn={isMultiTenant}
      />

      {!isMultiTenant && singleTenantResult.data && (
        <Pagination
          page={page}
          pageSize={20}
          total={singleTenantResult.data.total}
          onPageChange={setPage}
        />
      )}

      <CsvImportDialog open={showImport} onOpenChange={setShowImport} />

      <CustomerForm
        open={showCreate}
        onOpenChange={setShowCreate}
        onSubmit={handleCreate}
        isLoading={isSaving}
        tenants={isSuperAdmin ? tenants : undefined}
        requireTenant={isSuperAdmin}
      />
    </div>
  );
}
