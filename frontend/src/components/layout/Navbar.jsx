import React, { useState, useEffect } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { MessageSquareShare, Activity, ShieldCheck, Menu, X, ArrowRight } from 'lucide-react';
import { checkHealth } from '../../services/api';

export default function Navbar() {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [systemStatus, setSystemStatus] = useState({ checking: true, healthy: false, label: 'Checking...' });
  const location = useLocation();

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

  const navLinks = [
    { name: 'Features', href: '#features' },
    { name: 'How It Works', href: '#how-it-works' },
    { name: 'Impact Areas', href: '#impact' },
  ];

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
          <div className="hidden lg:flex items-center gap-2 px-3 py-1 rounded-full text-xs font-medium border bg-slate-50 border-slate-200">
            <span className={`w-2 h-2 rounded-full ${systemStatus.checking ? 'bg-amber-400 animate-pulse' : systemStatus.healthy ? 'bg-emerald-500' : 'bg-rose-500'}`} />
            <span className="text-slate-600">Backend:</span>
            <span className={systemStatus.healthy ? 'text-emerald-700 font-semibold' : 'text-slate-500'}>
              {systemStatus.label}
            </span>
          </div>

          {/* Desktop Navigation Links */}
          <nav className="hidden md:flex items-center gap-8">
            {navLinks.map((item) => (
              <a
                key={item.name}
                href={item.href}
                className="text-sm font-medium text-slate-600 hover:text-brand-600 transition-colors"
              >
                {item.name}
              </a>
            ))}
          </nav>

          {/* CTAs */}
          <div className="hidden sm:flex items-center gap-3">
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
            {navLinks.map((item) => (
              <a
                key={item.name}
                href={item.href}
                onClick={() => setMobileMenuOpen(false)}
                className="block px-3 py-2 rounded-md text-base font-medium text-slate-700 hover:text-brand-600 hover:bg-slate-50"
              >
                {item.name}
              </a>
            ))}
          </div>

          <div className="pt-2 border-t border-slate-100 flex flex-col gap-2">
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
          </div>
        </div>
      )}
    </header>
  );
}

