import { useState } from "react";
import { Outlet, useLocation } from "react-router-dom";
import { Sidebar } from "./sidebar";
import { Header } from "./header";
import { TenantFilterProvider } from "@/context/tenant-filter-context";

const PAGE_TITLES: Record<string, string> = {
  "/dashboard": "Dashboard",
  "/tenant-dashboard": "Tenant Dashboard",
  "/bookings": "Bookings",
  "/customers": "Volunteers",
  "/appointment-types": "Service Types",
  "/availability": "Schedule Setup",
  "/reminders": "Reminders",
  "/conversations": "Conversations",
  "/suspensions": "Suspensions",
  "/analytics": "Analytics",
  "/settings": "Settings",
  "/announcements": "Announcements",
  "/test-tool": "SMS Test Tool",
  "/tenants": "Tenants",
};

function getPageTitle(pathname: string): string {
  // Check exact match first
  if (PAGE_TITLES[pathname]) return PAGE_TITLES[pathname];
  // Check prefix match for detail pages
  for (const [path, title] of Object.entries(PAGE_TITLES)) {
    if (pathname.startsWith(path)) return title;
  }
  return "Booking System";
}

export function AppLayout() {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const location = useLocation();
  const title = getPageTitle(location.pathname);

  return (
    <TenantFilterProvider>
      <div className="flex h-screen overflow-hidden">
        <Sidebar
          collapsed={sidebarCollapsed}
          onToggle={() => setSidebarCollapsed(!sidebarCollapsed)}
        />
        <div className="flex flex-1 flex-col overflow-hidden">
          <Header title={title} />
          <main className="flex-1 overflow-y-auto p-6">
            <Outlet />
          </main>
        </div>
      </div>
    </TenantFilterProvider>
  );
}
