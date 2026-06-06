import { useEffect, useMemo, useState } from "react";
import { NavLink, useLocation } from "react-router-dom";
import {
  Activity,
  BarChart3,
  Bell,
  Building2,
  Calendar,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ClipboardList,
  Clock,
  Coins,
  Database,
  FlaskConical,
  Gauge,
  LayoutDashboard,
  FileText,
  Megaphone,
  MessageSquare,
  MessagesSquare,
  Settings,
  ShieldAlert,
  Sparkles,
  Trophy,
  UserPlus,
  Users,
  Users2,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/hooks/use-auth";
import { AdminRole } from "@/types/enums";
import { Button } from "@/components/ui/button";

interface SidebarProps {
  collapsed: boolean;
  onToggle: () => void;
}

interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
  requiresRole?: AdminRole;
}

interface NavSection {
  id: string;
  label: string;
  icon: LucideIcon;
  items: NavItem[];
}

const SECTIONS: NavSection[] = [
  {
    id: "monitoring",
    label: "Monitoring",
    icon: Activity,
    items: [
      {
        to: "/tenant-dashboard",
        label: "Tenant Dashboard",
        icon: LayoutDashboard,
        requiresRole: AdminRole.SUPER_ADMIN,
      },
      { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
      { to: "/bookings", label: "Calendar", icon: Calendar },
      { to: "/announcements", label: "Announcements", icon: Megaphone },
      { to: "/campaigns", label: "Musters", icon: Users2 },
      { to: "/reminders", label: "Reminders", icon: Bell },
      { to: "/conversations", label: "Conversations", icon: MessageSquare },
      { to: "/suspensions", label: "Suspensions", icon: ShieldAlert },
      { to: "/candidates", label: "Walk-up candidates", icon: UserPlus },
      { to: "/analytics", label: "Analytics", icon: BarChart3 },
      { to: "/observability", label: "Observability", icon: Gauge },
    ],
  },
  {
    id: "data-setup",
    label: "Data Setup",
    icon: Database,
    items: [
      { to: "/customers", label: "Volunteers", icon: Users },
      { to: "/appointment-types", label: "Service Types", icon: ClipboardList },
      { to: "/availability", label: "Schedule Setup", icon: Clock },
    ],
  },
  {
    id: "test-tools",
    label: "Test Tools",
    icon: FlaskConical,
    items: [
      { to: "/test-tool", label: "SMS Test", icon: FlaskConical },
      {
        to: "/multi-test",
        label: "Multi-Volunteer Test",
        icon: MessagesSquare,
      },
    ],
  },
  {
    id: "settings",
    label: "Settings",
    icon: Settings,
    items: [
      {
        to: "/settings",
        label: "Settings",
        icon: Settings,
        requiresRole: AdminRole.OWNER,
      },
      {
        to: "/ai-prompts",
        label: "AI Prompts",
        icon: Sparkles,
        requiresRole: AdminRole.OWNER,
      },
      {
        to: "/templates",
        label: "Templates",
        icon: FileText,
        requiresRole: AdminRole.OWNER,
      },
      {
        to: "/recognition",
        label: "Recognition",
        icon: Trophy,
        requiresRole: AdminRole.OWNER,
      },
      { to: "/token-usage", label: "Token Usage", icon: Coins },
      {
        to: "/tenants",
        label: "Tenants",
        icon: Building2,
        requiresRole: AdminRole.SUPER_ADMIN,
      },
    ],
  },
];

const STORAGE_KEY_OPEN_SECTIONS = "sidebar-open-sections";

function loadOpenSections(): Set<string> {
  try {
    const raw = localStorage.getItem(STORAGE_KEY_OPEN_SECTIONS);
    if (raw) {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed)) {
        return new Set(parsed.filter((s): s is string => typeof s === "string"));
      }
    }
  } catch {
    // ignore
  }
  // Default: all sections expanded on first visit
  return new Set(SECTIONS.map((s) => s.id));
}

