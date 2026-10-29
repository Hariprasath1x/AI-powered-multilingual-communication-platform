import React, { useState, useEffect } from 'react';
import { Link, useLocation } from 'react-router-dom';
import {
  MessageSquareShare,
  Activity,
  ShieldCheck,
  Menu,
  X,
  ArrowRight,
  User as UserIcon,
  LogOut,
  LayoutDashboard,
  Users
} from 'lucide-react';
import { checkHealth } from '../../services/api';
import { useAuth } from '../../context/AuthContext';

export default function Navbar() {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [systemStatus, setSystemStatus] = useState({ checking: true, healthy: false, label: 'Checking...' });
  const location = useLocation();
  const { user, isAuthenticated, isAdmin, logout } = useAuth();

  useEffect(() => {
    let isMounted = true;
    checkHealth().then((res) => {
      if (isMounted) {
        if (res.healthy) {
          setSystemStatus({ checking: false, healthy: true, label: 'API & DB Connected' });
        } else {
          setSystemStatus({ checking: false, healthy: false, label: res.status === 'unreachable' ? 'API Offline' : 'Degraded' });
        }
      }
    });
    return () => { isMounted = false; };
  }, []);

  const publicNavLinks = [
    { name: 'Features', href: '/#features' },
    { name: 'How It Works', href: '/#how-it-works' },
    { name: 'Impact Areas', href: '/#impact' },
  ];

  const roleBadgeColor = {
    'Admin': 'bg-purple-100 text-purple-800 border-purple-200',
    'Campaign Manager': 'bg-indigo-100 text-indigo-800 border-indigo-200',
    'Communication Team': 'bg-blue-100 text-blue-800 border-blue-200'
  }[user?.role?.name || ''] || 'bg-slate-100 text-slate-800 border-slate-200';

  return (
    <header className="sticky top-0 z-50 bg-white/90 backdrop-blur-md border-b border-slate-200">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          
          {/* Brand Logo & Wordmark */}
          <Link to="/" className="flex items-center gap-2.5 group">
            <div className="w-10 h-10 rounded-xl bg-brand-600 flex items-center justify-center text-white shadow-md shadow-brand-500/20 group-hover:bg-brand-700 transition">
              <MessageSquareShare className="w-5 h-5" />
            </div>
            <div className="flex flex-col">
              <span className="text-xl font-bold tracking-tight text-slate-900 group-hover:text-brand-600 transition">
                MassComm<span className="text-brand-600">AI</span>
              </span>
              <span className="text-[10px] text-slate-400 font-medium tracking-wide uppercase -mt-1">
                Public Awareness Engine
              </span>
            </div>
          </Link>

          {/* System Health Status Indicator */}
          <div className="hidden xl:flex items-center gap-2 px-3 py-1 rounded-full text-xs font-medium border bg-slate-50 border-slate-200">
            <span className={`w-2 h-2 rounded-full ${systemStatus.checking ? 'bg-amber-400 animate-pulse' : systemStatus.healthy ? 'bg-emerald-500' : 'bg-rose-500'}`} />
            <span className="text-slate-600">Backend:</span>
            <span className={systemStatus.healthy ? 'text-emerald-700 font-semibold' : 'text-slate-500'}>
              {systemStatus.label}
            </span>
          </div>

          {/* Navigation Links */}
          <nav className="hidden md:flex items-center gap-6">
            {!isAuthenticated ? (
              publicNavLinks.map((item) => (
                <a
                  key={item.name}
                  href={item.href}
                  className="text-sm font-medium text-slate-600 hover:text-brand-600 transition-colors"
                >
                  {item.name}
                </a>
              ))
            ) : (
              <>
                <Link
                  to="/dashboard"
                  className={`inline-flex items-center gap-1.5 text-sm font-medium transition-colors ${
                    location.pathname === '/dashboard' ? 'text-brand-600 font-semibold' : 'text-slate-600 hover:text-brand-600'
                  }`}
                >
                  <LayoutDashboard className="w-4 h-4" />
                  Dashboard
                </Link>
                <Link
                  to="/audience"
                  className={`inline-flex items-center gap-1.5 text-sm font-medium transition-colors ${
                    location.pathname.startsWith('/audience') ? 'text-brand-600 font-semibold' : 'text-slate-600 hover:text-brand-600'
                  }`}
                >
                  <Users className="w-4 h-4" />
                  Audience
                </Link>
                {isAdmin && (
                  <Link
                    to="/admin/users"
                    className={`inline-flex items-center gap-1.5 text-sm font-medium transition-colors ${
                      location.pathname.startsWith('/admin') ? 'text-brand-600 font-semibold' : 'text-slate-600 hover:text-brand-600'
                    }`}
                  >
                    <ShieldCheck className="w-4 h-4" />
                    User Governance
                  </Link>
                )}
              </>
            )}
          </nav>

          {/* CTAs / User Session */}
          <div className="hidden sm:flex items-center gap-3">
            {isAuthenticated ? (
              <div className="flex items-center gap-3">
                <div className="flex items-center gap-2.5 px-3 py-1.5 bg-slate-50 border border-slate-200 rounded-lg">
                  <div className="w-7 h-7 rounded-full bg-brand-100 text-brand-700 flex items-center justify-center font-bold text-xs">
                    {user?.name ? user.name.charAt(0).toUpperCase() : 'U'}
                  </div>
                  <div className="flex flex-col text-left">
                    <span className="text-xs font-semibold text-slate-800 line-clamp-1 max-w-[120px]">{user?.name}</span>
                    <span className={`text-[10px] font-medium px-1.5 py-0.2 rounded border w-fit ${roleBadgeColor}`}>
                      {user?.role?.name || 'Member'}
                    </span>
                  </div>
                </div>
                <button
                  onClick={logout}
                  className="inline-flex items-center gap-1 px-3 py-2 text-xs font-medium text-slate-600 hover:text-rose-600 hover:bg-rose-50 border border-transparent hover:border-rose-200 rounded-lg transition"
                  title="Sign out of MassCommAI"
                >
                  <LogOut className="w-4 h-4" />
                  Sign Out
                </button>
              </div>
            ) : (
              <>
                <Link
                  to="/login"
                  className="px-4 py-2 text-sm font-medium text-slate-700 hover:text-brand-600 transition"
                  title="Task 3: Authentication"
                >
                  Log in
                </Link>
                <Link
                  to="/register"
                  className="inline-flex items-center gap-1.5 px-4 py-2 text-sm font-semibold text-white bg-brand-600 hover:bg-brand-700 rounded-lg shadow-sm hover:shadow-brand-500/25 transition active:scale-[0.98]"
                  title="Task 2: User Registration"
                >
                  Get Started
                  <ArrowRight className="w-4 h-4" />
                </Link>
              </>
            )}
          </div>

          {/* Mobile Menu Button */}
          <div className="flex md:hidden">
            <button
              type="button"
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="p-2 rounded-md text-slate-600 hover:text-slate-900 hover:bg-slate-100 focus:outline-none"
              aria-label="Toggle menu"
            >
              {mobileMenuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
            </button>
          </div>

        </div>
      </div>

      {/* Mobile Drawer */}
      {mobileMenuOpen && (
        <div className="md:hidden border-b border-slate-200 bg-white px-4 pt-2 pb-6 space-y-3">
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium bg-slate-100">
            <span className={`w-2 h-2 rounded-full ${systemStatus.healthy ? 'bg-emerald-500' : 'bg-rose-500'}`} />
            <span className="text-slate-600">System Status:</span>
            <span className="text-slate-900 font-semibold">{systemStatus.label}</span>
          </div>

          <div className="space-y-1">
            {!isAuthenticated ? (
              publicNavLinks.map((item) => (
                <a
                  key={item.name}
                  href={item.href}
                  onClick={() => setMobileMenuOpen(false)}
                  className="block px-3 py-2 rounded-md text-base font-medium text-slate-700 hover:text-brand-600 hover:bg-slate-50"
                >
                  {item.name}
                </a>
              ))
            ) : (
              <>
                <div className="px-3 py-2 border-b border-slate-100 mb-2">
                  <p className="text-sm font-semibold text-slate-900">{user?.name}</p>
                  <p className="text-xs text-slate-500">{user?.email}</p>
                  <span className={`inline-block mt-1 text-[10px] font-medium px-2 py-0.5 rounded border ${roleBadgeColor}`}>
                    {user?.role?.name}
                  </span>
                </div>
                <Link
                  to="/dashboard"
                  onClick={() => setMobileMenuOpen(false)}
                  className="block px-3 py-2 rounded-md text-base font-medium text-slate-700 hover:text-brand-600 hover:bg-slate-50"
                >
                  Dashboard
                </Link>
                <Link
                  to="/audience"
                  onClick={() => setMobileMenuOpen(false)}
                  className="block px-3 py-2 rounded-md text-base font-medium text-slate-700 hover:text-brand-600 hover:bg-slate-50"
                >
                  Audience Database
                </Link>
                {isAdmin && (
                  <Link
                    to="/admin/users"
                    onClick={() => setMobileMenuOpen(false)}
                    className="block px-3 py-2 rounded-md text-base font-medium text-slate-700 hover:text-brand-600 hover:bg-slate-50"
                  >
                    User Governance (Admin)
                  </Link>
                )}
              </>
            )}
          </div>

          <div className="pt-2 border-t border-slate-100 flex flex-col gap-2">
            {isAuthenticated ? (
              <button
                onClick={() => {
                  setMobileMenuOpen(false);
                  logout();
                }}
                className="w-full text-center py-2 text-sm font-medium text-rose-600 border border-rose-200 rounded-lg hover:bg-rose-50 transition"
              >
                Sign Out
              </button>
            ) : (
              <>
                <Link
                  to="/login"
                  onClick={() => setMobileMenuOpen(false)}
                  className="w-full text-center py-2 text-sm font-medium text-slate-700 border border-slate-200 rounded-lg hover:bg-slate-50"
                >
                  Log in
                </Link>
                <Link
                  to="/register"
                  onClick={() => setMobileMenuOpen(false)}
                  className="w-full text-center py-2 text-sm font-semibold text-white bg-brand-600 rounded-lg shadow-sm hover:bg-brand-700"
                >
                  Get Started
                </Link>
              </>
            )}
          </div>
        </div>
      )}
    </header>
  );
}

