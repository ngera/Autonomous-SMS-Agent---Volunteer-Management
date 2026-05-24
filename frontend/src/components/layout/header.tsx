import { LogOut, Moon, Sun, User } from "lucide-react";
import { useAuth } from "@/hooks/use-auth";
import { useTheme } from "@/hooks/use-theme";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { ADMIN_ROLE_LABELS } from "@/lib/constants";
import { Badge } from "@/components/ui/badge";
import { NotificationPanel } from "@/features/dashboard/components/notification-panel";
import { TenantFilterBar } from "./tenant-filter-bar";

interface HeaderProps {
  title: string;
}

export function Header({ title }: HeaderProps) {
  const { user, logout } = useAuth();
  const { mode, toggle } = useTheme();

  return (
    <header className="flex h-14 items-center justify-between border-b border-border bg-card px-6">
      <div className="flex items-center gap-4">
        <h1 className="text-lg font-semibold">{title}</h1>
        <TenantFilterBar />
      </div>

      <div className="flex items-center gap-3">
        <Button
          variant="ghost"
          size="icon-sm"
          onClick={toggle}
          aria-label={mode === "dark" ? "Switch to light theme" : "Switch to dark theme"}
          title={mode === "dark" ? "Switch to light theme" : "Switch to dark theme"}
        >
          {mode === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
        </Button>

        <NotificationPanel />

        {user?.role && (
          <Badge variant="secondary" className="text-xs">
            {ADMIN_ROLE_LABELS[user.role] ?? user.role}
          </Badge>
        )}

        <DropdownMenu>
          <DropdownMenuTrigger
            render={
              <Button variant="ghost" size="sm" className="gap-2">
                <User className="h-4 w-4" />
                <span className="hidden sm:inline">{user?.email}</span>
              </Button>
            }
          />
          <DropdownMenuContent align="end" className="w-48">
            <DropdownMenuLabel className="space-y-1">
              <div className="text-sm">{user?.email}</div>
              {user?.tenant_name && (
                <div className="text-xs font-normal text-muted-foreground">
                  {user.tenant_name}
                </div>
              )}
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={() => void logout()}>
              <LogOut className="mr-2 h-4 w-4" />
              Sign out
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => void logout()}
          className="text-muted-foreground"
        >
          <LogOut className="mr-1 h-4 w-4" />
          <span className="hidden sm:inline">Logout</span>
        </Button>
      </div>
    </header>
  );
}
