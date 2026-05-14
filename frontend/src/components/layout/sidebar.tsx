import { NavLink } from "react-router-dom";
import {
  LayoutDashboard,
  Calendar,
  Users,
  ClipboardList,
  Clock,
  Bell,
  MessageSquare,
  ShieldAlert,
  BarChart3,
  Settings,
  Building2,
  Megaphone,
  FlaskConical,
  MessagesSquare,
  Coins,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/hooks/use-auth";
import { AdminRole } from "@/types/enums";
import { Button } from "@/components/ui/button";

interface SidebarProps {
  collapsed: boolean;
  onToggle: () => void;
}

const navItems = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { to: "/bookings", label: "Calendar", icon: Calendar },
  { to: "/customers", label: "Volunteers", icon: Users },
  { to: "/appointment-types", label: "Types", icon: ClipboardList },
  { to: "/availability", label: "Schedule Setup", icon: Clock },
  { to: "/reminders", label: "Reminders", icon: Bell },
  { to: "/conversations", label: "Conversations", icon: MessageSquare },
  { to: "/suspensions", label: "Suspensions", icon: ShieldAlert },
  { to: "/analytics", label: "Analytics", icon: BarChart3 },
  { to: "/token-usage", label: "Token Usage", icon: Coins },
  { to: "/announcements", label: "Announcements", icon: Megaphone },
  { to: "/test-tool", label: "SMS Test", icon: FlaskConical },
  { to: "/multi-test", label: "Multi-Volunteer Test", icon: MessagesSquare },
];

export function Sidebar({ collapsed, onToggle }: SidebarProps) {
  const { hasRole, user } = useAuth();

  return (
    <aside
      className={cn(
        "flex h-screen flex-col border-r border-border bg-card transition-all duration-200",
        collapsed ? "w-16" : "w-56"
      )}
    >
      <div className="flex h-14 items-center justify-between border-b border-border px-3">
        {!collapsed && (
          <span className="text-sm font-semibold truncate">
            {user?.tenant_name || "Booking System"}
          </span>
        )}
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8 shrink-0"
          onClick={onToggle}
        >
          {collapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
        </Button>
      </div>

      <nav className="flex-1 space-y-1 p-2 overflow-y-auto">
        {hasRole(AdminRole.SUPER_ADMIN) && (
          <NavLink
            to="/tenant-dashboard"
            className={({ isActive }) =>
              cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                isActive
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
                collapsed && "justify-center px-2"
              )
            }
          >
            <LayoutDashboard className="h-4 w-4 shrink-0" />
            {!collapsed && <span>Tenant Dashboard</span>}
          </NavLink>
        )}

        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                isActive
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
                collapsed && "justify-center px-2"
              )
            }
          >
            <item.icon className="h-4 w-4 shrink-0" />
            {!collapsed && <span className="truncate">{item.label}</span>}
          </NavLink>
        ))}

        {hasRole(AdminRole.OWNER) && (
          <NavLink
            to="/settings"
            className={({ isActive }) =>
              cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                isActive
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
                collapsed && "justify-center px-2"
              )
            }
          >
            <Settings className="h-4 w-4 shrink-0" />
            {!collapsed && <span>Settings</span>}
          </NavLink>
        )}

        {hasRole(AdminRole.SUPER_ADMIN) && (
          <NavLink
            to="/tenants"
            className={({ isActive }) =>
              cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                isActive
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
                collapsed && "justify-center px-2"
              )
            }
          >
            <Building2 className="h-4 w-4 shrink-0" />
            {!collapsed && <span>Tenants</span>}
          </NavLink>
        )}
      </nav>
    </aside>
  );
}
