import React, { useState } from 'react';
import { Outlet } from 'react-router-dom';
import Sidebar from './Sidebar';
import AppHeader from './AppHeader';
import { Landmark, ShieldCheck } from 'lucide-react';

export default function AppLayout() {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <div className="min-h-screen bg-slate-50 text-slate-800 flex flex-col font-sans">
      
      {/* Sidebar Navigation (Desktop persistent + Mobile drawer) */}
      <Sidebar mobileOpen={mobileOpen} setMobileOpen={setMobileOpen} />

      {/* Main Content Area (offset by sidebar width on desktop) */}
      <div className="md:pl-64 flex flex-col flex-1 min-w-0">
        
        {/* Top App Header with Context & System Health */}
        <AppHeader onOpenMobileMenu={() => setMobileOpen(true)} />

        {/* Page Content Viewport */}
        <main className="flex-1">
          <Outlet />
        </main>

        {/* Professional Operational Footer */}
        <footer className="border-t border-slate-200 bg-white py-3 px-4 sm:px-6 lg:px-8 text-xs text-slate-500">
          <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-3 text-center sm:text-left">
            <div className="flex items-center gap-2">
              <span className="font-semibold text-slate-700">
                Civora
              </span>
              <span className="hidden md:inline text-slate-300">•</span>
              <span className="hidden md:inline text-slate-500">
                by MassCommAI
              </span>
              <span className="hidden md:inline text-slate-300">•</span>
              <span className="hidden md:inline text-slate-500">
                Bringing communities closer.
              </span>
            </div>
            <div className="flex items-center gap-3 text-xs">
              <span className="inline-flex items-center gap-1 text-green-700 font-medium">
                <ShieldCheck className="w-3.5 h-3.5 text-green-600" />
                Session Secure & Encrypted
              </span>
              <span>•</span>
              <span className="text-slate-400">PostgreSQL Operational</span>
            </div>
          </div>
        </footer>

      </div>

    </div>
  );
}

