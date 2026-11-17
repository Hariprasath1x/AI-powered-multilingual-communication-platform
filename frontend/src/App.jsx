import React, { useEffect, Suspense, lazy } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import PublicLayout from './components/layout/PublicLayout';
import AppLayout from './components/layout/AppLayout';
import ProtectedRoute from './components/guards/ProtectedRoute';
import AdminRoute from './components/guards/AdminRoute';
import { AuthProvider } from './context/AuthContext';
import { LanguageProvider } from './context/LanguageContext';
import { logDiagnosticHealth } from './services/api';

// Route-level code splitting via dynamic imports
const LandingPage = lazy(() => import('./pages/LandingPage'));
const RegisterPage = lazy(() => import('./pages/RegisterPage'));
const LoginPage = lazy(() => import('./pages/auth/LoginPage'));
const PublicAnnouncementsPage = lazy(() => import('./pages/public/PublicAnnouncementsPage'));
const PublicFeedbackPage = lazy(() => import('./pages/public/PublicFeedbackPage'));

const DashboardPage = lazy(() => import('./pages/dashboard/DashboardPage'));
const AnalyticsDashboardPage = lazy(() => import('./pages/analytics/AnalyticsDashboardPage'));
const UserManagementPage = lazy(() => import('./pages/admin/UserManagementPage'));
const ChannelSettingsPage = lazy(() => import('./pages/admin/ChannelSettingsPage'));
const AudienceListPage = lazy(() => import('./pages/audience/AudienceListPage'));
const SegmentListPage = lazy(() => import('./pages/segments/SegmentListPage'));
const TemplateListPage = lazy(() => import('./pages/templates/TemplateListPage'));
const CampaignListPage = lazy(() => import('./pages/campaigns/CampaignListPage'));
const CampaignWizardPage = lazy(() => import('./pages/campaigns/CampaignWizardPage'));
const CampaignDetailPage = lazy(() => import('./pages/campaigns/CampaignDetailPage'));
const ScheduledCampaignsPage = lazy(() => import('./pages/campaigns/ScheduledCampaignsPage'));
const ContentStudioPage = lazy(() => import('./pages/content/ContentStudioPage'));
const DistributionDashboardPage = lazy(() => import('./pages/distribution/DistributionDashboardPage'));
const DeliveryTrackingPage = lazy(() => import('./pages/distribution/DeliveryTrackingPage'));
const FeedbackMonitoringPage = lazy(() => import('./pages/feedback/FeedbackMonitoringPage'));

function PageLoadingFallback() {
  return (
    <div className="flex flex-col items-center justify-center min-h-[40vh] p-8 text-slate-500">
      <div className="w-8 h-8 border-3 border-sky-600 border-t-transparent rounded-full animate-spin mb-3" />
      <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Loading module...</p>
    </div>
  );
}

export default function App() {
  useEffect(() => {
    // Run initial health-check diagnostic once on application load
    logDiagnosticHealth();
  }, []);

  return (
    <BrowserRouter>
      <AuthProvider>
        <LanguageProvider>
          <Suspense fallback={<PageLoadingFallback />}>
            <Routes>
              {/* Public Routes with Institutional Public Navbar & Footer */}
              <Route element={<PublicLayout />}>
                <Route path="/" element={<LandingPage />} />
                <Route path="/register" element={<RegisterPage />} />
                <Route path="/login" element={<LoginPage />} />
                <Route path="/announcements" element={<PublicAnnouncementsPage />} />
                <Route path="/feedback/:token" element={<PublicFeedbackPage />} />
              </Route>

              {/* Authenticated Protected Routes with AppLayout (Sidebar + AppHeader) */}
              <Route
                element={
                  <ProtectedRoute>
                    <AppLayout />
                  </ProtectedRoute>
                }
              >
                <Route path="/dashboard" element={<DashboardPage />} />
                <Route path="/analytics" element={<AnalyticsDashboardPage />} />
                <Route path="/audience" element={<AudienceListPage />} />
                <Route path="/segments" element={<SegmentListPage />} />
                <Route path="/templates" element={<TemplateListPage />} />
                <Route path="/campaigns" element={<CampaignListPage />} />
                <Route path="/campaigns/new" element={<CampaignWizardPage />} />
                <Route path="/campaigns/scheduled" element={<ScheduledCampaignsPage />} />
                <Route path="/campaigns/:id" element={<CampaignDetailPage />} />
                <Route path="/campaigns/:id/edit" element={<CampaignWizardPage />} />
                <Route path="/content" element={<ContentStudioPage />} />
                <Route path="/distribution" element={<DistributionDashboardPage />} />
                <Route path="/distribution/tracking" element={<DeliveryTrackingPage />} />
                <Route path="/feedback" element={<FeedbackMonitoringPage />} />
                <Route
                  path="/admin/users"
                  element={
                    <AdminRoute>
                      <UserManagementPage />
                    </AdminRoute>
                  }
                />
                <Route
                  path="/admin/channels"
                  element={
                    <AdminRoute>
                      <ChannelSettingsPage />
                    </AdminRoute>
                  }
                />
              </Route>

              {/* Fallback Route */}
              <Route element={<PublicLayout />}>
                <Route path="*" element={<LandingPage />} />
              </Route>
            </Routes>
          </Suspense>
        </LanguageProvider>
      </AuthProvider>
    </BrowserRouter>
  );
}
