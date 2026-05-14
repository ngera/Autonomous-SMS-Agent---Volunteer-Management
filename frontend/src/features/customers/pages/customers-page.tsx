import { useMemo, useState } from "react";
import { Download, Upload, Plus } from "lucide-react";
import { Pagination } from "@/components/shared/pagination";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/hooks/use-auth";
import { AdminRole, AvailabilitySlot, ContactStatus, ConsentStatus } from "@/types/enums";
import { useTenantFilter } from "@/context/tenant-filter-context";
import { useTenants } from "@/features/tenants/hooks/use-tenants";
import { CustomersTable } from "../components/customers-table";
import { CsvImportDialog } from "../components/csv-import-dialog";
import { CustomerForm, type CustomerFormData } from "../components/customer-form";
import { VolunteerFilterCard } from "../components/volunteer-filter-card";
import {
  useCustomers,
  useMultiTenantCustomers,
  useCreateCustomer,
} from "../hooks/use-customers";
import {
  useAppointmentTypes,
  useMultiTenantAppointmentTypes,
} from "@/features/appointment-types/hooks/use-appointment-types";
import { listCustomers } from "../api";
import { customersToCsv, downloadCsv } from "../lib/csv";
import type { CustomerResponse, CustomerWithTenant } from "@/types/api";

