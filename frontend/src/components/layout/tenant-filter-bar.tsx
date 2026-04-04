import { X, Building2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useTenantFilter } from "@/context/tenant-filter-context";
import { useTenants } from "@/features/tenants/hooks/use-tenants";

export function TenantFilterBar() {
  const { selectedTenantIds, setSelectedTenantIds, isSuperAdmin } =
    useTenantFilter();
  const { data } = useTenants();

  if (!isSuperAdmin) return null;

  const tenants = data?.items || [];

  const toggleTenant = (id: string) => {
    if (selectedTenantIds.includes(id)) {
      setSelectedTenantIds(selectedTenantIds.filter((t) => t !== id));
    } else {
      setSelectedTenantIds([...selectedTenantIds, id]);
    }
  };

  const selectedNames = tenants
    .filter((t) => selectedTenantIds.includes(t.id))
    .map((t) => t.name);

  return (
    <div className="flex items-center gap-2">
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="outline" size="sm" className="gap-2">
            <Building2 className="h-4 w-4" />
            {selectedTenantIds.length === 0
              ? "All Tenants"
              : `${selectedTenantIds.length} Tenant${selectedTenantIds.length > 1 ? "s" : ""}`}
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start" className="w-56">
          {tenants.map((tenant) => (
            <DropdownMenuCheckboxItem
              key={tenant.id}
              checked={selectedTenantIds.includes(tenant.id)}
              onCheckedChange={() => toggleTenant(tenant.id)}
            >
              {tenant.name}
            </DropdownMenuCheckboxItem>
          ))}
          {tenants.length === 0 && (
            <div className="px-2 py-1.5 text-sm text-muted-foreground">
              No tenants
            </div>
          )}
        </DropdownMenuContent>
      </DropdownMenu>

      {selectedNames.map((name) => (
        <Badge key={name} variant="secondary" className="gap-1">
          {name}
          <X
            className="h-3 w-3 cursor-pointer"
            onClick={() => {
              const tenant = tenants.find((t) => t.name === name);
              if (tenant) toggleTenant(tenant.id);
            }}
          />
        </Badge>
      ))}

      {selectedTenantIds.length > 0 && (
        <Button
          variant="ghost"
          size="sm"
          className="text-xs text-muted-foreground"
          onClick={() => setSelectedTenantIds([])}
        >
          Clear
        </Button>
      )}
    </div>
  );
}
