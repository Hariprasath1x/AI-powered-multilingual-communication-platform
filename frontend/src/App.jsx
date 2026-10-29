import React, { useEffect } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Navbar from './components/layout/Navbar';
import Footer from './components/layout/Footer';
import LandingPage from './pages/LandingPage';
import PlaceholderAuth from './pages/PlaceholderAuth';
import { logDiagnosticHealth } from './services/api';

export default function App() {
  useEffect(() => {
    // Run initial health-check diagnostic once on application load
    logDiagnosticHealth();
  }, []);

  return (
    <BrowserRouter>
      <div className="min-h-screen flex flex-col bg-slate-50">
        <Navbar />
        <main className="flex-grow">
          <Routes>
            <Route path="/" element={<LandingPage />} />
            <Route path="/login" element={<PlaceholderAuth />} />
            <Route path="/register" element={<PlaceholderAuth />} />
            <Route path="*" element={<LandingPage />} />
          </Routes>
        </main>
        <Footer />
      </div>
    </BrowserRouter>
  );
}

