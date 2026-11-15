import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Link } from 'react-router-dom';
import {
  SendHorizontal,
  Server,
  Activity,
  CheckCircle2,
  AlertTriangle,
  AlertCircle,
  Clock,
  RotateCw,
  Search,
  Filter,
  RefreshCw,
  XCircle,
  Copy,
  Check,
  ChevronLeft,
  ChevronRight,
  ShieldCheck,
  ExternalLink,
  Smartphone,
  Mail,
  MessageSquare,
  Volume2,
  Globe,
  Loader2,
  Eye,
  Terminal,
  ShieldAlert,
} from 'lucide-react';
import {
  getDistributionMetrics,
  listDistributionJobs,
  getDistributionJob,
  listJobDeliveries,
  processDistributionJob,
  retryDistributionJob,
  cancelDistributionJob,
} from '../../services/distributionService';
import { useAuth } from '../../context/AuthContext';

const CHANNEL_ICONS = {
  Email: <Mail className="w-3.5 h-3.5 text-blue-600" />,
  SMS: <Smartphone className="w-3.5 h-3.5 text-emerald-600" />,
  WhatsApp: <MessageSquare className="w-3.5 h-3.5 text-emerald-500" />,
  Voice: <Volume2 className="w-3.5 h-3.5 text-indigo-500" />,
  Web: <Globe className="w-3.5 h-3.5 text-sky-500" />,
};

