import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import {
  Users,
  ShieldCheck,
  Layers,
  Megaphone,
  FileText,
  Sparkles,
  SendHorizontal,
  ArrowRight,
  CheckCircle2,
  Plus,
  Radio,
  Activity,
  Sliders,
  ShieldAlert,
  Server,
  Zap,
  BarChart3,
} from 'lucide-react';
import { getAudienceStats } from '../../services/audienceService';
import { listCampaigns } from '../../services/campaignService';
import { listSegments } from '../../services/segmentService';
import { listTemplates } from '../../services/templateService';
import { listContentAssets } from '../../services/contentService';

export default function DashboardPage() {
  const { user, isAdmin } = useAuth();
  const [stats, setStats] = useState({
    audienceCount: null,
    campaignsCount: null,
    segmentsCount: null,
    templatesCount: null,
    contentCount: null,
    loading: true,
  });

  useEffect(() => {
    let isMounted = true;
    Promise.allSettled([
      getAudienceStats(),
      listCampaigns({ page: 1, size: 1 }),
      listSegments({ page: 1, size: 1 }),
      listTemplates({ page: 1, size: 1 }),
      listContentAssets({ page: 1, size: 1 }),
    ]).then(([audRes, campRes, segRes, tplRes, cntRes]) => {
      if (isMounted) {
        setStats({
          audienceCount: audRes.status === 'fulfilled' ? audRes.value?.total_members || 0 : 0,
          campaignsCount: campRes.status === 'fulfilled' ? campRes.value?.total || 0 : 0,
          segmentsCount: segRes.status === 'fulfilled' ? segRes.value?.total || 0 : 0,
          templatesCount: tplRes.status === 'fulfilled' ? tplRes.value?.total || 0 : 0,
          contentCount: cntRes.status === 'fulfilled' ? cntRes.value?.total || 0 : 0,
          loading: false,
        });
      }
    });

    return () => {
      isMounted = false;
    };
  }, []);

  const getRoleBadge = (roleName) => {
    switch (roleName) {
      case 'Admin':
        return 'bg-purple-50 text-purple-700 border-purple-200';
      case 'Campaign Manager':
        return 'bg-blue-50 text-blue-700 border-blue-200';
      case 'Communication Team':
      default:
        return 'bg-teal-50 text-teal-700 border-teal-200';
    }
  };

  const modules = [
    {
      title: 'Audience Database',
      description: 'Manage citizen recipients, language preferences, SMS/Voice endpoints, and verified opt-in consent records.',
      href: '/audience',
      icon: Users,
      iconColor: 'text-teal-600',
      iconBg: 'bg-teal-50 border border-teal-200',
      action: 'View Recipients',
      statLabel: 'Total Contacts',
      statValue: stats.loading ? '...' : stats.audienceCount?.toLocaleString() || '0',
    },
    {
      title: 'Audience Segments',
      description: 'Create dynamic targeting rules combining geographic districts, language preferences, and demographic parameters.',
      href: '/segments',
      icon: Layers,
      iconColor: 'text-blue-600',
      iconBg: 'bg-blue-50 border border-blue-200',
      action: 'Manage Segments',
      statLabel: 'Saved Segments',
      statValue: stats.loading ? '...' : stats.segmentsCount?.toString() || '0',
    },
    {
      title: 'Campaign Studio',
      description: 'Plan and launch multi-channel campaigns with step-by-step audience selection, template binding, and scheduling.',
      href: '/campaigns',
      icon: Megaphone,
      iconColor: 'text-indigo-600',
      iconBg: 'bg-indigo-50 border border-indigo-200',
      action: 'Open Campaigns',
      statLabel: 'Total Campaigns',
      statValue: stats.loading ? '...' : stats.campaignsCount?.toString() || '0',
    },
    {
      title: 'Message Templates',
      description: 'Standardized announcement templates with domain categories, Indian language variants, and dynamic placeholders.',
      href: '/templates',
      icon: FileText,
      iconColor: 'text-purple-600',
      iconBg: 'bg-purple-50 border border-purple-200',
      action: 'Browse Templates',
      statLabel: 'Active Templates',
      statValue: stats.loading ? '...' : stats.templatesCount?.toString() || '0',
    },
    {
      title: 'AI Content Studio',
      description: 'Draft compliant copy with AI assistance, translate into 6 Indian languages, and verify GSM-7/UCS-2 constraints.',
      href: '/content',
      icon: Sparkles,
      iconColor: 'text-amber-600',
      iconBg: 'bg-amber-50 border border-amber-200',
      action: 'Open Studio',
      statLabel: 'Content Assets',
      statValue: stats.loading ? '...' : stats.contentCount?.toString() || '0',
    },
    {
      title: 'Distribution Engine',
      description: 'Monitor automated delivery queues across SMS, WhatsApp, Voice IVR, and Email with real-time worker health.',
      href: '/distribution',
      icon: SendHorizontal,
      iconColor: 'text-green-600',
      iconBg: 'bg-green-50 border border-green-200',
      action: 'Monitor Queues',
      statLabel: 'Engine Status',
      statValue: 'Operational',
    },
    {
      title: 'Analytics & Civic Intelligence',
      description: 'Executive KPIs, conversion funnels, multilingual response trends, and AI-driven broadcast recommendations.',
      href: '/analytics',
      icon: BarChart3,
      iconColor: 'text-purple-600',
      iconBg: 'bg-purple-50 border border-purple-200',
      action: 'View Analytics',
      statLabel: 'Analytics Engine',
      statValue: 'Live Telemetry',
    },
  ];

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
      
      {/* 1. Welcome & Operational Header */}
      <div className="bg-white rounded-lg border border-slate-200 p-5 shadow-subtle flex flex-col lg:flex-row lg:items-center lg:justify-between gap-5">
        <div className="space-y-1.5 max-w-2xl">
          <div className="inline-flex items-center gap-2 text-xs font-medium px-2.5 py-0.5 rounded-full bg-green-50 text-green-700 border border-green-200">
            <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
            Communication System Operational
          </div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
            Welcome back, {user?.full_name || 'Official'}
          </h1>
          <p className="text-sm text-slate-500 leading-relaxed">
            Public Awareness and Mass Communication Command Center. Coordinate targeted multilingual broadcasts across SMS, Voice IVR, WhatsApp, and Email.
          </p>
        </div>

        {/* Account Details Card */}
        <div className="bg-slate-50 p-3.5 rounded-lg border border-slate-200 text-xs space-y-2 lg:min-w-[280px]">
          <div className="flex items-center justify-between pb-2 border-b border-slate-200">
            <span className="text-slate-500">Role</span>
            <span className={`px-2 py-0.5 rounded-full font-medium border text-[11px] ${getRoleBadge(user?.role_name)}`}>
              {user?.role_name || user?.role?.name || 'Authorized User'}
            </span>
          </div>
          <div className="flex items-center justify-between text-xs">
            <span className="text-slate-500">Account</span>
            <span className="font-medium text-slate-800 truncate max-w-[160px]">{user?.email}</span>
          </div>
          <div className="flex items-center justify-between text-xs">
            <span className="text-slate-500">Department</span>
            <span className="font-medium text-slate-800">{user?.organization || 'MassCommAI Platform'}</span>
          </div>
        </div>
      </div>

      {/* 2. Key Operational Statistics Bar */}
      <div>
        <h2 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">
          Key Platform Statistics
        </h2>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
          <div className="bg-white p-4 rounded-lg border border-slate-200 shadow-subtle space-y-1">
            <div className="flex items-center justify-between text-xs text-slate-500">
              <span>Recipients</span>
              <Users className="w-4 h-4 text-teal-600" />
            </div>
            <div className="text-2xl font-bold text-slate-900">
              {stats.loading ? '...' : stats.audienceCount?.toLocaleString() || '0'}
            </div>
            <div className="text-[11px] text-slate-500">Registered contacts</div>
          </div>

          <div className="bg-white p-4 rounded-lg border border-slate-200 shadow-subtle space-y-1">
            <div className="flex items-center justify-between text-xs text-slate-500">
              <span>Segments</span>
              <Layers className="w-4 h-4 text-blue-600" />
            </div>
            <div className="text-2xl font-bold text-slate-900">
              {stats.loading ? '...' : stats.segmentsCount?.toString() || '0'}
            </div>
            <div className="text-[11px] text-slate-500">Targeting criteria</div>
          </div>

          <div className="bg-white p-4 rounded-lg border border-slate-200 shadow-subtle space-y-1">
            <div className="flex items-center justify-between text-xs text-slate-500">
              <span>Templates</span>
              <FileText className="w-4 h-4 text-purple-600" />
            </div>
            <div className="text-2xl font-bold text-slate-900">
              {stats.loading ? '...' : stats.templatesCount?.toString() || '0'}
            </div>
            <div className="text-[11px] text-slate-500">Reusable messages</div>
          </div>

          <div className="bg-white p-4 rounded-lg border border-slate-200 shadow-subtle space-y-1">
            <div className="flex items-center justify-between text-xs text-slate-500">
              <span>Campaigns</span>
              <Megaphone className="w-4 h-4 text-indigo-600" />
            </div>
            <div className="text-2xl font-bold text-slate-900">
              {stats.loading ? '...' : stats.campaignsCount?.toString() || '0'}
            </div>
            <div className="text-[11px] text-slate-500">Awareness drives</div>
          </div>

          <div className="bg-white p-4 rounded-lg border border-slate-200 shadow-subtle space-y-1">
            <div className="flex items-center justify-between text-xs text-slate-500">
              <span>Content Drafts</span>
              <Sparkles className="w-4 h-4 text-amber-600" />
            </div>
            <div className="text-2xl font-bold text-slate-900">
              {stats.loading ? '...' : stats.contentCount?.toString() || '0'}
            </div>
            <div className="text-[11px] text-slate-500">Multilingual assets</div>
          </div>
        </div>
      </div>

      {/* 3. Quick Actions Toolbar */}
      <div className="bg-white rounded-lg border border-slate-200 p-4 shadow-subtle">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Zap className="w-4 h-4 text-blue-600" />
            <span className="text-sm font-semibold text-slate-900">Quick Actions</span>
            <span className="text-xs text-slate-500 hidden md:inline">— Frequent operations</span>
          </div>
          <div className="flex items-center gap-2.5 flex-wrap">
            <Link
              to="/campaigns/new"
              className="inline-flex items-center gap-1.5 px-3.5 py-2 text-xs font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg shadow-sm transition"
            >
              <Plus className="w-3.5 h-3.5" />
              New Campaign
            </Link>
            <Link
              to="/audience"
              className="inline-flex items-center gap-1.5 px-3.5 py-2 text-xs font-medium text-slate-700 bg-white hover:bg-slate-50 border border-slate-300 rounded-lg shadow-sm transition"
            >
              <Users className="w-3.5 h-3.5 text-slate-500" />
              Add Recipient
            </Link>
            <Link
              to="/content"
              className="inline-flex items-center gap-1.5 px-3.5 py-2 text-xs font-medium text-slate-700 bg-white hover:bg-slate-50 border border-slate-300 rounded-lg shadow-sm transition"
            >
              <Sparkles className="w-3.5 h-3.5 text-slate-500" />
              Generate Message
            </Link>
            <Link
              to="/distribution"
              className="inline-flex items-center gap-1.5 px-3.5 py-2 text-xs font-medium text-slate-700 bg-white hover:bg-slate-50 border border-slate-300 rounded-lg shadow-sm transition"
            >
              <SendHorizontal className="w-3.5 h-3.5 text-slate-500" />
              Delivery Queues
            </Link>
          </div>
        </div>
      </div>

      {/* 4. Primary Communication Modules Grid */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
            Communication Modules
          </h2>
          <span className="text-xs text-slate-500">6 core functional areas</span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {modules.map((mod) => {
            const Icon = mod.icon;
            return (
              <div
                key={mod.title}
                className="bg-white rounded-lg border border-slate-200 p-5 shadow-subtle hover:border-slate-300 hover:shadow-elevated transition flex flex-col justify-between"
              >
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <div className={`w-9 h-9 rounded-lg flex items-center justify-center ${mod.iconBg}`}>
                      <Icon className={`w-5 h-5 ${mod.iconColor}`} />
                    </div>
                    <span className="text-xs font-semibold text-slate-700 bg-slate-50 px-2.5 py-0.5 rounded-full border border-slate-200">
                      {mod.statValue}
                    </span>
                  </div>

                  <div>
                    <h3 className="text-base font-semibold text-slate-900">
                      {mod.title}
                    </h3>
                    <p className="text-xs text-slate-500 mt-1 leading-relaxed">
                      {mod.description}
                    </p>
                  </div>
                </div>

                <div className="pt-4 mt-4 border-t border-slate-100 flex items-center justify-between">
                  <span className="text-xs text-slate-500 font-medium">
                    {mod.statLabel}
                  </span>
                  <Link
                    to={mod.href}
                    className="inline-flex items-center gap-1 text-xs font-semibold text-blue-600 hover:text-blue-700 transition"
                  >
                    <span>{mod.action}</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </Link>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* 5. Standards & Governance Reference Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        
        {/* Telephony Constraints Info */}
        <div className="p-4 bg-white rounded-lg border border-slate-200 shadow-subtle space-y-2.5">
          <div className="flex items-center gap-2 text-xs font-semibold text-slate-900">
            <Radio className="w-4 h-4 text-blue-600" />
            <span>Telecommunication Standards & Constraints</span>
          </div>
          <p className="text-xs text-slate-500 leading-relaxed">
            Automatic character encoding detection enforces single-part vs multipart limits across channels:
          </p>
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div className="p-2 bg-slate-50 rounded border border-slate-200">
              <span className="font-semibold text-slate-800 block">GSM-7 (English):</span>
              <span className="text-slate-500">160 chars / part (153 multipart)</span>
            </div>
            <div className="p-2 bg-slate-50 rounded border border-slate-200">
              <span className="font-semibold text-slate-800 block">UCS-2 (Indic):</span>
              <span className="text-slate-500">70 chars / part (67 multipart)</span>
            </div>
          </div>
        </div>

        {/* Role-Based Governance Reference */}
        <div className="p-4 bg-white rounded-lg border border-slate-200 shadow-subtle space-y-2.5">
          <div className="flex items-center gap-2 text-xs font-semibold text-slate-900">
            <ShieldCheck className="w-4 h-4 text-green-600" />
            <span>Role-Based Operational Access Control</span>
          </div>
          <p className="text-xs text-slate-500 leading-relaxed">
            Strict permission policies govern content authoring, review sign-offs, and batch dispatches:
          </p>
          <div className="grid grid-cols-3 gap-2 text-[11px] text-center">
            <div className="p-1.5 bg-slate-50 rounded border border-slate-200">
              <span className="font-semibold text-purple-700 block">Admin</span>
              <span className="text-slate-500">Full System</span>
            </div>
            <div className="p-1.5 bg-slate-50 rounded border border-slate-200">
              <span className="font-semibold text-blue-700 block">Manager</span>
              <span className="text-slate-500">Launch & Approve</span>
            </div>
            <div className="p-1.5 bg-slate-50 rounded border border-slate-200">
              <span className="font-semibold text-teal-700 block">Team</span>
              <span className="text-slate-500">Draft & Review</span>
            </div>
          </div>
        </div>

      </div>

    </div>
  );
}