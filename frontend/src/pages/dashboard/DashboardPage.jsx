import React from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { 
  Users, 
  ShieldCheck, 
  Layers, 
  Megaphone, 
  Mail, 
  Building2, 
  ArrowRight, 
  CheckCircle2, 
  Clock 
} from 'lucide-react';

export default function DashboardPage() {
  const { user, isAdmin } = useAuth();

  const getRoleBadge = (roleName) => {
    switch (roleName) {
      case 'Admin':
        return 'bg-purple-100 text-purple-800 border-purple-200';
      case 'Campaign Manager':
        return 'bg-indigo-100 text-indigo-800 border-indigo-200';
      case 'Communication Team':
      default:
        return 'bg-emerald-100 text-emerald-800 border-emerald-200';
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 space-y-8">
      
      {/* Welcome Banner */}
      <div className="bg-white rounded-2xl p-6 sm:p-8 border border-slate-200 shadow-sm flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
        <div className="space-y-2">
          <div className="inline-flex items-center gap-2 text-xs font-semibold px-2.5 py-0.5 rounded-full bg-brand-50 text-brand-700 border border-brand-200">
            <CheckCircle2 className="w-3.5 h-3.5 text-brand-600" />
            Authenticated Session Active
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">
            Welcome back, {user?.full_name}!
          </h1>
          <p className="text-sm text-slate-600 max-w-2xl">
            You are signed in to the AI-Powered Multilingual Public Awareness and Mass Communication Platform.
          </p>
        </div>

        {/* Profile Details Pill */}
        <div className="bg-slate-50 p-4 rounded-xl border border-slate-200 text-xs space-y-1.5 w-full md:w-auto min-w-[240px]">
          <div className="flex items-center justify-between gap-4">
            <span className="text-slate-500">System Role:</span>
            <span className={`px-2 py-0.5 rounded-full font-semibold border ${getRoleBadge(user?.role_name)}`}>
              {user?.role_name}
            </span>
          </div>
          <div className="flex items-center justify-between gap-4">
            <span className="text-slate-500">Email:</span>
            <span className="font-medium text-slate-800">{user?.email}</span>
          </div>
          <div className="flex items-center justify-between gap-4">
            <span className="text-slate-500">Organization:</span>
            <span className="font-medium text-slate-800">{user?.organization || 'N/A'}</span>
          </div>
        </div>
      </div>

      {/* Admin Module Quick Access (Admin Only) */}
      {isAdmin && (
        <div className="bg-gradient-to-r from-purple-900 to-indigo-900 rounded-2xl p-6 sm:p-8 text-white shadow-lg space-y-4">
          <div className="flex items-center gap-2 text-purple-300 text-xs font-bold uppercase tracking-wider">
            <ShieldCheck className="w-4 h-4" />
            Administrator Controls
          </div>
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
            <div className="space-y-1">
              <h3 className="text-xl font-bold">User Directory & Role Governance</h3>
              <p className="text-sm text-purple-200 max-w-xl">
                Manage platform accounts, elevate members to Campaign Manager or Admin, and toggle account activation states.
              </p>
            </div>
            <Link
              to="/admin/users"
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl font-semibold text-purple-950 bg-white hover:bg-purple-50 transition shadow-sm whitespace-nowrap"
            >
              Open User Management
              <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
        </div>
      )}

      {/* Milestone 1 Feature Modules Grid */}
      <div className="space-y-4">
        <h2 className="text-lg font-bold text-slate-900">
          Communication Modules
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          
          {/* Audience Management */}
          <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm space-y-3">
            <div className="w-10 h-10 rounded-xl bg-blue-100 text-blue-600 flex items-center justify-center">
              <Users className="w-5 h-5" />
            </div>
            <div className="flex items-center justify-between">
              <h3 className="text-base font-bold text-slate-900">Audience Database</h3>
              <span className="text-[11px] font-semibold px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 flex items-center gap-1">
                <Clock className="w-3 h-3" /> Task 4
              </span>
            </div>
            <p className="text-xs text-slate-600 leading-relaxed">
              Recipient directory with language preferences, communication channels, and bulk CSV ingestion.
            </p>
          </div>

          {/* Audience Segmentation */}
          <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm space-y-3">
            <div className="w-10 h-10 rounded-xl bg-amber-100 text-amber-600 flex items-center justify-center">
              <Layers className="w-5 h-5" />
            </div>
            <div className="flex items-center justify-between">
              <h3 className="text-base font-bold text-slate-900">Audience Segments</h3>
              <span className="text-[11px] font-semibold px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 flex items-center gap-1">
                <Clock className="w-3 h-3" /> Task 5
              </span>
            </div>
            <p className="text-xs text-slate-600 leading-relaxed">
              Dynamic rule builder targeting recipients by language, geography, and civic demographics.
            </p>
          </div>

          {/* Campaign Creation */}
          <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm space-y-3">
            <div className="w-10 h-10 rounded-xl bg-emerald-100 text-emerald-600 flex items-center justify-center">
              <Megaphone className="w-5 h-5" />
            </div>
            <div className="flex items-center justify-between">
              <h3 className="text-base font-bold text-slate-900">Campaign Studio</h3>
              <span className="text-[11px] font-semibold px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 flex items-center gap-1">
                <Clock className="w-3 h-3" /> Task 6
              </span>
            </div>
            <p className="text-xs text-slate-600 leading-relaxed">
              Multi-step campaign workflows, placeholder-aware templates, and content libraries.
            </p>
          </div>

        </div>
      </div>

    </div>
  );
}

