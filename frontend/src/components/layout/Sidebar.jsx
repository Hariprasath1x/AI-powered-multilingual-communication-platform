import React from 'react';
import { NavLink, useNavigate, useLocation } from 'react-router-dom';
import {
  LayoutDashboard,
  Users,
  Layers,
  Megaphone,
  FileText,
  Sparkles,
  SendHorizontal,
  ShieldCheck,
  LogOut,
  X,
  Radio,
  Calendar,
  RotateCcw,
  MessageSquareHeart,
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';

export default function Sidebar({ mobileOpen, setMobileOpen }) {
  const { user, isAdmin, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const navGroups = [
    {
      group: 'Overview',
      items: [
        { name: 'Dashboard', path: '/dashboard', icon: LayoutDashboard },
      ],
    },
    {
      group: 'Audience & Reach',
      items: [
        { name: 'Audience Database', path: '/audience', icon: Users },
        { name: 'Audience Segments', path: '/segments', icon: Layers },
      ],
    },
    {
      group: 'Communication & Creative',
      items: [
        { name: 'Campaign Studio', path: '/campaigns', icon: Megaphone },
        { name: 'Scheduled Campaigns', path: '/campaigns/scheduled', icon: Calendar },
        { name: 'Message Templates', path: '/templates', icon: FileText },
        { name: 'AI Content Studio', path: '/content', icon: Sparkles },
      ],
    },
    {
      group: 'Delivery & Telephony',
      items: [
        { name: 'Distribution Engine', path: '/distribution', icon: SendHorizontal },
        { name: 'Delivery Tracking & Retries', path: '/distribution/tracking', icon: RotateCcw },
      ],
    },
    {
      group: 'Feedback & Community',
      items: [
        { name: 'Citizen Feedback', path: '/feedback', icon: MessageSquareHeart },
      ],
    },
  ];

  if (isAdmin) {
    navGroups.push({
      group: 'Administration',
      items: [
        { name: 'User Governance', path: '/admin/users', icon: ShieldCheck },
        { name: 'Channel Settings', path: '/admin/channels', icon: Radio },
      ],
    });
  }

  const rolePill = {
    Admin: 'bg-purple-950 text-purple-300 border-purple-800',
    'Campaign Manager': 'bg-blue-950 text-blue-300 border-blue-800',
    'Communication Team': 'bg-teal-950 text-teal-300 border-teal-800',
  }[user?.role?.name || user?.role_name || ''] || 'bg-slate-800 text-slate-300 border-slate-700';

  const NavContent = () => (
    <div className="flex flex-col h-full bg-slate-900 text-slate-300 border-r border-slate-800 select-none">

      {/* Brand Header */}
      <div className="p-4 border-b border-slate-800">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-lg bg-blue-600 text-white flex items-center justify-center shadow-sm">
              <Radio className="w-5 h-5 text-white" />
            </div>
            <div>
              <div className="flex items-center gap-1">
                <span className="text-base font-bold text-white tracking-tight">MassComm</span>
                <span className="text-blue-400 text-base font-bold">AI</span>
              </div>
              <p className="text-[10px] text-slate-400 font-medium tracking-wider uppercase">
                Public Awareness Platform
              </p>
            </div>
          </div>

          {/* Close button on mobile drawer */}
          {mobileOpen && (
            <button
              onClick={() => setMobileOpen(false)}
              className="md:hidden p-1.5 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800 transition"
              aria-label="Close menu"
            >
              <X className="w-5 h-5" />
            </button>
          )}
        </div>
      </div>

      {/* Navigation Groupings */}
      <div className="flex-1 overflow-y-auto px-3 py-4 space-y-5">
        {navGroups.map((grp) => (
          <div key={grp.group} className="space-y-1">
            <span className="px-3 text-[10px] font-semibold text-slate-400 uppercase tracking-wider block mb-1">
              {grp.group}
            </span>
            <div className="space-y-0.5">
              {grp.items.map((item) => {
                const Icon = item.icon;
                const isActive = location.pathname === item.path || (item.path !== '/dashboard' && location.pathname.startsWith(item.path));
                return (
                  <NavLink
                    key={item.path}
                    to={item.path}
                    onClick={() => setMobileOpen(false)}
                    className={`flex items-center justify-between px-3 py-2 rounded-lg text-xs font-medium transition ${
                      isActive
                        ? 'bg-slate-800 text-white font-semibold border-l-2 border-blue-500'
                        : 'text-slate-300 hover:text-white hover:bg-slate-800/60'
                    }`}
                  >
                    <div className="flex items-center gap-2.5">
                      <Icon className={`w-4 h-4 transition ${isActive ? 'text-blue-400' : 'text-slate-400'}`} />
                      <span>{item.name}</span>
                    </div>
                    {isActive && <span className="w-1.5 h-1.5 rounded-full bg-blue-500" />}
                  </NavLink>
                );
              })}
            </div>
          </div>
        ))}
      </div>

      {/* User Session Footer */}
      <div className="p-3.5 border-t border-slate-800 bg-slate-950/60 space-y-2.5">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center font-bold text-xs text-blue-400">
            {user?.full_name ? user.full_name.charAt(0).toUpperCase() : 'U'}
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-xs font-medium text-white truncate">
              {user?.full_name || 'Authorized Official'}
            </div>
            <div className="flex items-center gap-1.5 mt-0.5">
              <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded border ${rolePill}`}>
                {user?.role?.name || user?.role_name || 'Official'}
              </span>
            </div>
          </div>
        </div>

        <div className="flex items-center justify-between pt-1 text-xs text-slate-400">
          <span className="truncate max-w-[130px] text-[11px]" title={user?.organization || 'MassCommAI'}>
            {user?.organization || 'MassCommAI'}
          </span>
          <button
            onClick={handleLogout}
            className="inline-flex items-center gap-1 text-xs font-medium text-slate-400 hover:text-red-400 transition"
            title="Sign out of platform"
          >
            <LogOut className="w-3.5 h-3.5" />
            <span>Sign Out</span>
          </button>
        </div>
      </div>
    </div>
  );

  return (
    <>
      {/* Desktop Persistent Sidebar */}
      <aside className="hidden md:flex md:w-64 md:flex-col md:fixed md:inset-y-0 z-40">
        <NavContent />
      </aside>

      {/* Mobile Drawer Backdrop */}
      {mobileOpen && (
        <div
          onClick={() => setMobileOpen(false)}
          className="fixed inset-0 z-40 bg-slate-900/60 backdrop-blur-xs md:hidden"
        />
      )}

      {/* Mobile Slide-out Drawer */}
      <div
        className={`fixed inset-y-0 left-0 z-50 w-72 transform transition-transform duration-300 ease-in-out md:hidden ${
          mobileOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <NavContent />
      </div>
    </>
  );
}

