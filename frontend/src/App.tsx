import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { ProtectedRoute } from "@/components/guards/protected-route";
import { RoleGate } from "@/components/guards/role-gate";
import { AppLayout } from "@/components/layout/app-layout";
import { LoginPage } from "@/pages/login-page";
import { DashboardPage } from "@/features/dashboard/pages/dashboard-page";
import { TenantDashboardPage } from "@/features/tenants/pages/tenant-dashboard-page";
import { BookingsPage } from "@/features/bookings/pages/bookings-page";
import { BookingDetailPage } from "@/features/bookings/pages/booking-detail-page";
import { BookingCreatePage } from "@/features/bookings/pages/booking-create-page";
import { CustomersPage } from "@/features/customers/pages/customers-page";
import { CustomerDetailPage } from "@/features/customers/pages/customer-detail-page";
import { AppointmentTypesPage } from "@/features/appointment-types/pages/appointment-types-page";
import { AvailabilityPage } from "@/features/availability/pages/availability-page";
import { RemindersPage } from "@/features/reminders/pages/reminders-page";
import { ConversationsPage } from "@/features/conversations/pages/conversations-page";
import { SuspensionsPage } from "@/features/suspensions/pages/suspensions-page";
import { AnalyticsPage } from "@/features/analytics/pages/analytics-page";
import { TokenUsagePage } from "@/features/token-usage/pages/token-usage-page";
import { SettingsPage } from "@/features/settings/pages/settings-page";
import AnnouncementsPage from "@/features/announcements/pages/announcements-page";
import { TestToolPage } from "@/features/test-tool/pages/test-tool-page";
import { TenantsPage } from "@/features/tenants/pages/tenants-page";
import { TenantDetailPage } from "@/features/tenants/pages/tenant-detail-page";
import { AdminRole } from "@/types/enums";
import { useAuth } from "@/hooks/use-auth";
import { ROLE_HIERARCHY } from "@/lib/constants";

function DefaultRedirect() {
  const { user } = useAuth();
  const isSuperAdmin =
    user && ROLE_HIERARCHY[user.role] >= ROLE_HIERARCHY[AdminRole.SUPER_ADMIN];
  return <Navigate to={isSuperAdmin ? "/tenant-dashboard" : "/dashboard"} replace />;
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />

        <Route element={<ProtectedRoute />}>
          <Route element={<AppLayout />}>
            <Route path="/" element={<DefaultRedirect />} />
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route
              path="/tenant-dashboard"
              element={
                <RoleGate minimum={AdminRole.SUPER_ADMIN}>
                  <TenantDashboardPage />
                </RoleGate>
              }
            />
            <Route path="/bookings" element={<BookingsPage />} />
            <Route path="/bookings/new" element={<BookingCreatePage />} />
            <Route path="/bookings/:id" element={<BookingDetailPage />} />
            <Route path="/customers" element={<CustomersPage />} />
            <Route path="/customers/:phone" element={<CustomerDetailPage />} />
            <Route path="/appointment-types" element={<AppointmentTypesPage />} />
            <Route path="/availability" element={<AvailabilityPage />} />
            <Route path="/reminders" element={<RemindersPage />} />
            <Route path="/conversations" element={<ConversationsPage />} />
            <Route path="/suspensions" element={<SuspensionsPage />} />
            <Route path="/analytics" element={<AnalyticsPage />} />
            <Route
              path="/token-usage"
              element={
                <RoleGate minimum={AdminRole.MANAGER}>
                  <TokenUsagePage />
                </RoleGate>
              }
            />
            <Route
              path="/announcements"
              element={
                <RoleGate minimum={AdminRole.MANAGER}>
                  <AnnouncementsPage />
                </RoleGate>
              }
            />
            <Route
              path="/test-tool"
              element={
                <RoleGate minimum={AdminRole.MANAGER}>
                  <TestToolPage />
                </RoleGate>
              }
            />
            <Route
              path="/settings"
              element={
                <RoleGate minimum={AdminRole.OWNER}>
                  <SettingsPage />
                </RoleGate>
              }
            />
            <Route
              path="/tenants"
              element={
                <RoleGate minimum={AdminRole.SUPER_ADMIN}>
                  <TenantsPage />
                </RoleGate>
              }
            />
            <Route
              path="/tenants/:id"
              element={
                <RoleGate minimum={AdminRole.SUPER_ADMIN}>
                  <TenantDetailPage />
                </RoleGate>
              }
            />
          </Route>
        </Route>

        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
