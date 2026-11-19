import React, { useState, useEffect, useMemo, useCallback } from 'react';
import {
  BarChart3,
  TrendingUp,
  Download,
  Filter,
  RefreshCw,
  Send,
  CheckCircle2,
  Eye,
  MousePointerClick,
  MessageSquare,
  AlertTriangle,
  Sparkles,
  Layers,
  Globe,
  Radio,
  FileSpreadsheet,
  FileText,
  ChevronDown,
  X,
  ArrowRight,
  ShieldAlert,
  ThumbsUp,
  ThumbsDown,
  Minus,
  Info,
  Calendar,
} from 'lucide-react';

import {
  getAnalyticsKPIs,
  getAnalyticsTrends,
  getAnalyticsBreakdowns,
  getAnalyticsFunnel,
  getAnalyticsInsights,
  downloadAnalyticsCSV,
  downloadAnalyticsPDF,
} from '../../services/analyticsService';
import { listCampaigns } from '../../services/campaignService';
import { listSegments } from '../../services/segmentService';

export default function AnalyticsDashboardPage() {
  // Global Filter State
  const [datePreset, setDatePreset] = useState('30d');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [selectedCampaign, setSelectedCampaign] = useState('');
  const [selectedChannel, setSelectedChannel] = useState('');
  const [selectedLanguage, setSelectedLanguage] = useState('');
  const [selectedSegment, setSelectedSegment] = useState('');

  // Dropdown reference options
  const [campaignOptions, setCampaignOptions] = useState([]);
  const [segmentOptions, setSegmentOptions] = useState([]);

  // Data States
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [kpis, setKpis] = useState(null);
  const [trends, setTrends] = useState(null);
  const [breakdowns, setBreakdowns] = useState(null);
  const [funnel, setFunnel] = useState(null);
  const [insights, setInsights] = useState(null);

  // Export states
  const [exportingCsv, setExportingCsv] = useState(false);
  const [exportingPdf, setExportingPdf] = useState(false);

  // Trends Metric Toggles
  const [activeMetrics, setActiveMetrics] = useState({
    sent: false,
    delivered: true,
    opens: true,
    clicks: true,
    replies: false,
  });
  const [hoveredTrendPoint, setHoveredTrendPoint] = useState(null);

  // Initialize Date Presets
  const resolveDateParams = useCallback(() => {
    const now = new Date();
    const endStr = now.toISOString().split('T')[0];

    if (datePreset === '7d') {
      const past = new Date();
      past.setDate(now.getDate() - 7);
      return { start_date: past.toISOString().split('T')[0], end_date: endStr };
    }
    if (datePreset === '30d') {
      const past = new Date();
      past.setDate(now.getDate() - 30);
      return { start_date: past.toISOString().split('T')[0], end_date: endStr };
    }
    if (datePreset === '90d') {
      const past = new Date();
      past.setDate(now.getDate() - 90);
      return { start_date: past.toISOString().split('T')[0], end_date: endStr };
    }
    if (datePreset === 'custom') {
      return {
        start_date: startDate || undefined,
        end_date: endDate || undefined,
      };
    }
    return { start_date: undefined, end_date: undefined };
  }, [datePreset, startDate, endDate]);

  // Load Dropdown Metadata
  useEffect(() => {
    Promise.allSettled([
      listCampaigns({ page: 1, size: 50 }),
      listSegments({ page: 1, size: 50 }),
    ]).then(([campRes, segRes]) => {
      if (campRes.status === 'fulfilled' && campRes.value?.items) {
        setCampaignOptions(campRes.value.items);
      }
      if (segRes.status === 'fulfilled' && segRes.value?.items) {
        setSegmentOptions(segRes.value.items);
      }
    });
  }, []);

  // Fetch Analytics Data
  const loadAnalytics = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const dateParams = resolveDateParams();
      const params = {
        ...dateParams,
        campaign_id: selectedCampaign || undefined,
        channel: selectedChannel || undefined,
        language: selectedLanguage || undefined,
        segment_id: selectedSegment || undefined,
      };

      const [kpiRes, trendsRes, breakdownRes, funnelRes, insightsRes] = await Promise.all([
        getAnalyticsKPIs(params),
        getAnalyticsTrends(params),
        getAnalyticsBreakdowns(params),
        getAnalyticsFunnel(params),
        getAnalyticsInsights(params),
      ]);

      setKpis(kpiRes);
      setTrends(trendsRes);
      setBreakdowns(breakdownRes);
      setFunnel(funnelRes);
      setInsights(insightsRes);
    } catch (err) {
      console.error('Failed to load analytics dashboard data:', err);
      setError(
        err.response?.data?.detail || 'Unable to aggregate analytics metrics. Please retry or adjust filters.'
      );
    } finally {
      setLoading(false);
    }
  }, [
    resolveDateParams,
    selectedCampaign,
    selectedChannel,
    selectedLanguage,
    selectedSegment,
  ]);

  useEffect(() => {
    loadAnalytics();
  }, [loadAnalytics]);

  // Reset Filters Handler
  const handleResetFilters = () => {
    setDatePreset('30d');
    setStartDate('');
    setEndDate('');
    setSelectedCampaign('');
    setSelectedChannel('');
    setSelectedLanguage('');
    setSelectedSegment('');
  };

  // Export Handlers
  const handleExportCsv = async () => {
    setExportingCsv(true);
    try {
      const dateParams = resolveDateParams();
      await downloadAnalyticsCSV({
        ...dateParams,
        campaign_id: selectedCampaign || undefined,
        channel: selectedChannel || undefined,
        language: selectedLanguage || undefined,
        segment_id: selectedSegment || undefined,
      });
    } catch (err) {
      console.error('Failed to export CSV:', err);
      alert('Failed to generate CSV export. Please try again.');
    } finally {
      setExportingCsv(false);
    }
  };

  const handleExportPdf = async () => {
    setExportingPdf(true);
    try {
      const dateParams = resolveDateParams();
      await downloadAnalyticsPDF({
        ...dateParams,
        campaign_id: selectedCampaign || undefined,
        channel: selectedChannel || undefined,
        language: selectedLanguage || undefined,
        segment_id: selectedSegment || undefined,
      });
    } catch (err) {
      console.error('Failed to export PDF:', err);
      alert('Failed to generate PDF executive report. Please try again.');
    } finally {
      setExportingPdf(false);
    }
  };

  // Trends Chart Math
  const chartPoints = useMemo(() => {
    if (!trends?.trends || trends.trends.length === 0) return [];
    return trends.trends;
  }, [trends]);

  const maxTrendValue = useMemo(() => {
    if (chartPoints.length === 0) return 10;
    let maxVal = 0;
    chartPoints.forEach((p) => {
      if (activeMetrics.sent && p.sent > maxVal) maxVal = p.sent;
      if (activeMetrics.delivered && p.delivered > maxVal) maxVal = p.delivered;
      if (activeMetrics.opens && p.opens > maxVal) maxVal = p.opens;
      if (activeMetrics.clicks && p.clicks > maxVal) maxVal = p.clicks;
      if (activeMetrics.replies && p.replies > maxVal) maxVal = p.replies;
    });
    return Math.max(maxVal * 1.15, 10);
  }, [chartPoints, activeMetrics]);

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
      {/* 1. Header & Actions Bar */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 border-b border-slate-200 pb-5">
        <div>
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center shadow-lg shadow-indigo-500/20">
              <BarChart3 className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="text-2xl font-bold tracking-tight text-slate-900 flex items-center gap-2">
                Civic Analytics & Intelligence
                <span className="text-xs font-semibold px-2.5 py-0.5 rounded-full bg-indigo-50 text-indigo-700 border border-indigo-200">
                  Milestone 3
                </span>
              </h1>
              <p className="text-sm text-slate-500">
                Cross-channel telemetry, citizen engagement, multilingual reach, and AI-driven recommendations.
              </p>
            </div>
          </div>
        </div>

        {/* Global Action Buttons */}
        <div className="flex flex-wrap items-center gap-2.5">
          <button
            onClick={loadAnalytics}
            disabled={loading}
            className="inline-flex items-center gap-2 px-3.5 py-2 text-sm font-medium rounded-lg bg-white hover:bg-slate-50 text-slate-700 hover:text-slate-900 border border-slate-300 shadow-sm transition"
            title="Refresh analytics data"
          >
            <RefreshCw className={`w-4 h-4 text-slate-500 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>

          <button
            onClick={handleExportCsv}
            disabled={exportingCsv || loading}
            className="inline-flex items-center gap-2 px-3.5 py-2 text-sm font-medium rounded-lg bg-emerald-50 hover:bg-emerald-100 text-emerald-700 border border-emerald-300 shadow-sm transition disabled:opacity-50"
            title="Export filtered data to CSV"
          >
            <FileSpreadsheet className="w-4 h-4 text-emerald-600" />
            {exportingCsv ? 'Generating CSV...' : 'Export CSV'}
          </button>

          <button
            onClick={handleExportPdf}
            disabled={exportingPdf || loading}
            className="inline-flex items-center gap-2 px-3.5 py-2 text-sm font-medium rounded-lg bg-purple-50 hover:bg-purple-100 text-purple-700 border border-purple-300 shadow-sm transition disabled:opacity-50"
            title="Export executive PDF report"
          >
            <FileText className="w-4 h-4 text-purple-600" />
            {exportingPdf ? 'Generating PDF...' : 'Export PDF'}
          </button>
        </div>
      </div>

      {/* 2. Global Filter Toolbar */}
      <div className="bg-white rounded-xl border border-slate-200 p-4 space-y-3 shadow-sm">
        <div className="flex items-center justify-between text-xs font-semibold uppercase tracking-wider text-slate-500 border-b border-slate-200 pb-2">
          <div className="flex items-center gap-2">
            <Filter className="w-3.5 h-3.5 text-indigo-600" />
            Dashboard Filters & Telemetry Scope
          </div>
          {(selectedCampaign || selectedChannel || selectedLanguage || selectedSegment || datePreset !== '30d') && (
            <button
              onClick={handleResetFilters}
              className="text-xs text-indigo-600 hover:text-indigo-800 flex items-center gap-1 transition"
            >
              <X className="w-3 h-3" />
              Reset Filters
            </button>
          )}
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-6 gap-3">
          {/* Date Presets */}
          <div className="space-y-1">
            <label className="text-xs font-medium text-slate-700">Time Window</label>
            <select
              value={datePreset}
              onChange={(e) => setDatePreset(e.target.value)}
              className="w-full bg-white text-slate-800 border border-slate-300 rounded-lg px-3 py-2 text-xs focus:ring-2 focus:ring-indigo-500 focus:outline-none"
            >
              <option value="7d">Last 7 Days</option>
              <option value="30d">Last 30 Days</option>
              <option value="90d">Last 90 Days</option>
              <option value="all">All Time</option>
              <option value="custom">Custom Date Range</option>
            </select>
          </div>

          {/* Campaign Selector */}
          <div className="space-y-1">
            <label className="text-xs font-medium text-slate-700">Campaign</label>
            <select
              value={selectedCampaign}
              onChange={(e) => setSelectedCampaign(e.target.value)}
              className="w-full bg-white text-slate-800 border border-slate-300 rounded-lg px-3 py-2 text-xs focus:ring-2 focus:ring-indigo-500 focus:outline-none truncate"
            >
              <option value="">All Campaigns</option>
              {campaignOptions.map((c) => (
                <option key={c.id} value={c.id}>
                  #{c.id} - {c.name}
                </option>
              ))}
            </select>
          </div>

          {/* Channel Selector */}
          <div className="space-y-1">
            <label className="text-xs font-medium text-slate-700">Channel</label>
            <select
              value={selectedChannel}
              onChange={(e) => setSelectedChannel(e.target.value)}
              className="w-full bg-white text-slate-800 border border-slate-300 rounded-lg px-3 py-2 text-xs focus:ring-2 focus:ring-indigo-500 focus:outline-none"
            >
              <option value="">All Channels</option>
              <option value="SMS">SMS</option>
              <option value="WhatsApp">WhatsApp</option>
              <option value="Email">Email</option>
              <option value="Push">Push Notifications</option>
              <option value="Web Broadcast">Web Broadcast</option>
            </select>
          </div>

          {/* Language Selector */}
          <div className="space-y-1">
            <label className="text-xs font-medium text-slate-700">Language</label>
            <select
              value={selectedLanguage}
              onChange={(e) => setSelectedLanguage(e.target.value)}
              className="w-full bg-white text-slate-800 border border-slate-300 rounded-lg px-3 py-2 text-xs focus:ring-2 focus:ring-indigo-500 focus:outline-none"
            >
              <option value="">All Languages</option>
              <option value="en">English (en)</option>
              <option value="hi">Hindi (hi)</option>
              <option value="ta">Tamil (ta)</option>
              <option value="te">Telugu (te)</option>
              <option value="mr">Marathi (mr)</option>
              <option value="kn">Kannada (kn)</option>
            </select>
          </div>

          {/* Audience Segment */}
          <div className="space-y-1">
            <label className="text-xs font-medium text-slate-700">Audience Segment</label>
            <select
              value={selectedSegment}
              onChange={(e) => setSelectedSegment(e.target.value)}
              className="w-full bg-white text-slate-800 border border-slate-300 rounded-lg px-3 py-2 text-xs focus:ring-2 focus:ring-indigo-500 focus:outline-none truncate"
            >
              <option value="">All Segments</option>
              {segmentOptions.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          </div>

          {/* Custom Date Pickers if enabled */}
          {datePreset === 'custom' ? (
            <div className="space-y-1">
              <label className="text-xs font-medium text-slate-700">Dates (From - To)</label>
              <div className="flex items-center gap-1">
                <input
                  type="date"
                  value={startDate}
                  onChange={(e) => setStartDate(e.target.value)}
                  className="w-1/2 bg-white text-slate-800 border border-slate-300 rounded-lg px-2 py-1.5 text-xs focus:ring-2 focus:ring-indigo-500"
                />
                <input
                  type="date"
                  value={endDate}
                  onChange={(e) => setEndDate(e.target.value)}
                  className="w-1/2 bg-white text-slate-800 border border-slate-300 rounded-lg px-2 py-1.5 text-xs focus:ring-2 focus:ring-indigo-500"
                />
              </div>
            </div>
          ) : (
            <div className="flex items-end">
              <div className="text-xs text-slate-600 bg-slate-50 rounded-lg p-2.5 w-full border border-slate-200 flex items-center gap-1.5">
                <Calendar className="w-3.5 h-3.5 text-indigo-600 shrink-0" />
                <span className="truncate">
                  {kpis?.total_campaigns || 0} active campaigns in scope
                </span>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Error Banner */}
      {error && (
        <div className="p-4 bg-rose-50 border border-rose-200 rounded-xl text-rose-800 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <AlertTriangle className="w-5 h-5 text-rose-600 shrink-0" />
            <p className="text-sm">{error}</p>
          </div>
          <button
            onClick={loadAnalytics}
            className="px-3 py-1 bg-rose-600 hover:bg-rose-700 text-white rounded text-xs font-semibold"
          >
            Retry
          </button>
        </div>
      )}

      {/* 3. Primary KPI Summary Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Messages Sent */}
        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm relative overflow-hidden">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Total Sent</span>
            <div className="w-8 h-8 rounded-lg bg-blue-50 text-blue-600 border border-blue-200 flex items-center justify-center">
              <Send className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-3xl font-extrabold text-slate-900">
              {loading ? '-' : (kpis?.total_messages_sent || 0).toLocaleString()}
            </span>
            <span className="text-xs text-slate-500">dispatches</span>
          </div>
          <div className="mt-2 text-xs text-slate-500 flex items-center gap-2">
            <span className="text-emerald-600 font-semibold">{kpis?.delivery_rate || 0}%</span> delivery rate
            <span className="text-slate-300">•</span>
            <span className="text-rose-600 font-medium">{kpis?.bounce_rate || 0}%</span> bounce
          </div>
        </div>

        {/* Total Reach */}
        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm relative overflow-hidden">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Total Citizen Reach</span>
            <div className="w-8 h-8 rounded-lg bg-emerald-50 text-emerald-600 border border-emerald-200 flex items-center justify-center">
              <CheckCircle2 className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-3xl font-extrabold text-slate-900">
              {loading ? '-' : (kpis?.total_reach || 0).toLocaleString()}
            </span>
            <span className="text-xs text-slate-500">unique citizens reached</span>
          </div>
          <div className="mt-2 text-xs text-slate-500 flex items-center gap-2">
            <span className="text-emerald-600 font-semibold">{(kpis?.total_delivered || 0).toLocaleString()}</span> total delivered
          </div>
        </div>

        {/* Open Rate */}
        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm relative overflow-hidden">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Average Open Rate</span>
            <div className="w-8 h-8 rounded-lg bg-indigo-50 text-indigo-600 border border-indigo-200 flex items-center justify-center">
              <Eye className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-3xl font-extrabold text-slate-900">
              {loading ? '-' : `${kpis?.average_open_rate || 0}%`}
            </span>
            <span className="text-xs text-slate-500">opens / delivered</span>
          </div>
          <div className="mt-2 text-xs text-slate-500 flex items-center gap-2">
            <span className="text-indigo-600 font-semibold">{kpis?.average_click_through_rate || 0}%</span> Click-Through (CTR)
          </div>
        </div>

        {/* Response & Feedback Rate */}
        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm relative overflow-hidden">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Citizen Response Rate</span>
            <div className="w-8 h-8 rounded-lg bg-purple-50 text-purple-600 border border-purple-200 flex items-center justify-center">
              <MessageSquare className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-3xl font-extrabold text-slate-900">
              {loading ? '-' : `${kpis?.response_rate || 0}%`}
            </span>
            <span className="text-xs text-slate-500">inbound replies</span>
          </div>
          <div className="mt-2 text-xs text-slate-500 flex items-center gap-2">
            <span className="text-purple-600 font-semibold">{kpis?.participation_rate || 0}%</span> feedback participation
          </div>
        </div>
      </div>

      {/* 4. Engagement Trends Over Time (Interactive Line Chart) */}
      <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div>
            <h2 className="text-base font-semibold text-slate-900 flex items-center gap-2">
              <TrendingUp className="w-4 h-4 text-indigo-600" />
              Engagement Trends Time-Series
            </h2>
            <p className="text-xs text-slate-500">
              Daily/periodic citizen telemetry: dispatches, deliveries, email opens, link clicks, and inbound responses.
            </p>
          </div>

          {/* Metric Toggle Buttons */}
          <div className="flex flex-wrap items-center gap-1.5">
            <button
              onClick={() => setActiveMetrics((m) => ({ ...m, sent: !m.sent }))}
              className={`px-2.5 py-1 text-xs rounded-full border transition flex items-center gap-1.5 ${
                activeMetrics.sent
                  ? 'bg-blue-50 text-blue-700 border-blue-300 font-medium'
                  : 'bg-slate-100 text-slate-500 border-slate-200 opacity-70 hover:bg-slate-200'
              }`}
            >
              <span className="w-2 h-2 rounded-full bg-blue-600" />
              Sent
            </button>
            <button
              onClick={() => setActiveMetrics((m) => ({ ...m, delivered: !m.delivered }))}
              className={`px-2.5 py-1 text-xs rounded-full border transition flex items-center gap-1.5 ${
                activeMetrics.delivered
                  ? 'bg-emerald-50 text-emerald-700 border-emerald-300 font-medium'
                  : 'bg-slate-100 text-slate-500 border-slate-200 opacity-70 hover:bg-slate-200'
              }`}
            >
              <span className="w-2 h-2 rounded-full bg-emerald-600" />
              Delivered
            </button>
            <button
              onClick={() => setActiveMetrics((m) => ({ ...m, opens: !m.opens }))}
              className={`px-2.5 py-1 text-xs rounded-full border transition flex items-center gap-1.5 ${
                activeMetrics.opens
                  ? 'bg-indigo-50 text-indigo-700 border-indigo-300 font-medium'
                  : 'bg-slate-100 text-slate-500 border-slate-200 opacity-70 hover:bg-slate-200'
              }`}
            >
              <span className="w-2 h-2 rounded-full bg-indigo-600" />
              Opens
            </button>
            <button
              onClick={() => setActiveMetrics((m) => ({ ...m, clicks: !m.clicks }))}
              className={`px-2.5 py-1 text-xs rounded-full border transition flex items-center gap-1.5 ${
                activeMetrics.clicks
                  ? 'bg-amber-50 text-amber-700 border-amber-300 font-medium'
                  : 'bg-slate-100 text-slate-500 border-slate-200 opacity-70 hover:bg-slate-200'
              }`}
            >
              <span className="w-2 h-2 rounded-full bg-amber-600" />
              Clicks
            </button>
            <button
              onClick={() => setActiveMetrics((m) => ({ ...m, replies: !m.replies }))}
              className={`px-2.5 py-1 text-xs rounded-full border transition flex items-center gap-1.5 ${
                activeMetrics.replies
                  ? 'bg-purple-50 text-purple-700 border-purple-300 font-medium'
                  : 'bg-slate-100 text-slate-500 border-slate-200 opacity-70 hover:bg-slate-200'
              }`}
            >
              <span className="w-2 h-2 rounded-full bg-purple-600" />
              Replies
            </button>
          </div>
        </div>

        {/* SVG Line Chart */}
        <div className="relative h-64 w-full pt-4">
          {chartPoints.length === 0 ? (
            <div className="h-full flex items-center justify-center text-xs text-slate-400">
              No trend telemetry recorded in the selected window.
            </div>
          ) : (
            <svg
              className="w-full h-full overflow-visible"
              viewBox={`0 0 ${chartPoints.length * 60} 200`}
              preserveAspectRatio="none"
            >
              {/* Background Grid Lines */}
              {[0, 50, 100, 150].map((y) => (
                <line
                  key={y}
                  x1="0"
                  y1={y}
                  x2={chartPoints.length * 60}
                  y2={y}
                  stroke="#e2e8f0"
                  strokeDasharray="3 3"
                  strokeWidth="0.8"
                />
              ))}

              {/* Render Trend Lines */}
              {activeMetrics.sent && (
                <polyline
                  fill="none"
                  stroke="#2563eb"
                  strokeWidth="2.5"
                  points={chartPoints
                    .map((p, i) => `${i * 60 + 30},${190 - (p.sent / maxTrendValue) * 170}`)
                    .join(' ')}
                />
              )}
              {activeMetrics.delivered && (
                <polyline
                  fill="none"
                  stroke="#10b981"
                  strokeWidth="2.5"
                  points={chartPoints
                    .map((p, i) => `${i * 60 + 30},${190 - (p.delivered / maxTrendValue) * 170}`)
                    .join(' ')}
                />
              )}
              {activeMetrics.opens && (
                <polyline
                  fill="none"
                  stroke="#6366f1"
                  strokeWidth="2.5"
                  points={chartPoints
                    .map((p, i) => `${i * 60 + 30},${190 - (p.opens / maxTrendValue) * 170}`)
                    .join(' ')}
                />
              )}
              {activeMetrics.clicks && (
                <polyline
                  fill="none"
                  stroke="#f59e0b"
                  strokeWidth="2.5"
                  points={chartPoints
                    .map((p, i) => `${i * 60 + 30},${190 - (p.clicks / maxTrendValue) * 170}`)
                    .join(' ')}
                />
              )}
              {activeMetrics.replies && (
                <polyline
                  fill="none"
                  stroke="#a855f7"
                  strokeWidth="2.5"
                  points={chartPoints
                    .map((p, i) => `${i * 60 + 30},${190 - (p.replies / maxTrendValue) * 170}`)
                    .join(' ')}
                />
              )}

              {/* Interactive Hover Circles and Click Targets */}
              {chartPoints.map((p, i) => {
                const x = i * 60 + 30;
                return (
                  <g key={p.date} className="cursor-pointer">
                    <rect
                      x={x - 25}
                      y="0"
                      width="50"
                      height="200"
                      fill="transparent"
                      onMouseEnter={() => setHoveredTrendPoint({ ...p, x })}
                      onMouseLeave={() => setHoveredTrendPoint(null)}
                    />
                    {hoveredTrendPoint?.date === p.date && (
                      <line x1={x} y1="0" x2={x} y2="190" stroke="#94a3b8" strokeWidth="1" strokeDasharray="2 2" />
                    )}
                    {activeMetrics.delivered && (
                      <circle
                        cx={x}
                        cy={190 - (p.delivered / maxTrendValue) * 170}
                        r="4"
                        fill="#10b981"
                        stroke="#ffffff"
                        strokeWidth="2"
                      />
                    )}
                  </g>
                );
              })}
            </svg>
          )}

          {/* Hover Tooltip Box */}
          {hoveredTrendPoint && (
            <div
              className="absolute top-2 bg-white border border-slate-200 text-xs rounded-lg p-2.5 shadow-lg pointer-events-none z-10 space-y-1"
              style={{
                left: `${Math.min(Math.max(10, (hoveredTrendPoint.x / (chartPoints.length * 60)) * 100), 80)}%`,
              }}
            >
              <div className="font-semibold text-slate-800 border-b border-slate-100 pb-1">
                {hoveredTrendPoint.date}
              </div>
              <div className="grid grid-cols-2 gap-x-3 gap-y-0.5 text-slate-600">
                <span className="text-blue-600 font-medium">Sent:</span> <span className="font-semibold text-slate-800">{hoveredTrendPoint.sent}</span>
                <span className="text-emerald-600 font-medium">Delivered:</span> <span className="font-semibold text-slate-800">{hoveredTrendPoint.delivered}</span>
                <span className="text-indigo-600 font-medium">Opens:</span> <span className="font-semibold text-slate-800">{hoveredTrendPoint.opens}</span>
                <span className="text-amber-600 font-medium">Clicks:</span> <span className="font-semibold text-slate-800">{hoveredTrendPoint.clicks}</span>
                <span className="text-purple-600 font-medium">Replies:</span> <span className="font-semibold text-slate-800">{hoveredTrendPoint.replies}</span>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* 5. Channel Performance Breakdown & Conversion Funnel */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Channel Comparison */}
        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-semibold text-slate-900 flex items-center gap-2">
              <Radio className="w-4 h-4 text-emerald-600" />
              Channel Effectiveness Breakdown
            </h2>
            <span className="text-xs text-slate-500 font-medium">5 Delivery Channels</span>
          </div>

          <div className="space-y-3">
            {Object.entries(breakdowns?.by_channel || {}).map(([chName, chData]) => (
              <div key={chName} className="p-3 bg-slate-50 rounded-lg border border-slate-200 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-semibold text-slate-900">{chName}</span>
                  <div className="flex items-center gap-2 text-xs">
                    <span className="text-slate-500">{chData.sent} sent</span>
                    <span className="text-slate-300">•</span>
                    <span className="text-emerald-600 font-medium">{chData.delivery_rate}% delivered</span>
                  </div>
                </div>

                {/* Progress bar */}
                <div className="w-full bg-slate-200 rounded-full h-2 overflow-hidden flex">
                  <div
                    className="bg-emerald-500 h-full"
                    style={{ width: `${Math.min(chData.delivery_rate, 100)}%` }}
                  />
                  <div
                    className="bg-rose-400 h-full"
                    style={{ width: `${Math.min(100 - chData.delivery_rate, 100)}%` }}
                  />
                </div>

                <div className="grid grid-cols-3 text-xs text-slate-500 pt-1">
                  <div>
                    Open Rate: <span className="text-indigo-600 font-medium">{chData.open_rate}%</span>
                  </div>
                  <div>
                    CTR: <span className="text-amber-600 font-medium">{chData.ctr}%</span>
                  </div>
                  <div>
                    Replies: <span className="text-purple-600 font-medium">{chData.replies}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* 5-Stage Conversion Funnel */}
        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-semibold text-slate-900 flex items-center gap-2">
              <Layers className="w-4 h-4 text-purple-600" />
              Campaign Conversion Funnel
            </h2>
            <span className="text-xs px-2.5 py-0.5 rounded-full bg-purple-50 text-purple-700 border border-purple-200 font-medium">
              End-to-End: {funnel?.overall_conversion_rate || 0}%
            </span>
          </div>

          <div className="space-y-3">
            {funnel?.stages?.map((stage, idx) => {
              const colors = [
                'bg-blue-500',
                'bg-emerald-500',
                'bg-indigo-500',
                'bg-amber-500',
                'bg-purple-500',
              ];
              const barColor = colors[idx % colors.length];

              return (
                <div key={stage.stage} className="p-3 bg-slate-50 rounded-lg border border-slate-200 space-y-1.5">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-semibold text-slate-800 flex items-center gap-2">
                      <span className="w-5 h-5 rounded-full bg-slate-200 text-slate-700 text-xs flex items-center justify-center font-bold">
                        {idx + 1}
                      </span>
                      {stage.stage}
                    </span>
                    <span className="text-sm font-bold text-slate-900">{stage.count.toLocaleString()}</span>
                  </div>

                  {/* Relative bar width */}
                  <div className="w-full bg-slate-200 rounded-full h-2 overflow-hidden">
                    <div
                      className={`${barColor} h-full transition-all duration-500`}
                      style={{ width: `${Math.min(stage.conversion_from_top, 100)}%` }}
                    />
                  </div>

                  <div className="flex items-center justify-between text-xs text-slate-500 pt-0.5">
                    <span>
                      From Top: <span className="text-slate-700 font-medium">{stage.conversion_from_top}%</span>
                    </span>
                    {idx > 0 && (
                      <span>
                        Step Dropoff: <span className="text-rose-600 font-medium">{stage.dropoff_rate}%</span>
                      </span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* 6. Language-wise Analytics Table & Sentiment Distribution */}
      <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-semibold text-slate-900 flex items-center gap-2">
            <Globe className="w-4 h-4 text-teal-600" />
            Multilingual Engagement & Sentiment Matrix
          </h2>
          <span className="text-xs text-slate-500 font-medium">Language Equity Monitoring</span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-slate-700">
            <thead className="bg-slate-50 uppercase tracking-wider text-slate-500 border-b border-slate-200">
              <tr>
                <th className="py-3 px-4 font-semibold">Language</th>
                <th className="py-3 px-4 font-semibold">Messages</th>
                <th className="py-3 px-4 font-semibold">Delivered</th>
                <th className="py-3 px-4 font-semibold">Open Rate</th>
                <th className="py-3 px-4 font-semibold">CTR</th>
                <th className="py-3 px-4 font-semibold">Response Rate</th>
                <th className="py-3 px-4 font-semibold">Sentiment Split</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {Object.entries(breakdowns?.by_language || {}).map(([lCode, lData]) => {
                const langLabels = {
                  en: 'English (en)',
                  hi: 'Hindi (hi)',
                  ta: 'Tamil (ta)',
                  te: 'Telugu (te)',
                  mr: 'Marathi (mr)',
                  kn: 'Kannada (kn)',
                };
                const langName = langLabels[lCode] || lCode.toUpperCase();
                const totalFb =
                  (lData.sentiment_distribution?.Positive || 0) +
                  (lData.sentiment_distribution?.Neutral || 0) +
                  (lData.sentiment_distribution?.Negative || 0);

                return (
                  <tr key={lCode} className="hover:bg-slate-50/80 transition">
                    <td className="py-3 px-4 font-semibold text-slate-900">{langName}</td>
                    <td className="py-3 px-4 text-slate-600">{lData.messages}</td>
                    <td className="py-3 px-4 text-slate-600">{lData.delivered}</td>
                    <td className="py-3 px-4 text-indigo-600 font-medium">{lData.open_rate}%</td>
                    <td className="py-3 px-4 text-amber-600 font-medium">{lData.ctr}%</td>
                    <td className="py-3 px-4 text-purple-600 font-medium">{lData.response_rate}%</td>
                    <td className="py-3 px-4">
                      {totalFb > 0 ? (
                        <div className="flex items-center gap-1.5 text-xs">
                          <span className="px-1.5 py-0.5 rounded bg-emerald-50 text-emerald-700 border border-emerald-200 font-medium">
                            +{lData.sentiment_distribution?.Positive || 0}
                          </span>
                          <span className="px-1.5 py-0.5 rounded bg-slate-100 text-slate-700 border border-slate-200 font-medium">
                            ~{lData.sentiment_distribution?.Neutral || 0}
                          </span>
                          <span className="px-1.5 py-0.5 rounded bg-rose-50 text-rose-700 border border-rose-200 font-medium">
                            -{lData.sentiment_distribution?.Negative || 0}
                          </span>
                        </div>
                      ) : (
                        <span className="text-slate-400">No feedback yet</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* 7. Audience Segment Performance & Campaign Rankings */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Top Performing Campaigns */}
        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm space-y-4">
          <h2 className="text-base font-semibold text-slate-900 flex items-center gap-2">
            <ThumbsUp className="w-4 h-4 text-emerald-600" />
            Top Ranked Campaigns
          </h2>
          <div className="space-y-2.5">
            {breakdowns?.best_performing?.length > 0 ? (
              breakdowns.best_performing.map((c, i) => (
                <div
                  key={c.campaign_id}
                  className="p-3 bg-slate-50 rounded-lg border border-slate-200 flex items-center justify-between"
                >
                  <div className="space-y-0.5">
                    <div className="text-sm font-semibold text-slate-900 flex items-center gap-2">
                      <span className="w-5 h-5 rounded-full bg-emerald-100 text-emerald-700 border border-emerald-300 text-xs flex items-center justify-center font-bold">
                        #{i + 1}
                      </span>
                      {c.campaign_name}
                    </div>
                    <div className="text-xs text-slate-500 flex items-center gap-2">
                      <span>{c.delivered} delivered</span>
                      <span className="text-slate-300">•</span>
                      <span className="text-indigo-600 font-medium">Open: {c.open_rate}%</span>
                      <span className="text-slate-300">•</span>
                      <span className="text-amber-600 font-medium">CTR: {c.ctr}%</span>
                    </div>
                  </div>
                  <span className="text-xs px-2.5 py-1 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200 font-semibold">
                    Score: {c.engagement_score}
                  </span>
                </div>
              ))
            ) : (
              <div className="text-xs text-slate-400 py-4 text-center">No ranked campaign activity recorded.</div>
            )}
          </div>
        </div>

        {/* Attention Needed / Low Engagement Campaigns */}
        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm space-y-4">
          <h2 className="text-base font-semibold text-slate-900 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-amber-600" />
            Campaigns Requiring Attention
          </h2>
          <div className="space-y-2.5">
            {breakdowns?.worst_performing?.length > 0 ? (
              breakdowns.worst_performing.map((c) => (
                <div
                  key={c.campaign_id}
                  className="p-3 bg-slate-50 rounded-lg border border-slate-200 flex items-center justify-between"
                >
                  <div className="space-y-0.5">
                    <div className="text-sm font-semibold text-slate-900">{c.campaign_name}</div>
                    <div className="text-xs text-slate-500 flex items-center gap-2">
                      <span>{c.delivered} delivered</span>
                      <span className="text-slate-300">•</span>
                      <span className="text-rose-600 font-medium">Open: {c.open_rate}%</span>
                      <span className="text-slate-300">•</span>
                      <span className="text-slate-600">Response: {c.response_rate}%</span>
                    </div>
                  </div>
                  <span className="text-xs px-2.5 py-1 rounded-full bg-amber-50 text-amber-700 border border-amber-200 font-semibold">
                    Score: {c.engagement_score}
                  </span>
                </div>
              ))
            ) : (
              <div className="text-xs text-slate-400 py-4 text-center">No campaign distress detected.</div>
            )}
          </div>
        </div>
      </div>

      {/* 8. AI / Rules-Based Actionable Insights */}
      <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-semibold text-slate-900 flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-purple-600" />
            AI & Rules-Based Actionable Insights
          </h2>
          <span className="text-xs text-slate-500 font-mono">
            Engine: {insights?.generation_method || 'rules_engine_fallback'}
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {insights?.insights?.map((ins) => {
            const badgeStyles = {
              positive: 'bg-emerald-50 text-emerald-700 border-emerald-200',
              warning: 'bg-amber-50 text-amber-700 border-amber-200',
              info: 'bg-blue-50 text-blue-700 border-blue-200',
              recommendation: 'bg-purple-50 text-purple-700 border-purple-200',
            }[ins.type] || 'bg-slate-100 text-slate-700 border-slate-200';

            return (
              <div
                key={ins.id}
                className="p-4 bg-slate-50 rounded-xl border border-slate-200 space-y-2.5 flex flex-col justify-between"
              >
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-sm font-semibold text-slate-900">{ins.title}</span>
                    <span className={`text-[10px] font-bold uppercase px-2 py-0.5 rounded-full border ${badgeStyles}`}>
                      {ins.type}
                    </span>
                  </div>
                  <p className="text-xs text-slate-600 leading-relaxed">{ins.description}</p>
                </div>

                <div className="space-y-1.5 pt-2 border-t border-slate-200 text-xs">
                  {ins.evidence && (
                    <div className="text-slate-600 flex items-start gap-1.5">
                      <span className="font-semibold text-slate-700 shrink-0">Evidence:</span>
                      <span>{ins.evidence}</span>
                    </div>
                  )}
                  {ins.recommendation && (
                    <div className="text-indigo-700 flex items-start gap-1.5">
                      <span className="font-semibold text-indigo-800 shrink-0">Action:</span>
                      <span>{ins.recommendation}</span>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
