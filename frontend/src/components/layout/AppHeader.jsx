import React, { useState, useEffect } from 'react';
import { useLocation, Link } from 'react-router-dom';
import { Menu, ShieldCheck, CheckCircle2, AlertCircle, Radio, User as UserIcon, Globe } from 'lucide-react';
import { checkHealth } from '../../services/api';
import { useAuth } from '../../context/AuthContext';
import { useLanguage } from '../../context/LanguageContext';

const ROUTE_TITLES = {
  '/dashboard': { title: 'Platform Dashboard', category: 'Overview' },
  '/audience': { title: 'Audience Database', category: 'Audience & Reach' },
  '/segments': { title: 'Audience Segments', category: 'Audience & Reach' },
  '/campaigns': { title: 'Campaign Studio', category: 'Communication & Creative' },
  '/campaigns/new': { title: 'New Public Awareness Campaign', category: 'Campaign Studio' },
  '/templates': { title: 'Message Templates', category: 'Communication & Creative' },
  '/content': { title: 'AI Content Studio', category: 'Communication & Creative' },
  '/distribution': { title: 'Multi-Channel Distribution', category: 'Delivery & Telephony' },
  '/admin/users': { title: 'User Governance & Roles', category: 'Administration' },
};

export default function AppHeader({ onOpenMobileMenu }) {
  const location = useLocation();
  const { user } = useAuth();
  const { currentLang, toggleLanguage, t } = useLanguage();
  const [systemStatus, setSystemStatus] = useState({ checking: true, healthy: false, label: 'Connecting...' });

  useEffect(() => {
    let isMounted = true;
    checkHealth().then((res) => {
      if (isMounted) {
        if (res.healthy) {
          setSystemStatus({ checking: false, healthy: true, label: 'API & DB Connected' });
        } else {
          setSystemStatus({
            checking: false,
            healthy: false,
            label: res.status === 'unreachable' ? 'API Offline' : 'Degraded',
          });
        }
      }
    });
    return () => {
      isMounted = false;
    };
  }, []);

  const routeInfo = ROUTE_TITLES[location.pathname] || {
    title: location.pathname.startsWith('/campaigns/') ? 'Campaign Details' : 'Civora Platform',
    category: 'Communication',
  };

  return (
    <header className="sticky top-0 z-30 bg-white border-b border-slate-200 px-4 sm:px-6 lg:px-8 py-3 transition-colors">
      <div className="flex items-center justify-between gap-4">
        
        {/* Left: Mobile Toggle & Page Context Breadcrumb */}
        <div className="flex items-center gap-3 min-w-0">
          <button
            onClick={onOpenMobileMenu}
            className="md:hidden p-2 rounded-lg text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition"
            aria-label="Open navigation sidebar"
          >
            <Menu className="w-5 h-5" />
          </button>

          <div className="min-w-0">
            <div className="flex items-center gap-1.5 text-xs text-slate-500">
              <span className="font-medium text-slate-600">Civora</span>
              <span>/</span>
              <span className="text-slate-500">{routeInfo.category}</span>
            </div>
            <div className="text-base sm:text-lg font-bold text-slate-900 truncate tracking-tight">
              {routeInfo.title}
            </div>
          </div>
        </div>

        {/* Right: Language Switcher, System Health Pill & User Badge */}
        <div className="flex items-center gap-2.5">

          {/* Bilingual Language Switcher Toggle */}
          <button
            onClick={toggleLanguage}
            type="button"
            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium border border-slate-200 bg-slate-50 hover:bg-slate-100 text-slate-700 transition"
            title="Toggle interface language (English / हिंदी)"
          >
            <Globe className="w-3.5 h-3.5 text-slate-500" />
            <span className="font-semibold">{currentLang === 'en' ? 'हिंदी' : 'English'}</span>
          </button>

          {/* Real-time System Connectivity Badge */}
          <div
            className="hidden sm:inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-medium border bg-slate-50 border-slate-200"
            title="Real-time backend API and PostgreSQL health status"
          >
            <span
              className={`w-2 h-2 rounded-full ${
                systemStatus.checking
                  ? 'bg-amber-400 animate-pulse'
                  : systemStatus.healthy
                  ? 'bg-green-500'
                  : 'bg-red-500'
              }`}
            />
            <span className="text-slate-500 text-xs">System:</span>
            <span
              className={`text-xs font-medium ${
                systemStatus.healthy ? 'text-green-700' : 'text-slate-600'
              }`}
            >
              {systemStatus.label}
            </span>
          </div>

          {/* User initials chip */}
          <div className="flex items-center gap-2 pl-2 border-l border-slate-200">
            <div className="w-8 h-8 rounded-full bg-slate-100 border border-slate-200 flex items-center justify-center font-bold text-xs text-slate-700">
              {user?.full_name ? user.full_name.charAt(0).toUpperCase() : 'U'}
            </div>
            <div className="hidden lg:block text-left">
              <div className="text-xs font-medium text-slate-900 truncate max-w-[120px]">
                {user?.full_name || 'Official'}
              </div>
              <div className="text-[10px] text-slate-500">
                {user?.role?.name || user?.role_name || 'User'}
              </div>
            </div>
          </div>

        </div>

      </div>
    </header>
  );
}

