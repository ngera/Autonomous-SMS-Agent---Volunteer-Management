import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { useAuth } from "@/hooks/use-auth";
import { AdminRole } from "@/types/enums";

interface TenantFilterContextType {
  selectedTenantIds: string[];
  setSelectedTenantIds: (ids: string[]) => void;
  isFiltered: boolean;
  isSuperAdmin: boolean;
}

const TenantFilterContext = createContext<TenantFilterContextType | null>(null);

export function TenantFilterProvider({ children }: { children: ReactNode }) {
  const { user, hasRole } = useAuth();
  const isSuperAdmin = !!user && hasRole(AdminRole.SUPER_ADMIN);
  const [selectedTenantIds, setSelectedTenantIdsState] = useState<string[]>([]);

  const setSelectedTenantIds = useCallback((ids: string[]) => {
    setSelectedTenantIdsState(ids);
  }, []);

  // Single source of truth for sessionStorage("active_tenant_id").
  // When exactly 1 tenant is selected, set it; otherwise clear it.
  useEffect(() => {
    if (!isSuperAdmin) return;

    if (selectedTenantIds.length === 1) {
      sessionStorage.setItem("active_tenant_id", selectedTenantIds[0]);
    } else {
      sessionStorage.removeItem("active_tenant_id");
    }
  }, [selectedTenantIds, isSuperAdmin]);

  const value = useMemo(
    () => ({
      selectedTenantIds,
      setSelectedTenantIds,
      isFiltered: selectedTenantIds.length > 0,
      isSuperAdmin,
    }),
    [selectedTenantIds, setSelectedTenantIds, isSuperAdmin]
  );

  return (
    <TenantFilterContext.Provider value={value}>
      {children}
    </TenantFilterContext.Provider>
  );
}

export function useTenantFilter() {
  const context = useContext(TenantFilterContext);
  if (!context) {
    throw new Error("useTenantFilter must be used within a TenantFilterProvider");
  }
  return context;
}
