import React, { useEffect } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import PublicLayout from './components/layout/PublicLayout';
import AppLayout from './components/layout/AppLayout';
import LandingPage from './pages/LandingPage';
import RegisterPage from './pages/RegisterPage';
import LoginPage from './pages/auth/LoginPage';
import PublicAnnouncementsPage from './pages/public/PublicAnnouncementsPage';
import DashboardPage from './pages/dashboard/DashboardPage';
import UserManagementPage from './pages/admin/UserManagementPage';
import ChannelSettingsPage from './pages/admin/ChannelSettingsPage';
import AudienceListPage from './pages/audience/AudienceListPage';
import SegmentListPage from './pages/segments/SegmentListPage';
import TemplateListPage from './pages/templates/TemplateListPage';
import CampaignListPage from './pages/campaigns/CampaignListPage';
import CampaignWizardPage from './pages/campaigns/CampaignWizardPage';
import CampaignDetailPage from './pages/campaigns/CampaignDetailPage';
import ContentStudioPage from './pages/content/ContentStudioPage';
import DistributionDashboardPage from './pages/distribution/DistributionDashboardPage';
import ProtectedRoute from './components/guards/ProtectedRoute';
import AdminRoute from './components/guards/AdminRoute';
import { AuthProvider } from './context/AuthContext';
import { logDiagnosticHealth } from './services/api';

export default function App() {
  useEffect(() => {
    // Run initial health-check diagnostic once on application load
    logDiagnosticHealth();
  }, []);

  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          {/* Public Routes with Institutional Public Navbar & Footer */}
          <Route element={<PublicLayout />}>
            <Route path="/" element={<LandingPage />} />
            <Route path="/register" element={<RegisterPage />} />
            <Route path="/login" element={<LoginPage />} />
            <Route path="/announcements" element={<PublicAnnouncementsPage />} />
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
            <Route path="/audience" element={<AudienceListPage />} />
            <Route path="/segments" element={<SegmentListPage />} />
            <Route path="/templates" element={<TemplateListPage />} />
            <Route path="/campaigns" element={<CampaignListPage />} />
            <Route path="/campaigns/new" element={<CampaignWizardPage />} />
            <Route path="/campaigns/:id" element={<CampaignDetailPage />} />
            <Route path="/campaigns/:id/edit" element={<CampaignWizardPage />} />
            <Route path="/content" element={<ContentStudioPage />} />
            <Route path="/distribution" element={<DistributionDashboardPage />} />
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
      </AuthProvider>
    </BrowserRouter>
  );
}
