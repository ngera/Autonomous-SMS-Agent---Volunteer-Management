import { useTenantFilter } from "@/context/tenant-filter-context";

/**
 * Returns the currently active tenant ID for use in query keys.
 * When exactly one tenant is selected in the filter, returns its ID.
 * Otherwise returns "none" — hooks should use `enabled: tenantId !== "none"`
 * to prevent API calls without tenant context.
 */
export function useActiveTenantId() {
  const { selectedTenantIds, isSuperAdmin } = useTenantFilter();
  if (!isSuperAdmin) {
    // Non-super-admin users always have a tenant from their user record,
    // so return a stable key (their requests always include their own tenant).
    return "self";
  }
  return selectedTenantIds.length === 1 ? selectedTenantIds[0] : "none";
}