function itemLink(
  item: NavItem,
  collapsed: boolean,
  indent: boolean
): JSX.Element {
  return (
    <NavLink
      key={item.to}
      to={item.to}
      className={({ isActive }) =>
        cn(
          "flex items-center gap-3 rounded-md py-2 text-sm font-medium transition-colors",
          collapsed ? "justify-center px-2" : indent ? "pl-7 pr-3" : "px-3",
          isActive
            ? "bg-primary text-primary-foreground"
            : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
        )
      }
      title={collapsed ? item.label : undefined}
    >
      <item.icon className="h-4 w-4 shrink-0" />
      {!collapsed && <span className="truncate">{item.label}</span>}
    </NavLink>
  );
}

export function Sidebar({ collapsed, onToggle }: SidebarProps) {
  const { hasRole, user } = useAuth();
  const location = useLocation();

  const [openSections, setOpenSections] = useState<Set<string>>(() =>
    loadOpenSections()
  );

  useEffect(() => {
    try {
      localStorage.setItem(
        STORAGE_KEY_OPEN_SECTIONS,
        JSON.stringify([...openSections])
      );
    } catch {
      // ignore quota / privacy errors
    }
  }, [openSections]);

  // Filter sections + items based on role; drop empty sections entirely.
  const visibleSections = useMemo<NavSection[]>(() => {
    return SECTIONS.map((section) => ({
      ...section,
      items: section.items.filter((i) =>
        !i.requiresRole || hasRole(i.requiresRole)
      ),
    })).filter((s) => s.items.length > 0);
  }, [hasRole]);

  // When the route changes, auto-expand the section that contains it so the
  // active item is visible without forcing the user to expand manually.
  useEffect(() => {
    const containing = visibleSections.find((s) =>
      s.items.some((i) => location.pathname.startsWith(i.to))
    );
    if (containing && !openSections.has(containing.id)) {
      setOpenSections((prev) => new Set(prev).add(containing.id));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.pathname]);

  function toggleSection(id: string) {
    setOpenSections((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  return (
    <aside
      className={cn(
        "flex h-screen flex-col border-r border-border bg-card transition-all duration-200",
        collapsed ? "w-16" : "w-60"
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
          title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? (
            <ChevronRight className="h-4 w-4" />
          ) : (
            <ChevronLeft className="h-4 w-4" />
          )}
        </Button>
      </div>

      <nav className="flex-1 space-y-3 p-2 overflow-y-auto">
        {visibleSections.map((section) => {
          const isOpen = openSections.has(section.id);
          // When the sidebar itself is icon-collapsed, hide section headers
          // and render items as a flat icon list — there's no room for a
          // hierarchy and tooltips already disambiguate.
          if (collapsed) {
            return (
              <div key={section.id} className="space-y-1">
                {section.items.map((item) => itemLink(item, true, false))}
              </div>
            );
          }
          return (
            <div key={section.id} className="space-y-1">
              <button
                type="button"
                onClick={() => toggleSection(section.id)}
                className={cn(
                  "flex w-full items-center gap-2 rounded-md px-3 py-1.5",
                  "text-xs font-semibold uppercase tracking-wide",
                  "text-muted-foreground hover:bg-accent hover:text-foreground",
                  "transition-colors"
                )}
              >
                <section.icon className="h-3.5 w-3.5 shrink-0" />
                <span className="flex-1 text-left">{section.label}</span>
                {isOpen ? (
                  <ChevronDown className="h-3.5 w-3.5 shrink-0" />
                ) : (
                  <ChevronRight className="h-3.5 w-3.5 shrink-0" />
                )}
              </button>
              {isOpen && (
                <div className="space-y-1">
                  {section.items.map((item) => itemLink(item, false, true))}
                </div>
              )}
            </div>
          );
        })}
      </nav>
    </aside>
  );
}
