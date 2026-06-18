import {
  BrowserRouter,
  Routes,
  Route,
  Navigate,
  useParams,
} from "react-router-dom";
import { ProtectedRoute } from "@/components/guards/protected-route";
import { RoleGate } from "@/components/guards/role-gate";
import { AppLayout } from "@/components/layout/app-layout";
import { LoginPage } from "@/pages/login-page";
import { LandingPage } from "@/features/marketing/pages/landing-page";
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
import { AiPromptsPage } from "@/features/settings/pages/ai-prompts-page";
import { TemplatesPage } from "@/features/settings/pages/templates-page";
import AnnouncementsPage from "@/features/announcements/pages/announcements-page";
import CampaignsListPage from "@/features/recruitment/pages/campaigns-list-page";
import CampaignDetailPage from "@/features/recruitment/pages/campaign-detail-page";
import { TestToolPage } from "@/features/test-tool/pages/test-tool-page";
import { MultiVolunteerTestPage } from "@/features/test-tool/pages/multi-volunteer-test-page";
import { TenantsPage } from "@/features/tenants/pages/tenants-page";
import { TenantDetailPage } from "@/features/tenants/pages/tenant-detail-page";
import { CandidatesListPage } from "@/features/candidates/pages/candidates-list-page";
import { ObservabilityPage } from "@/features/observability/pages/observability-page";
import { EvalCasesPage } from "@/features/evals/pages/eval-cases-page";
import { RunSheetPage } from "@/features/event-ops/pages/run-sheet-page";
import { EventReviewPage } from "@/features/reviews/pages/event-review-page";
import { RecognitionDefinitionsPage } from "@/features/recognition/pages/definitions-page";
import { AdminRole } from "@/types/enums";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/login" element={<LoginPage />} />

        <Route element={<ProtectedRoute />}>
          <Route element={<AppLayout />}>
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
            <Route path="/events/specific/:slotId" element={<BookingDetailPage />} />
            <Route path="/events/rule/:ruleId/:date" element={<BookingDetailPage />} />
            <Route path="/customers" element={<CustomersPage />} />
            <Route path="/customers/:phone" element={<CustomerDetailPage />} />
            <Route path="/appointment-types" element={<AppointmentTypesPage />} />
            <Route path="/availability" element={<AvailabilityPage />} />
            <Route path="/reminders" element={<RemindersPage />} />
            <Route path="/conversations" element={<ConversationsPage />} />
            <Route path="/suspensions" element={<SuspensionsPage />} />
            <Route path="/analytics" element={<AnalyticsPage />} />
            {/* Phase 1 — event lifecycle plan */}
            <Route
              path="/candidates"
              element={
                <RoleGate minimum={AdminRole.MANAGER}>
                  <CandidatesListPage />
                </RoleGate>
              }
            />
            <Route
              path="/observability"
              element={
                <RoleGate minimum={AdminRole.MANAGER}>
                  <ObservabilityPage />
                </RoleGate>
              }
            />
            <Route
              path="/run-sheet/:slotId"
              element={
                <RoleGate minimum={AdminRole.MANAGER}>
                  <RunSheetPage />
                </RoleGate>
              }
            />
            <Route
              path="/event-review/:slotId"
              element={
                <RoleGate minimum={AdminRole.MANAGER}>
                  <EventReviewPage />
                </RoleGate>
              }
            />
            <Route
              path="/recognition"
              element={
                <RoleGate minimum={AdminRole.OWNER}>
                  <RecognitionDefinitionsPage />
                </RoleGate>
              }
            />
            <Route
              path="/token-usage"
              element={
                <RoleGate minimum={AdminRole.MANAGER}>
                  <TokenUsagePage />
                </RoleGate>
              }
            />
            <Route
              path="/campaigns"
              element={
                <RoleGate minimum={AdminRole.MANAGER}>
                  <CampaignsListPage />
                </RoleGate>
              }
            />
            <Route
              path="/campaigns/:id"
              element={
                <RoleGate minimum={AdminRole.MANAGER}>
                  <CampaignDetailPage />
                </RoleGate>
              }
            />
            {/* Keep the old /recruitment paths redirecting to /campaigns
                so any saved bookmarks or in-progress sessions don't 404. */}
            <Route
              path="/recruitment"
              element={<Navigate to="/campaigns" replace />}
            />
            <Route
              path="/recruitment/:id"
              element={<RecruitmentDetailRedirect />}
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
              path="/multi-test"
              element={
                <RoleGate minimum={AdminRole.MANAGER}>
                  <MultiVolunteerTestPage />
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
              path="/ai-prompts"
              element={
                <RoleGate minimum={AdminRole.OWNER}>
                  <AiPromptsPage />
                </RoleGate>
              }
            />
            <Route
              path="/templates"
              element={
                <RoleGate minimum={AdminRole.OWNER}>
                  <TemplatesPage />
                </RoleGate>
              }
            />
            <Route
              path="/evals"
              element={
                <RoleGate minimum={AdminRole.SUPER_ADMIN}>
                  <EvalCasesPage />
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

function RecruitmentDetailRedirect() {
  const { id } = useParams();
  return <Navigate to={`/campaigns/${id}`} replace />;
}