export function CustomersPage() {
  const { hasRole } = useAuth();
  const canEdit = hasRole(AdminRole.MANAGER);
  const { selectedTenantIds, isSuperAdmin } = useTenantFilter();
  const { data: tenantsData } = useTenants();
  const tenants = tenantsData?.items ?? [];

  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<ContactStatus | undefined>();
  const [consentFilter, setConsentFilter] = useState<ConsentStatus | undefined>();
  const [bgCheckFilter, setBgCheckFilter] = useState<boolean | undefined>();
  const [availabilityFilter, setAvailabilityFilter] = useState<AvailabilitySlot | undefined>();
  const [showImport, setShowImport] = useState(false);
  const [showCreate, setShowCreate] = useState(false);

  const isMultiTenant = isSuperAdmin && selectedTenantIds.length !== 1;
  const tenantIdsToQuery = isMultiTenant
    ? selectedTenantIds.length > 0
      ? selectedTenantIds
      : tenants.map((t) => t.id)
    : [];

  const filters = {
    page,
    page_size: 20,
    search: search || undefined,
    status: statusFilter,
    consent_status: consentFilter,
    background_check_required: bgCheckFilter,
    availability: availabilityFilter,
  };

  const singleTenantResult = useCustomers(filters);
  const multiTenantResult = useMultiTenantCustomers(
    tenantIdsToQuery,
    tenants,
    { page: 1, page_size: 100, search: search || undefined }
  );

  const createCustomer = useCreateCustomer();

  // Build a service-name lookup that works in both single and multi-tenant modes.
  const { data: singleTenantTypes } = useAppointmentTypes();
  const visibleTenantIds = useMemo(() => {
    if (!isMultiTenant) return [];
    const set = new Set<string>();
    for (const c of multiTenantResult.data) {
      if (c.tenant_id) set.add(c.tenant_id);
    }
    return Array.from(set);
  }, [isMultiTenant, multiTenantResult.data]);
  const { data: multiTenantTypes } = useMultiTenantAppointmentTypes(visibleTenantIds);
  const typeMap = useMemo(() => {
    const map: Record<string, string> = {};
    for (const t of singleTenantTypes ?? []) map[t.id] = t.name;
    for (const t of multiTenantTypes ?? []) map[t.id] = t.name;
    return map;
  }, [singleTenantTypes, multiTenantTypes]);

  const [exporting, setExporting] = useState(false);

  async function handleExport() {
    if (exporting) return;
    setExporting(true);
    try {
      let rows: (CustomerResponse | CustomerWithTenant)[];
      if (isMultiTenant) {
        // Multi-tenant view already has all loaded rows (one fetch per tenant
        // with page_size=100). Use what's in memory.
        rows = multiTenantResult.data;
      } else {
        // Single-tenant: page through the filtered results so the export
        // matches what the user sees with their filters applied.
        const pages: CustomerResponse[] = [];
        let p = 1;
        while (true) {
          const result = await listCustomers({
            ...filters,
            page: p,
            page_size: 100,
          });
          pages.push(...result.items);
          if (result.items.length < 100 || pages.length >= result.total) break;
          p++;
          if (p > 200) break; // safety: never loop more than 20 000 rows
        }
        rows = pages;
      }
      if (rows.length === 0) {
        alert("No volunteers to export.");
        return;
      }
      const csv = customersToCsv(rows, {
        typeMap,
        includeTenant: isMultiTenant,
      });
      const stamp = new Date().toISOString().slice(0, 10);
      downloadCsv(`volunteers-${stamp}.csv`, csv);
    } catch (err) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail || (err as Error)?.message || "Export failed";
      alert(`Could not export volunteers: ${detail}`);
    } finally {
      setExporting(false);
    }
  }

  const tableData = isMultiTenant
    ? multiTenantResult.data
    : singleTenantResult.data?.items ?? [];
  const tableLoading = isMultiTenant
    ? multiTenantResult.isLoading
    : singleTenantResult.isLoading;

  const filteredTotal = singleTenantResult.data?.total ?? 0;
  const unfilteredTotal = singleTenantResult.data?.total_unfiltered ?? 0;
  const isFiltered =
    !!search ||
    !!statusFilter ||
    !!consentFilter ||
    bgCheckFilter === true ||
    !!availabilityFilter;

  function resetPage() {
    setPage(1);
  }

  function handleCreate(data: CustomerFormData) {
    createCustomer.mutate(data, {
      onSuccess: () => setShowCreate(false),
      onError: (error: unknown) => {
        const msg =
          (error as { response?: { data?: { detail?: string } } })?.response
            ?.data?.detail || "Failed to create volunteer";
        alert(msg);
      },
    });
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Volunteers</h2>
          {!isMultiTenant && (
            <p className="mt-1 text-sm text-muted-foreground">
              {unfilteredTotal} total
              {isFiltered && (
                <>
                  {" · "}
                  <span className="text-emerald-700 dark:text-emerald-300">
                    {filteredTotal} matching filter{filteredTotal === 1 ? "" : "s"}
                  </span>
                </>
              )}
            </p>
          )}
        </div>
        {canEdit && (
          <div className="flex gap-2">
            <Button
              variant="outline"
              onClick={handleExport}
              disabled={exporting || tableLoading}
            >
              <Download className="mr-2 h-4 w-4" />
              {exporting ? "Exporting..." : "Export CSV"}
            </Button>
            <Button variant="outline" onClick={() => setShowImport(true)}>
              <Upload className="mr-2 h-4 w-4" />
              Import CSV
            </Button>
            <Button onClick={() => setShowCreate(true)}>
              <Plus className="mr-2 h-4 w-4" />
              Add volunteer
            </Button>
          </div>
        )}
      </div>

      {!isMultiTenant && (
        <VolunteerFilterCard
          search={search}
          onSearchChange={(v) => {
            setSearch(v);
            resetPage();
          }}
          status={statusFilter}
          onStatusChange={(s) => {
            setStatusFilter(s);
            resetPage();
          }}
          consent={consentFilter}
          onConsentChange={(c) => {
            setConsentFilter(c);
            resetPage();
          }}
          bgCheckRequired={bgCheckFilter}
          onBgCheckChange={(v) => {
            setBgCheckFilter(v);
            resetPage();
          }}
          availability={availabilityFilter}
          onAvailabilityChange={(v) => {
            setAvailabilityFilter(v);
            resetPage();
          }}
        />
      )}

      <CustomersTable
        data={tableData}
        isLoading={tableLoading}
        showTenantColumn={isMultiTenant}
      />

      {!isMultiTenant && singleTenantResult.data && (
        <div className="flex flex-wrap items-center justify-between gap-3 text-sm text-muted-foreground">
          <span>
            Showing {(page - 1) * 20 + 1}–
            {Math.min(page * 20, filteredTotal)} of {filteredTotal}
            {isFiltered ? " matches" : ""}
          </span>
          <Pagination
            page={page}
            pageSize={20}
            total={filteredTotal}
            onPageChange={setPage}
          />
        </div>
      )}

      <CsvImportDialog open={showImport} onOpenChange={setShowImport} />
      <CustomerForm
        open={showCreate}
        onOpenChange={setShowCreate}
        onSubmit={handleCreate}
        isLoading={createCustomer.isPending}
      />
    </div>
  );
}