export default function DistributionDashboardPage() {
  const { user } = useAuth();
  const isOperator = user?.role?.name === 'Admin' || user?.role?.name === 'Campaign Manager';

  // Metrics State
  const [metrics, setMetrics] = useState(null);
  const [metricsLoading, setMetricsLoading] = useState(true);
  const [metricsError, setMetricsError] = useState(null);

  // Jobs State
  const [jobs, setJobs] = useState([]);
  const [jobsLoading, setJobsLoading] = useState(true);
  const [totalJobs, setTotalJobs] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(10);
  const [statusFilter, setStatusFilter] = useState('');
  const [channelFilter, setChannelFilter] = useState('');
  const [searchQuery, setSearchQuery] = useState('');

  // Auto-refresh state
  const [autoRefresh, setAutoRefresh] = useState(true);
  const refreshTimerRef = useRef(null);

  // Job Details / Deliveries Modal State
  const [selectedJob, setSelectedJob] = useState(null);
  const [modalLoading, setModalLoading] = useState(false);
  const [modalDeliveries, setModalDeliveries] = useState([]);
  const [modalDeliveryFilter, setModalDeliveryFilter] = useState('');
  const [modalSearch, setModalSearch] = useState('');
  const [modalDeliveryPage, setModalDeliveryPage] = useState(1);
  const [modalTotalDeliveries, setModalTotalDeliveries] = useState(0);
  const [modalActionLoading, setModalActionLoading] = useState(false);
  const [modalNotification, setModalNotification] = useState(null);

  // Copied CLI command state
  const [copiedSnippet, setCopiedSnippet] = useState(false);

  // Fetch Metrics
  const fetchMetrics = useCallback(async () => {
    try {
      const data = await getDistributionMetrics();
      setMetrics(data);
      setMetricsError(null);
    } catch (err) {
      console.error('Failed to load metrics:', err);
      setMetricsError('Unable to load queue processing metrics. Verify database and API connectivity.');
    } finally {
      setMetricsLoading(false);
    }
  }, []);

  // Fetch Jobs List
  const fetchJobs = useCallback(async () => {
    setJobsLoading(true);
    try {
      const res = await listDistributionJobs({
        page,
        size: pageSize,
        status: statusFilter || undefined,
        channel: channelFilter || undefined,
      });
      setJobs(res?.items || []);
      setTotalJobs(res?.total || 0);
    } catch (err) {
      console.error('Failed to load distribution jobs:', err);
    } finally {
      setJobsLoading(false);
    }
  }, [page, pageSize, statusFilter, channelFilter]);

  // Fetch Specific Job Deliveries for Modal
  const fetchJobDeliveries = useCallback(async (jobId, targetPage = 1) => {
    if (!jobId) return;
    setModalLoading(true);
    try {
      const res = await listJobDeliveries(jobId, {
        page: targetPage,
        size: 15,
        status: modalDeliveryFilter || undefined,
        search: modalSearch.trim() || undefined,
      });
      setModalDeliveries(res?.items || []);
      setModalTotalDeliveries(res?.total || 0);
      setModalDeliveryPage(targetPage);
    } catch (err) {
      console.error('Failed to load deliveries for job:', err);
    } finally {
      setModalLoading(false);
    }
  }, [modalDeliveryFilter, modalSearch]);

  // Initial Data Load
  useEffect(() => {
    fetchMetrics();
    fetchJobs();
  }, [fetchMetrics, fetchJobs]);

  // Auto-refresh interval (every 8 seconds when enabled)
  useEffect(() => {
    if (autoRefresh) {
      refreshTimerRef.current = setInterval(() => {
        fetchMetrics();
        fetchJobs();
        if (selectedJob?.job_id) {
          getDistributionJob(selectedJob.job_id).then((refreshed) => {
            setSelectedJob(refreshed);
          });
          fetchJobDeliveries(selectedJob.job_id, modalDeliveryPage);
        }
      }, 8000);
    }
    return () => {
      if (refreshTimerRef.current) clearInterval(refreshTimerRef.current);
    };
  }, [autoRefresh, fetchMetrics, fetchJobs, selectedJob?.job_id, fetchJobDeliveries, modalDeliveryPage]);

  // Modal Deliveries query effect
  useEffect(() => {
    if (selectedJob?.job_id) {
      fetchJobDeliveries(selectedJob.job_id, 1);
    }
  }, [fetchJobDeliveries, selectedJob?.job_id, modalDeliveryFilter, modalSearch]);

  const handleOpenJobDetails = async (job) => {
    setSelectedJob(job);
    setModalDeliveryFilter('');
    setModalSearch('');
    setModalDeliveryPage(1);
    setModalNotification(null);
    fetchJobDeliveries(job.job_id, 1);
  };

  const handleManualProcess = async (jobUuid) => {
    if (!isOperator) return;
    setModalActionLoading(true);
    setModalNotification(null);
    try {
      const processed = await processDistributionJob(jobUuid);
      setSelectedJob(processed);
      setModalNotification({
        type: 'success',
        message: `Simulation execution finished! ${processed.delivered_recipients} delivered, ${processed.skipped_recipients} skipped, ${processed.failed_recipients} failed.`,
      });
      fetchMetrics();
      fetchJobs();
      fetchJobDeliveries(jobUuid, 1);
    } catch (err) {
      setModalNotification({
        type: 'error',
        message: err.response?.data?.detail || 'Manual dispatch simulation failed.',
      });
    } finally {
      setModalActionLoading(false);
    }
  };

  const handleRetryJob = async (jobUuid) => {
    if (!isOperator) return;
    if (!window.confirm('Retry all eligible failed deliveries for this job? (Excludes permanent errors)')) return;
    setModalActionLoading(true);
    setModalNotification(null);
    try {
      const retried = await retryDistributionJob(jobUuid);
      setSelectedJob(retried);
      setModalNotification({
        type: 'success',
        message: 'Eligible failed records re-queued and processed successfully.',
      });
      fetchMetrics();
      fetchJobs();
      fetchJobDeliveries(jobUuid, 1);
    } catch (err) {
      setModalNotification({
        type: 'error',
        message: err.response?.data?.detail || 'Retry failed.',
      });
    } finally {
      setModalActionLoading(false);
    }
  };

  const handleCancelJob = async (jobUuid) => {
    if (!isOperator) return;
    if (!window.confirm('Cancel this distribution job? Pending deliveries will not be dispatched.')) return;
    setModalActionLoading(true);
    setModalNotification(null);
    try {
      const cancelled = await cancelDistributionJob(jobUuid);
      setSelectedJob(cancelled);
      setModalNotification({
        type: 'success',
        message: 'Distribution job and pending deliveries cancelled successfully.',
      });
      fetchMetrics();
      fetchJobs();
      fetchJobDeliveries(jobUuid, 1);
    } catch (err) {
      setModalNotification({
        type: 'error',
        message: err.response?.data?.detail || 'Failed to cancel job.',
      });
    } finally {
      setModalActionLoading(false);
    }
  };

  const copyWorkerSnippet = () => {
    navigator.clipboard.writeText('PYTHONPATH=backend python -m app.workers.distribution_worker --one-shot');
    setCopiedSnippet(true);
    setTimeout(() => setCopiedSnippet(false), 2000);
  };

  const getStatusBadge = (status) => {
    switch (status) {
      case 'completed':
        return 'bg-emerald-100 text-emerald-800 border-emerald-300';
      case 'completed_with_errors':
        return 'bg-amber-100 text-amber-800 border-amber-300';
      case 'failed':
        return 'bg-rose-100 text-rose-800 border-rose-300';
      case 'processing':
        return 'bg-sky-100 text-sky-800 border-sky-300 animate-pulse';
      case 'queued':
        return 'bg-blue-100 text-blue-800 border-blue-300';
      case 'pending':
        return 'bg-slate-100 text-slate-700 border-slate-300';
      case 'cancelled':
      default:
        return 'bg-slate-100 text-slate-600 border-slate-200';
    }
  };

  const getDeliveryStatusBadge = (st) => {
    switch (st) {
      case 'delivered':
        return 'bg-emerald-100 text-emerald-800 border-emerald-200';
      case 'failed':
        return 'bg-rose-100 text-rose-800 border-rose-200';
      case 'skipped_consent':
        return 'bg-amber-100 text-amber-800 border-amber-200';
      case 'retrying':
        return 'bg-orange-100 text-orange-800 border-orange-200';
      case 'processing':
        return 'bg-sky-100 text-sky-800 border-sky-200 animate-pulse';
      case 'cancelled':
        return 'bg-slate-100 text-slate-500 border-slate-200';
      case 'pending':
      default:
        return 'bg-slate-50 text-slate-600 border-slate-200';
    }
  };

  // Filtered jobs by search query
  const filteredJobs = jobs.filter((job) => {
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase();
    return (
      job.job_id.toLowerCase().includes(q) ||
      (job.campaign_name && job.campaign_name.toLowerCase().includes(q)) ||
      job.channel.toLowerCase().includes(q)
    );
  });

  const totalPages = Math.ceil(totalJobs / pageSize) || 1;

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8 font-sans">
      {/* Top Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 border-b border-slate-200 pb-4">
        <div>
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-blue-50 text-blue-600 border border-blue-100 flex items-center justify-center">
              <SendHorizontal className="w-5 h-5 text-blue-600" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
                Distribution Operations & Worker Health Dashboard
              </h1>
              <p className="text-sm text-slate-500 mt-0.5">
                Real-time queue monitoring, batch processing metrics, and delivery audit logs.
              </p>
            </div>
          </div>
        </div>

        {/* Global Controls & Refresh */}
        <div className="flex items-center gap-3 flex-wrap">
          <button
            type="button"
            onClick={() => setAutoRefresh(!autoRefresh)}
            className={`inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg border transition ${
              autoRefresh
                ? 'bg-emerald-50 text-emerald-800 border-emerald-200'
                : 'bg-slate-100 text-slate-600 border-slate-200'
            }`}
            title="Toggle live 8s auto-refresh polling"
          >
            <Activity className={`w-3.5 h-3.5 ${autoRefresh ? 'animate-pulse text-emerald-600' : 'text-slate-400'}`} />
            Auto-refresh: {autoRefresh ? 'Active (8s)' : 'Paused'}
          </button>

          <button
            type="button"
            onClick={() => {
              fetchMetrics();
              fetchJobs();
            }}
            disabled={jobsLoading || metricsLoading}
            className="inline-flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-semibold rounded-lg bg-white border border-slate-200 text-slate-700 hover:bg-slate-50 transition shadow-2xs disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${jobsLoading ? 'animate-spin' : ''}`} />
            Refresh
          </button>

          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-blue-50 border border-blue-200 text-blue-800 text-xs font-semibold">
            <ShieldCheck className="w-3.5 h-3.5 text-blue-700" />
            Simulated Safe Mode
          </div>
        </div>
      </div>

      {/* Safety Notice & Worker Engine Banner */}
      <div className="p-4 rounded-2xl bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 text-white shadow-sm space-y-3">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <Server className="w-4 h-4 text-sky-400" />
              <span className="text-xs font-bold uppercase tracking-wider text-sky-300">
                Database-Backed Queue Worker Engine
              </span>
              {metrics && metrics.active_workers_count > 0 ? (
                <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/40">
                  Worker Online ({metrics.active_workers_count} active)
                </span>
              ) : (
                <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/40">
                  Worker Daemon Inactive (Manual / Standalone Mode)
                </span>
              )}
            </div>
            <p className="text-xs text-slate-300 max-w-3xl leading-relaxed">
              When campaigns are queued, jobs wait safely in the PostgreSQL database. Run the independent worker daemon to process batches automatically, or manually trigger processing from the campaign view.
            </p>
          </div>

          {/* Quick Worker Command Snippet */}
          <div className="bg-slate-950/80 border border-slate-800 rounded-xl p-2.5 flex items-center justify-between gap-3 text-xs font-mono text-slate-300">
            <div className="flex items-center gap-2 truncate">
              <Terminal className="w-3.5 h-3.5 text-amber-400 flex-shrink-0" />
              <span className="truncate text-slate-400">
                PYTHONPATH=backend python -m app.workers.distribution_worker --one-shot
              </span>
            </div>
            <button
              type="button"
              onClick={copyWorkerSnippet}
              className="p-1 rounded hover:bg-slate-800 text-slate-400 hover:text-white transition flex-shrink-0"
              title="Copy worker CLI command"
            >
              {copiedSnippet ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
            </button>
          </div>
        </div>
      </div>

      {/* Metrics Error Banner */}
      {metricsError && (
        <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-center gap-2">
          <AlertCircle className="w-4 h-4 text-rose-600 flex-shrink-0" />
          <span>{metricsError}</span>
        </div>
      )}

      {/* Overview Metrics Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Card 1: Job Lifecycle */}
        <div className="bg-white rounded-2xl p-5 border border-slate-200 shadow-sm space-y-3">
          <div className="flex items-center justify-between text-xs font-bold text-slate-500 uppercase tracking-wider">
            <span>Jobs Lifecycle</span>
            <span className="text-slate-400 font-normal">All channels</span>
          </div>
          <div>
            <div className="text-3xl font-extrabold text-slate-900">
              {metricsLoading ? <Loader2 className="w-6 h-6 animate-spin text-slate-400" /> : metrics?.total_jobs ?? 0}
            </div>
            <span className="text-xs text-slate-500">Total Created Broadcast Jobs</span>
          </div>
          <div className="grid grid-cols-3 gap-1.5 pt-2 border-t border-slate-100 text-center text-[11px]">
            <div className="p-1 rounded bg-blue-50 text-blue-800 font-medium">
              <span className="font-bold block text-xs">{metrics?.queued_jobs ?? 0}</span>
              Queued
            </div>
            <div className="p-1 rounded bg-sky-50 text-sky-800 font-medium">
              <span className="font-bold block text-xs">{metrics?.processing_jobs ?? 0}</span>
              Processing
            </div>
            <div className="p-1 rounded bg-emerald-50 text-emerald-800 font-medium">
              <span className="font-bold block text-xs">{(metrics?.completed_jobs ?? 0) + (metrics?.completed_with_errors_jobs ?? 0)}</span>
              Finished
            </div>
          </div>
        </div>

        {/* Card 2: Deliveries Volume & Success Rate */}
        <div className="bg-white rounded-2xl p-5 border border-slate-200 shadow-sm space-y-3">
          <div className="flex items-center justify-between text-xs font-bold text-slate-500 uppercase tracking-wider">
            <span>Delivered Volume</span>
            <span className="text-slate-400 font-normal">Recipients</span>
          </div>
          <div>
            <div className="text-3xl font-extrabold text-emerald-600">
              {metricsLoading ? <Loader2 className="w-6 h-6 animate-spin text-slate-400" /> : metrics?.delivered_deliveries ?? 0}
            </div>
            <span className="text-xs text-slate-500">
              Out of {metrics?.total_delivery_records ?? 0} total recipients staged
            </span>
          </div>
          <div className="w-full bg-slate-100 rounded-full h-2 overflow-hidden mt-1">
            <div
              className="bg-emerald-500 h-2 rounded-full transition-all duration-500"
              style={{
                width: `${
                  metrics && metrics.total_delivery_records > 0
                    ? Math.round((metrics.delivered_deliveries / metrics.total_delivery_records) * 100)
                    : 0
                }%`,
              }}
            />
          </div>
          <div className="flex items-center justify-between text-[11px] text-slate-500 pt-0.5">
            <span>
              Success Rate:{' '}
              <strong>
                {metrics && metrics.total_delivery_records > 0
                  ? `${Math.round((metrics.delivered_deliveries / metrics.total_delivery_records) * 100)}%`
                  : 'N/A'}
              </strong>
            </span>
            <span>{metrics?.pending_deliveries ?? 0} pending</span>
          </div>
        </div>

        {/* Card 3: Consent & Exclusions */}
        <div className="bg-white rounded-2xl p-5 border border-slate-200 shadow-sm space-y-3">
          <div className="flex items-center justify-between text-xs font-bold text-slate-500 uppercase tracking-wider">
            <span>Safeguard Outcomes</span>
            <ShieldAlert className="w-3.5 h-3.5 text-amber-500" />
          </div>
          <div className="flex items-baseline gap-2">
            <div className="text-3xl font-extrabold text-amber-600">
              {metricsLoading ? <Loader2 className="w-6 h-6 animate-spin text-slate-400" /> : metrics?.skipped_consent_deliveries ?? 0}
            </div>
            <span className="text-xs text-amber-700 font-semibold">Consent Skipped</span>
          </div>
          <p className="text-[11px] text-slate-500">
            JIT opt-out or unconfirmed consent prevented broadcast prior to dispatch.
          </p>
          <div className="grid grid-cols-2 gap-1.5 pt-2 border-t border-slate-100 text-center text-[11px]">
            <div className="p-1 rounded bg-orange-50 text-orange-800 font-medium">
              <span className="font-bold block text-xs">{metrics?.retrying_deliveries ?? 0}</span>
              Retrying
            </div>
            <div className="p-1 rounded bg-rose-50 text-rose-800 font-medium">
              <span className="font-bold block text-xs">{metrics?.failed_deliveries ?? 0}</span>
              Permanent Fail
            </div>
          </div>
        </div>

        {/* Card 4: Worker Engine Health */}
        <div className="bg-white rounded-2xl p-5 border border-slate-200 shadow-sm space-y-3">
          <div className="flex items-center justify-between text-xs font-bold text-slate-500 uppercase tracking-wider">
            <span>Queue Health</span>
            <Server className="w-3.5 h-3.5 text-slate-400" />
          </div>
          <div>
            <div className="text-3xl font-extrabold text-slate-900">
              {metricsLoading ? <Loader2 className="w-6 h-6 animate-spin text-slate-400" /> : metrics?.active_workers_count ?? 0}
            </div>
            <span className="text-xs text-slate-500">Active Worker Leases</span>
          </div>
          <div className="space-y-1 pt-2 border-t border-slate-100 text-[11px] text-slate-600">
            <div className="flex justify-between">
              <span>Stale processing jobs:</span>
              <strong className={metrics?.stale_processing_jobs > 0 ? 'text-amber-600' : 'text-slate-800'}>
                {metrics?.stale_processing_jobs ?? 0}
              </strong>
            </div>
            <div className="flex justify-between">
              <span>Avg processing duration:</span>
              <strong className="text-slate-800">
                {metrics?.avg_processing_duration_seconds ? `${metrics.avg_processing_duration_seconds}s` : 'N/A'}
              </strong>
            </div>
          </div>
        </div>
      </div>

      {/* Main Jobs Section */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm space-y-4 p-6">
        {/* Table Filter Bar */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 border-b border-slate-100 pb-4">
          <div className="flex items-center gap-2">
            <h2 className="text-base font-bold text-slate-900">Distribution Jobs</h2>
            <span className="text-xs px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 font-mono">
              {totalJobs} total
            </span>
          </div>

          <div className="flex items-center gap-2 flex-wrap">
            {/* Search Input */}
            <div className="relative">
              <input
                type="text"
                placeholder="Search campaign or UUID..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-8 pr-3 py-1.5 text-xs rounded-xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-brand-500 w-48 sm:w-56"
              />
              <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-2.5" />
            </div>

            {/* Status Filter */}
            <select
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value);
                setPage(1);
              }}
              className="text-xs py-1.5 px-3 rounded-xl border border-slate-200 bg-white text-slate-700"
            >
              <option value="">All Statuses</option>
              <option value="queued">Queued</option>
              <option value="processing">Processing</option>
              <option value="completed">Completed</option>
              <option value="completed_with_errors">Completed with Errors</option>
              <option value="failed">Failed</option>
              <option value="cancelled">Cancelled</option>
            </select>

            {/* Channel Filter */}
            <select
              value={channelFilter}
              onChange={(e) => {
                setChannelFilter(e.target.value);
                setPage(1);
              }}
              className="text-xs py-1.5 px-3 rounded-xl border border-slate-200 bg-white text-slate-700"
            >
              <option value="">All Channels</option>
              <option value="Email">Email</option>
              <option value="SMS">SMS</option>
              <option value="WhatsApp">WhatsApp</option>
              <option value="Voice">Voice</option>
              <option value="Web">Web</option>
            </select>
          </div>
        </div>

        {/* Jobs Table */}
        <div className="overflow-x-auto border border-slate-200 rounded-xl">
          <table className="w-full text-left text-xs divide-y divide-slate-200">
            <thead className="bg-slate-50 text-[11px] font-bold text-slate-600 uppercase tracking-wider">
              <tr>
                <th className="px-4 py-3">Job ID</th>
                <th className="px-4 py-3">Campaign</th>
                <th className="px-4 py-3">Channel</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Progress / Counts</th>
                <th className="px-4 py-3">Created / Started</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 bg-white">
              {jobsLoading ? (
                <tr>
                  <td colSpan="7" className="p-8 text-center text-slate-400">
                    <Loader2 className="w-5 h-5 animate-spin mx-auto mb-2 text-brand-600" />
                    Loading distribution queue...
                  </td>
                </tr>
              ) : filteredJobs.length === 0 ? (
                <tr>
                  <td colSpan="7" className="p-8 text-center text-slate-400">
                    No distribution jobs found matching the selected criteria.
                  </td>
                </tr>
              ) : (
                filteredJobs.map((job) => (
                  <tr key={job.id} className="hover:bg-slate-50/70 transition">
                    <td className="px-4 py-3 font-mono font-semibold text-slate-800">
                      <span title={job.job_id}>#{job.job_id.slice(0, 8)}</span>
                    </td>
                    <td className="px-4 py-3">
                      <Link
                        to={`/campaigns/${job.campaign_id}`}
                        className="font-medium text-brand-600 hover:text-brand-800 hover:underline flex items-center gap-1"
                      >
                        {job.campaign_name || `Campaign #${job.campaign_id}`}
                        <ExternalLink className="w-3 h-3 text-slate-400" />
                      </Link>
                    </td>
                    <td className="px-4 py-3">
                      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-slate-100 text-slate-700 font-medium">
                        {CHANNEL_ICONS[job.channel]}
                        {job.channel}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`inline-block px-2.5 py-0.5 rounded-full text-[10px] font-bold border ${getStatusBadge(job.status)}`}>
                        {job.status}
                      </span>
                      {job.locked_by && (
                        <span className="block text-[10px] text-sky-600 font-mono mt-0.5">
                          lease: {job.locked_by.slice(0, 16)}...
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1.5 text-[11px] font-mono">
                        <span className="text-emerald-700 font-bold">{job.delivered_recipients} delivered</span>
                        {job.skipped_recipients > 0 && (
                          <span className="text-amber-700">({job.skipped_recipients} skipped)</span>
                        )}
                        {job.failed_recipients > 0 && (
                          <span className="text-rose-700 font-bold">({job.failed_recipients} failed)</span>
                        )}
                        <span className="text-slate-400">/ {job.eligible_recipients} total</span>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-slate-500 text-[11px]">
                      <div>{new Date(job.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</div>
                      <div className="text-[10px] text-slate-400">{new Date(job.created_at).toLocaleDateString()}</div>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button
                        type="button"
                        onClick={() => handleOpenJobDetails(job)}
                        className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-semibold bg-brand-50 text-brand-700 hover:bg-brand-100 transition"
                      >
                        <Eye className="w-3.5 h-3.5" />
                        Details
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination Bar */}
        <div className="flex items-center justify-between text-xs text-slate-500 pt-2">
          <span>
            Showing {jobs.length > 0 ? (page - 1) * pageSize + 1 : 0} to{' '}
            {Math.min(page * pageSize, totalJobs)} of {totalJobs} jobs
          </span>
          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={() => setPage(Math.max(1, page - 1))}
              disabled={page <= 1}
              className="p-1.5 rounded-lg border border-slate-200 hover:bg-slate-50 disabled:opacity-40"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <span className="px-3 py-1 font-semibold text-slate-700">
              {page} / {totalPages}
            </span>
            <button
              type="button"
              onClick={() => setPage(Math.min(totalPages, page + 1))}
              disabled={page >= totalPages}
              className="p-1.5 rounded-lg border border-slate-200 hover:bg-slate-50 disabled:opacity-40"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Selected Job Details & Delivery Records Modal */}
      {selectedJob && (
        <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-4xl w-full max-h-[90vh] flex flex-col shadow-2xl border border-slate-200 overflow-hidden">
            {/* Modal Header */}
            <div className="p-5 border-b border-slate-200 flex items-start justify-between bg-slate-50/50">
              <div>
                <div className="flex items-center gap-2">
                  <span className={`text-xs font-bold px-2.5 py-0.5 rounded-full border ${getStatusBadge(selectedJob.status)}`}>
                    {selectedJob.status}
                  </span>
                  <span className="text-xs font-mono text-slate-500">Job UUID: {selectedJob.job_id}</span>
                </div>
                <h3 className="text-lg font-bold text-slate-900 mt-1">
                  {selectedJob.campaign_name || `Campaign #${selectedJob.campaign_id}`} • {selectedJob.channel} Broadcast
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setSelectedJob(null)}
                className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition"
              >
                <XCircle className="w-5 h-5" />
              </button>
            </div>

            {/* Modal Notification */}
            {modalNotification && (
              <div
                className={`p-3 text-xs flex items-center gap-2 ${
                  modalNotification.type === 'success'
                    ? 'bg-emerald-50 text-emerald-800 border-b border-emerald-200'
                    : 'bg-rose-50 text-rose-800 border-b border-rose-200'
                }`}
              >
                {modalNotification.type === 'success' ? (
                  <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0" />
                ) : (
                  <AlertCircle className="w-4 h-4 text-rose-600 flex-shrink-0" />
                )}
                <span>{modalNotification.message}</span>
              </div>
            )}

            {/* Modal Body */}
            <div className="p-6 overflow-y-auto space-y-6 flex-grow">
              {/* Job Counters Grid */}
              <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 text-center">
                <div className="bg-slate-50 border border-slate-200 p-3 rounded-xl">
                  <span className="text-xl font-bold text-slate-900 block">{selectedJob.total_recipients}</span>
                  <span className="text-[10px] text-slate-500 uppercase font-semibold">Total Targeted</span>
                </div>
                <div className="bg-blue-50 border border-blue-200 p-3 rounded-xl">
                  <span className="text-xl font-bold text-blue-800 block">{selectedJob.queued_recipients}</span>
                  <span className="text-[10px] text-blue-700 uppercase font-semibold">Queued</span>
                </div>
                <div className="bg-emerald-50 border border-emerald-200 p-3 rounded-xl">
                  <span className="text-xl font-bold text-emerald-800 block">{selectedJob.delivered_recipients}</span>
                  <span className="text-[10px] text-emerald-700 uppercase font-semibold">Delivered</span>
                </div>
                <div className="bg-rose-50 border border-rose-200 p-3 rounded-xl">
                  <span className="text-xl font-bold text-rose-800 block">{selectedJob.failed_recipients}</span>
                  <span className="text-[10px] text-rose-700 uppercase font-semibold">Failed</span>
                </div>
                <div className="bg-amber-50 border border-amber-200 p-3 rounded-xl">
                  <span className="text-xl font-bold text-amber-800 block">{selectedJob.skipped_recipients}</span>
                  <span className="text-[10px] text-amber-700 uppercase font-semibold">Consent Skipped</span>
                </div>
              </div>

              {/* Progress Bar */}
              <div className="space-y-1">
                <div className="flex justify-between text-xs font-semibold text-slate-600">
                  <span>Broadcast Completion</span>
                  <span>
                    {selectedJob.eligible_recipients > 0
                      ? `${Math.round((selectedJob.delivered_recipients / selectedJob.eligible_recipients) * 100)}%`
                      : '0%'}
                  </span>
                </div>
                <div className="w-full bg-slate-100 rounded-full h-2.5 overflow-hidden">
                  <div
                    className="bg-emerald-500 h-2.5 rounded-full transition-all duration-500"
                    style={{
                      width: `${
                        selectedJob.eligible_recipients > 0
                          ? (selectedJob.delivered_recipients / selectedJob.eligible_recipients) * 100
                          : 0
                      }%`,
                    }}
                  />
                </div>
              </div>

              {/* Worker & Lease Information */}
              <div className="bg-slate-50 rounded-xl p-4 border border-slate-200 grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
                <div>
                  <span className="text-slate-400 block text-[11px]">Worker Lease:</span>
                  <strong className="font-mono text-slate-800">{selectedJob.locked_by || 'Unassigned / Released'}</strong>
                </div>
                <div>
                  <span className="text-slate-400 block text-[11px]">Recovery Count:</span>
                  <strong className="text-slate-800">{selectedJob.recovery_count} automated recoveries</strong>
                </div>
                <div>
                  <span className="text-slate-400 block text-[11px]">Completed At:</span>
                  <strong className="text-slate-800">
                    {selectedJob.completed_at ? new Date(selectedJob.completed_at).toLocaleString() : 'In Progress / Queued'}
                  </strong>
                </div>
              </div>

              {/* Operator Controls inside Modal */}
              {isOperator && (
                <div className="flex items-center gap-2 flex-wrap pt-2 border-t border-slate-100">
                  {['queued', 'pending'].includes(selectedJob.status) && (
                    <button
                      type="button"
                      onClick={() => handleManualProcess(selectedJob.job_id)}
                      disabled={modalActionLoading}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-brand-600 text-white text-xs font-bold hover:bg-brand-700 transition disabled:opacity-50"
                    >
                      {modalActionLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <SendHorizontal className="w-3.5 h-3.5" />}
                      Simulate Manual Dispatch
                    </button>
                  )}
                  {selectedJob.failed_recipients > 0 && (
                    <button
                      type="button"
                      onClick={() => handleRetryJob(selectedJob.job_id)}
                      disabled={modalActionLoading}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-amber-600 text-white text-xs font-bold hover:bg-amber-700 transition disabled:opacity-50"
                    >
                      <RotateCw className="w-3.5 h-3.5" />
                      Retry Eligible Failures
                    </button>
                  )}
                  {['queued', 'pending', 'processing'].includes(selectedJob.status) && (
                    <button
                      type="button"
                      onClick={() => handleCancelJob(selectedJob.job_id)}
                      disabled={modalActionLoading}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-rose-600 text-white text-xs font-bold hover:bg-rose-700 transition disabled:opacity-50"
                    >
                      <XCircle className="w-3.5 h-3.5" />
                      Cancel Job
                    </button>
                  )}
                </div>
              )}

              {/* Deliveries Audit Records Table */}
              <div className="space-y-3 pt-4 border-t border-slate-100">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div className="flex items-center gap-2">
                    <h4 className="text-xs font-bold text-slate-800 uppercase tracking-wider">
                      Audience Delivery Audit Logs ({modalTotalDeliveries})
                    </h4>
                  </div>

                  <div className="flex items-center gap-2">
                    <input
                      type="text"
                      placeholder="Filter address..."
                      value={modalSearch}
                      onChange={(e) => setModalSearch(e.target.value)}
                      className="px-2.5 py-1 text-xs rounded-lg border border-slate-200 focus:outline-none w-36"
                    />
                    <select
                      value={modalDeliveryFilter}
                      onChange={(e) => setModalDeliveryFilter(e.target.value)}
                      className="px-2 py-1 text-xs rounded-lg border border-slate-200 bg-white"
                    >
                      <option value="">All Outcomes</option>
                      <option value="delivered">Delivered</option>
                      <option value="skipped_consent">Skipped (Consent)</option>
                      <option value="retrying">Retrying</option>
                      <option value="failed">Failed</option>
                      <option value="pending">Pending</option>
                    </select>
                  </div>
                </div>

                <div className="border border-slate-200 rounded-xl overflow-hidden">
                  <table className="w-full text-left text-xs divide-y divide-slate-200">
                    <thead className="bg-slate-50 text-[11px] font-bold text-slate-600 uppercase tracking-wider">
                      <tr>
                        <th className="px-3.5 py-2">Recipient (Masked)</th>
                        <th className="px-3.5 py-2">Status</th>
                        <th className="px-3.5 py-2">Attempts</th>
                        <th className="px-3.5 py-2">Reference / Error</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 bg-white">
                      {modalLoading ? (
                        <tr>
                          <td colSpan="4" className="p-6 text-center text-slate-400">Loading delivery records...</td>
                        </tr>
                      ) : modalDeliveries.length === 0 ? (
                        <tr>
                          <td colSpan="4" className="p-6 text-center text-slate-400">No delivery records match filter.</td>
                        </tr>
                      ) : (
                        modalDeliveries.map((rec) => (
                          <tr key={rec.id} className="hover:bg-slate-50/50">
                            <td className="px-3.5 py-2">
                              <div className="font-semibold text-slate-900">{rec.recipient_name || `Recipient #${rec.audience_member_id}`}</div>
                              <div className="text-[11px] font-mono text-slate-500" title="Masked for privacy">
                                {rec.masked_recipient_address || '—'}
                              </div>
                            </td>
                            <td className="px-3.5 py-2">
                              <span className={`inline-block px-2 py-0.5 rounded-full text-[10px] font-bold border ${getDeliveryStatusBadge(rec.delivery_status)}`}>
                                {rec.delivery_status}
                              </span>
                            </td>
                            <td className="px-3.5 py-2 font-mono text-slate-600">
                              {rec.attempt_count} / {rec.max_attempts}
                            </td>
                            <td className="px-3.5 py-2 text-[11px]">
                              {rec.provider_reference && (
                                <span className="font-mono text-slate-600 truncate block max-w-xs">{rec.provider_reference}</span>
                              )}
                              {rec.error_code && (
                                <span className="text-rose-600 font-medium block">
                                  {rec.error_code}: {rec.error_message}
                                </span>
                              )}
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>

            {/* Modal Footer */}
            <div className="p-4 border-t border-slate-200 bg-slate-50 flex items-center justify-end">
              <button
                type="button"
                onClick={() => setSelectedJob(null)}
                className="px-4 py-2 text-xs font-semibold rounded-xl bg-white border border-slate-300 text-slate-700 hover:bg-slate-100 transition shadow-xs"
              >
                Close Details
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

