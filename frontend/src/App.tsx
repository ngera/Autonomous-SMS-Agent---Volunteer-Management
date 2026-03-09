import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { ProtectedRoute } from "@/components/guards/protected-route";
import { RoleGate } from "@/components/guards/role-gate";
import { AppLayout } from "@/components/layout/app-layout";
import { LoginPage } from "@/pages/login-page";
import { PlaceholderPage } from "@/pages/placeholder";
import { DashboardPage } from "@/features/dashboard/pages/dashboard-page";
import { BookingsPage } from "@/features/bookings/pages/bookings-page";
import { BookingDetailPage } from "@/features/bookings/pages/booking-detail-page";
import { BookingCreatePage } from "@/features/bookings/pages/booking-create-page";
import { CustomersPage } from "@/features/customers/pages/customers-page";
import { CustomerDetailPage } from "@/features/customers/pages/customer-detail-page";
import { AppointmentTypesPage } from "@/features/appointment-types/pages/appointment-types-page";
import { AdminRole } from "@/types/enums";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />

        <Route element={<ProtectedRoute />}>
          <Route element={<AppLayout />}>
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/bookings" element={<BookingsPage />} />
            <Route path="/bookings/new" element={<BookingCreatePage />} />
            <Route path="/bookings/:id" element={<BookingDetailPage />} />
            <Route path="/customers" element={<CustomersPage />} />
            <Route path="/customers/:phone" element={<CustomerDetailPage />} />
            <Route path="/appointment-types" element={<AppointmentTypesPage />} />
            <Route path="/availability" element={<PlaceholderPage />} />
            <Route path="/reminders" element={<PlaceholderPage />} />
            <Route path="/conversations" element={<PlaceholderPage />} />
            <Route path="/conversations/:id" element={<PlaceholderPage />} />
            <Route path="/suspensions" element={<PlaceholderPage />} />
            <Route path="/suspensions/:id" element={<PlaceholderPage />} />
            <Route path="/analytics" element={<PlaceholderPage />} />
            <Route
              path="/settings"
              element={
                <RoleGate minimum={AdminRole.OWNER}>
                  <PlaceholderPage />
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
