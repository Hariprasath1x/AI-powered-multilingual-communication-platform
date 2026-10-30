import React, { useEffect } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Navbar from './components/layout/Navbar';
import Footer from './components/layout/Footer';
import LandingPage from './pages/LandingPage';
import RegisterPage from './pages/RegisterPage';
import LoginPage from './pages/auth/LoginPage';
import DashboardPage from './pages/dashboard/DashboardPage';
import UserManagementPage from './pages/admin/UserManagementPage';
import AudienceListPage from './pages/audience/AudienceListPage';
import SegmentListPage from './pages/segments/SegmentListPage';
import TemplateListPage from './pages/templates/TemplateListPage';
import CampaignListPage from './pages/campaigns/CampaignListPage';
import CampaignWizardPage from './pages/campaigns/CampaignWizardPage';
import CampaignDetailPage from './pages/campaigns/CampaignDetailPage';
import ContentStudioPage from './pages/content/ContentStudioPage';
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
        <div className="min-h-screen flex flex-col bg-slate-50">
          <Navbar />
          <main className="flex-grow">
            <Routes>
              {/* Public Routes */}
              <Route path="/" element={<LandingPage />} />
              <Route path="/register" element={<RegisterPage />} />
              <Route path="/login" element={<LoginPage />} />

              {/* Authenticated Protected Routes */}
              <Route
                path="/dashboard"
                element={
                  <ProtectedRoute>
                    <DashboardPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/audience"
                element={
                  <ProtectedRoute>
                    <AudienceListPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/segments"
                element={
                  <ProtectedRoute>
                    <SegmentListPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/templates"
                element={
                  <ProtectedRoute>
                    <TemplateListPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/campaigns"
                element={
                  <ProtectedRoute>
                    <CampaignListPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/campaigns/new"
                element={
                  <ProtectedRoute>
                    <CampaignWizardPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/campaigns/:id"
                element={
                  <ProtectedRoute>
                    <CampaignDetailPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/campaigns/:id/edit"
                element={
                  <ProtectedRoute>
                    <CampaignWizardPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/content"
                element={
                  <ProtectedRoute>
                    <ContentStudioPage />
                  </ProtectedRoute>
                }
              />

              {/* Administrator Only Routes */}
              <Route
                path="/admin/users"
                element={
                  <AdminRoute>
                    <UserManagementPage />
                  </AdminRoute>
                }
              />

              {/* Fallback */}
              <Route path="*" element={<LandingPage />} />
            </Routes>
          </main>
          <Footer />
        </div>
      </AuthProvider>
    </BrowserRouter>
  );
}
