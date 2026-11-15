import React, { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import {
  SendHorizontal,
  CheckCircle2,
  AlertCircle,
  AlertTriangle,
  RotateCw,
  Clock,
  ShieldCheck,
  ShieldAlert,
  Users,
  Search,
  Filter,
  RefreshCw,
  XCircle,
  Smartphone,
  Mail,
  MessageSquare,
  Volume2,
  Globe,
  Loader2,
  ExternalLink,
  Info,
  Server,
  Play,
} from 'lucide-react';
import {
  getCampaignReadiness,
  createDistributionJob,
  listDistributionJobs,
  processDistributionJob,
  retryDistributionJob,
  cancelDistributionJob,
  listJobDeliveries,
} from '../../services/distributionService';

const CHANNEL_ICONS = {
  Email: <Mail className="w-3.5 h-3.5" />,
  SMS: <Smartphone className="w-3.5 h-3.5" />,
  WhatsApp: <MessageSquare className="w-3.5 h-3.5 text-emerald-500" />,
  Voice: <Volume2 className="w-3.5 h-3.5 text-indigo-500" />,
  Web: <Globe className="w-3.5 h-3.5 text-sky-500" />,
};

export default function CampaignDistributionSection({
  campaign,
  isOwner,
}) {
  const [selectedChannel, setSelectedChannel] = useState(
    campaign?.channels?.[0] || 'Email'
  );
  const [readiness, setReadiness] = useState(null);
  const [readinessLoading, setReadinessLoading] = useState(false);
  const [actionError, setActionError] = useState(null);
  const [actionSuccess, setActionSuccess] = useState(null);

  // Active Job State
  const [activeJob, setActiveJob] = useState(null);
  const [jobLoading, setJobLoading] = useState(false);
  const [creatingJob, setCreatingJob] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [retrying, setRetrying] = useState(false);

  // Deliveries Table State
  const [deliveries, setDeliveries] = useState([]);
  const [deliveriesLoading, setDeliveriesLoading] = useState(false);
  const [deliveryFilter, setDeliveryFilter] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [page, setPage] = useState(1);
  const [totalDeliveries, setTotalDeliveries] = useState(0);

  // 1. Fetch Readiness
  const fetchReadiness = useCallback(async () => {
    if (!campaign?.id) return;
    setReadinessLoading(true);
    try {
      const res = await getCampaignReadiness(campaign.id, selectedChannel);
      setReadiness(res);
    } catch (err) {
      console.error('Failed to fetch readiness:', err);
      setReadiness(null);
    } finally {
      setReadinessLoading(false);
    }
  }, [campaign?.id, selectedChannel]);

  // 2. Fetch Latest Job for this campaign
  const fetchLatestJob = useCallback(async () => {
    if (!campaign?.id) return;
    setJobLoading(true);
    try {
      const res = await listDistributionJobs({
        campaign_id: campaign.id,
        size: 1,
      });
      if (res?.items?.length > 0) {
        setActiveJob(res.items[0]);
      } else {
        setActiveJob(null);
      }
    } catch (err) {
      console.error('Failed to fetch jobs:', err);
    } finally {
      setJobLoading(false);
    }
  }, [campaign?.id]);

  // 3. Fetch Deliveries for active job
  const fetchDeliveries = useCallback(async () => {
    if (!activeJob?.job_id) {
      setDeliveries([]);
      setTotalDeliveries(0);
      return;
    }
    setDeliveriesLoading(true);
    try {
      const res = await listJobDeliveries(activeJob.job_id, {
        page,
        size: 10,
        status: deliveryFilter || undefined,
        search: searchQuery.trim() || undefined,
      });
      setDeliveries(res.items || []);
      setTotalDeliveries(res.total || 0);
    } catch (err) {
      console.error('Failed to load deliveries:', err);
    } finally {
      setDeliveriesLoading(false);
    }
  }, [activeJob?.job_id, page, deliveryFilter, searchQuery]);

  useEffect(() => {
    fetchReadiness();
  }, [fetchReadiness]);

  useEffect(() => {
    fetchLatestJob();
  }, [fetchLatestJob]);

  useEffect(() => {
    fetchDeliveries();
  }, [fetchDeliveries]);

  // Handle Queue Job (Stages in database with status 'queued' for worker or manual trigger)
  const handleQueueJob = async () => {
    if (!isOwner || creatingJob) return;
    setActionError(null);
    setActionSuccess(null);
    setCreatingJob(true);
    try {
      const job = await createDistributionJob(campaign.id, selectedChannel);
      setActiveJob(job);
      setActionSuccess(`Distribution job created (#${job.job_id.slice(0, 8)}) and queued in database. Ready for worker daemon or manual simulation.`);
      fetchDeliveries();
    } catch (err) {
      console.error('Job staging failed:', err);
      setActionError(err.response?.data?.detail || 'Failed to stage distribution job.');
    } finally {
      setCreatingJob(false);
    }
  };

  // Handle Process Job (Simulate Immediate Execution)
  const handleProcessJob = async (jobId) => {
    const targetJobId = jobId || activeJob?.job_id;
    if (!targetJobId || processing) return;
    setActionError(null);
    setActionSuccess(null);
    setProcessing(true);
    try {
      const processed = await processDistributionJob(targetJobId);
      setActiveJob(processed);
      setActionSuccess(`Broadcast simulation finished: ${processed.delivered_recipients} delivered, ${processed.failed_recipients} failed, ${processed.skipped_recipients} consent-skipped.`);
      fetchDeliveries();
    } catch (err) {
      console.error('Broadcast processing failed:', err);
      setActionError(err.response?.data?.detail || 'Failed to execute broadcast simulation.');
    } finally {
      setProcessing(false);
    }
  };

  // Handle Create and Immediately Process (Single-click workflow)
  const handleCreateAndSimulate = async () => {
    if (!isOwner || creatingJob || processing) return;
    setActionError(null);
    setActionSuccess(null);
    setProcessing(true);
    try {
      const job = await createDistributionJob(campaign.id, selectedChannel);
      setActiveJob(job);
      const processed = await processDistributionJob(job.job_id);
      setActiveJob(processed);
      setActionSuccess(`Distribution job created & simulated: ${processed.delivered_recipients} delivered successfully.`);
      fetchDeliveries();
    } catch (err) {
      console.error('Job create and simulate failed:', err);
      setActionError(err.response?.data?.detail || 'Failed to complete distribution simulation.');
    } finally {
      setProcessing(false);
    }
  };

  // Handle Retry
  const handleRetryJob = async () => {
    if (!activeJob || retrying) return;
    if (!window.confirm(`Are you sure you want to retry failed deliveries for job #${activeJob.job_id.slice(0, 8)}?`)) {
      return;
    }
    setActionError(null);
    setRetrying(true);
    try {
      const updated = await retryDistributionJob(activeJob.job_id);
      setActiveJob(updated);
      setActionSuccess(`Retry executed. Status: ${updated.status}. Total delivered: ${updated.delivered_recipients}.`);
      fetchDeliveries();
    } catch (err) {
      console.error('Retry failed:', err);
      setActionError(err.response?.data?.detail || 'Retry operation failed.');
    } finally {
      setRetrying(false);
    }
  };

  // Handle Cancel
  const handleCancelJob = async () => {
    if (!activeJob) return;
    if (!window.confirm(`Are you sure you want to cancel distribution job #${activeJob.job_id.slice(0, 8)}? Any unsent recipient deliveries will be aborted.`)) {
      return;
    }
    try {
      const cancelled = await cancelDistributionJob(activeJob.job_id);
      setActiveJob(cancelled);
      setActionSuccess('Distribution job cancelled successfully.');
      fetchDeliveries();
    } catch (err) {
      setActionError(err.response?.data?.detail || 'Failed to cancel distribution job.');
    }
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
      case 'pending':
        return 'bg-blue-100 text-blue-800 border-blue-300';
      case 'cancelled':
      default:
        return 'bg-slate-100 text-slate-700 border-slate-300';
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
      case 'pending':
      default:
        return 'bg-slate-100 text-slate-700 border-slate-200';
    }
  };

  const excludedConsentCount = readiness
    ? Math.max(0, (readiness.total_target_audience || 0) - (readiness.confirmed_consent_audience || 0))
    : 0;

  return (
    <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm space-y-6">
      
      {/* Section Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border-b border-slate-100 pb-4">
        <div>
          <div className="flex items-center gap-2">
            <SendHorizontal className="w-5 h-5 text-brand-600" />
            <h2 className="text-lg font-bold text-slate-900">
              Multichannel Distribution & Delivery Engine
            </h2>
          </div>
          <p className="text-xs text-slate-500 mt-0.5">
            Evaluate consent-aware readiness, configure target channels, and dispatch simulated mass public awareness broadcasts.
          </p>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          <Link
            to="/distribution"
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold transition"
          >
            <Server className="w-3.5 h-3.5 text-slate-600" />
            Distribution Dashboard
            <ExternalLink className="w-3 h-3 text-slate-400" />
          </Link>
          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-indigo-50 border border-indigo-200 text-indigo-700 text-xs font-semibold">
            <ShieldCheck className="w-3.5 h-3.5 text-indigo-600" />
            Simulated Provider Engine
          </div>
        </div>
      </div>

      {/* General Affirmative Consent Policy Banner */}
      <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200 text-xs text-slate-600 space-y-1">
        <div className="flex items-center gap-2 font-semibold text-slate-800">
          <Info className="w-4 h-4 text-brand-600 flex-shrink-0" />
          <span>General Affirmative Consent Policy</span>
        </div>
        <p className="text-[11px] text-slate-600 pl-6 leading-relaxed">
          Platform governance strictly mandates general affirmative opt-in consent (<code>consent_status = True</code>) and valid contact coordinates for target delivery. The current audience schema enforces platform-level consent across all channels; per-channel consent is not configured.
        </p>
      </div>

      {/* Action Alerts */}
      {actionSuccess && (
        <div className="p-3.5 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0" />
          <span className="flex-grow">{actionSuccess}</span>
          <button onClick={() => setActionSuccess(null)} className="text-emerald-700 font-bold hover:underline">Dismiss</button>
        </div>
      )}
      {actionError && (
        <div className="p-3.5 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-center gap-2">
          <AlertCircle className="w-4 h-4 text-rose-600 flex-shrink-0" />
          <span className="flex-grow">{actionError}</span>
          <button onClick={() => setActionError(null)} className="text-rose-700 font-bold hover:underline">Dismiss</button>
        </div>
      )}

      {/* Channel Selector Bar */}
      <div className="space-y-2">
        <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider">
          Target Communication Channel
        </label>
        <div className="flex items-center gap-2 flex-wrap">
          {['Email', 'SMS', 'WhatsApp', 'Voice', 'Web'].map((ch) => {
            const isConfigured = campaign.channels?.includes(ch);
            const isSelected = selectedChannel === ch;
            return (
              <button
                key={ch}
                type="button"
                onClick={() => setSelectedChannel(ch)}
                className={`inline-flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-semibold transition border ${
                  isSelected
                    ? 'bg-brand-600 text-white border-brand-600 shadow-sm'
                    : isConfigured
                    ? 'bg-slate-50 text-slate-700 border-slate-200 hover:bg-slate-100'
                    : 'bg-slate-50/50 text-slate-400 border-dashed border-slate-200 hover:text-slate-600'
                }`}
              >
                {CHANNEL_ICONS[ch]}
                {ch}
                {!isConfigured && (
                  <span className="text-[10px] text-slate-400 font-normal">(unconfigured)</span>
                )}
              </button>
            );
          })}
        </div>
      </div>

      {/* Readiness Assessment Card */}
      <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-4">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <span className="text-xs font-bold text-slate-800 uppercase tracking-wider flex items-center gap-1.5">
            <ShieldAlert className="w-4 h-4 text-amber-500" /> Pre-Dispatch Distribution Readiness
          </span>
          {readinessLoading ? (
            <span className="text-xs text-slate-400 flex items-center gap-1">
              <Loader2 className="w-3.5 h-3.5 animate-spin" /> Assessing...
            </span>
          ) : readiness?.is_ready ? (
            <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-emerald-100 text-emerald-800 border border-emerald-200 flex items-center gap-1">
              <CheckCircle2 className="w-3 h-3 text-emerald-600" /> Ready for Broadcast
            </span>
          ) : (
            <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-rose-100 text-rose-800 border border-rose-200 flex items-center gap-1">
              <AlertCircle className="w-3 h-3 text-rose-600" /> Action Required
            </span>
          )}
        </div>

        {/* Readiness Checklist */}
        {readiness && (
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-2.5 text-xs pt-1">
            <div className={`p-2.5 rounded-lg border ${readiness.campaign_status_valid ? 'bg-white border-slate-200' : 'bg-rose-50/70 border-rose-200 text-rose-800'}`}>
              <span className="text-[11px] text-slate-400 block">Campaign Lifecycle</span>
              <strong className={readiness.campaign_status_valid ? 'text-slate-800' : 'text-rose-700'}>
                {readiness.campaign_status}
              </strong>
            </div>

            <div className={`p-2.5 rounded-lg border ${readiness.channel_supported ? 'bg-white border-slate-200' : 'bg-rose-50/70 border-rose-200 text-rose-800'}`}>
              <span className="text-[11px] text-slate-400 block">Channel Supported</span>
              <strong className={readiness.channel_supported ? 'text-slate-800' : 'text-rose-700'}>
                {readiness.channel_supported ? 'Authorized' : 'Not Configured'}
              </strong>
            </div>

            <div className={`p-2.5 rounded-lg border ${readiness.content_approved && !readiness.content_is_outdated ? 'bg-white border-slate-200' : 'bg-rose-50/70 border-rose-200 text-rose-800'}`}>
              <span className="text-[11px] text-slate-400 block">Content Review Guard</span>
              <strong className={readiness.content_approved && !readiness.content_is_outdated ? 'text-slate-800' : 'text-rose-700'}>
                {readiness.content_is_outdated ? 'Evaluation Outdated' : readiness.content_approved ? 'Approved & Valid' : 'Unapproved'}
              </strong>
            </div>

            <div className={`p-2.5 rounded-lg border ${readiness.eligible_recipients_count > 0 ? 'bg-white border-slate-200' : 'bg-rose-50/70 border-rose-200 text-rose-800'}`}>
              <span className="text-[11px] text-slate-400 block">Confirmed Consent Reach</span>
              <strong className={readiness.eligible_recipients_count > 0 ? 'text-emerald-700 font-mono' : 'text-rose-700 font-mono'}>
                {readiness.eligible_recipients_count} Recipients
              </strong>
            </div>
          </div>
        )}

        {/* Audience Reach & Consent Breakdown */}
        {readiness && (
          <div className="bg-white p-3 rounded-xl border border-slate-200 space-y-2">
            <span className="text-[11px] font-bold text-slate-600 uppercase tracking-wider block">
              Audience Reach & Exclusion Breakdown
            </span>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-center text-xs">
              <div className="p-2 rounded-lg bg-slate-50">
                <span className="text-slate-400 text-[10px] uppercase block">Total Audience</span>
                <span className="font-bold text-slate-800 text-sm">{readiness.total_target_audience || 0}</span>
              </div>
              <div className="p-2 rounded-lg bg-emerald-50 text-emerald-800">
                <span className="text-emerald-600 text-[10px] uppercase block">Confirmed Opt-In</span>
                <span className="font-bold text-emerald-700 text-sm">{readiness.confirmed_consent_audience || 0}</span>
              </div>
              <div className="p-2 rounded-lg bg-amber-50 text-amber-800">
                <span className="text-amber-600 text-[10px] uppercase block">Consent Excluded</span>
                <span className="font-bold text-amber-700 text-sm">{excludedConsentCount}</span>
              </div>
              <div className="p-2 rounded-lg bg-indigo-50 text-indigo-800">
                <span className="text-indigo-600 text-[10px] uppercase block">Channel Deliverable</span>
                <span className="font-bold text-indigo-700 text-sm">{readiness.eligible_recipients_count || 0}</span>
              </div>
            </div>
          </div>
        )}

        {/* Blocking Reasons Alert */}
        {readiness && readiness.blocking_reasons && readiness.blocking_reasons.length > 0 && (
          <div className="p-3 rounded-lg bg-rose-50 border border-rose-200 text-xs text-rose-800 space-y-1">
            <span className="font-bold flex items-center gap-1">
              <AlertTriangle className="w-3.5 h-3.5 text-rose-600" /> Distribution Blockers:
            </span>
            <ul className="list-disc pl-5 space-y-0.5 text-[11px]">
              {readiness.blocking_reasons.map((r, idx) => (
                <li key={idx}>{r}</li>
              ))}
            </ul>
          </div>
        )}

        {/* Job Creation and Action Controls */}
        <div className="pt-2 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 border-t border-slate-200/80">
          <p className="text-[11px] text-slate-500 max-w-md">
            Stage a job in the database for background worker execution, or simulate immediate dispatch directly.
          </p>
          <div className="flex items-center gap-2 flex-wrap">
            <button
              type="button"
              onClick={handleQueueJob}
              disabled={!readiness?.is_ready || !isOwner || creatingJob || processing}
              className={`inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-bold transition border ${
                !readiness?.is_ready || !isOwner || creatingJob || processing
                  ? 'bg-slate-100 text-slate-400 border-slate-200 cursor-not-allowed'
                  : 'bg-white text-slate-700 border-slate-300 hover:bg-slate-50 shadow-xs'
              }`}
            >
              {creatingJob ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  Queueing Job...
                </>
              ) : (
                <>
                  <Clock className="w-3.5 h-3.5 text-slate-500" />
                  Queue Job for Worker
                </>
              )}
            </button>

            <button
              type="button"
              onClick={handleCreateAndSimulate}
              disabled={!readiness?.is_ready || !isOwner || creatingJob || processing}
              className={`inline-flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition shadow-xs ${
                !readiness?.is_ready || !isOwner || creatingJob || processing
                  ? 'bg-slate-200 text-slate-400 cursor-not-allowed'
                  : 'bg-brand-600 text-white hover:bg-brand-700'
              }`}
            >
              {processing ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  Simulating Broadcast...
                </>
              ) : (
                <>
                  <SendHorizontal className="w-3.5 h-3.5" />
                  Simulate {selectedChannel} Broadcast
                </>
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Active Distribution Job Status Card */}
      {activeJob && (
        <div className="p-5 rounded-2xl bg-slate-900 text-white space-y-4 shadow-md">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 border-b border-slate-800 pb-3">
            <div>
              <div className="flex items-center gap-2">
                <span className={`text-xs font-bold px-2.5 py-0.5 rounded-full border ${getStatusBadge(activeJob.status)}`}>
                  Job: {activeJob.status}
                </span>
                <span className="text-xs font-mono text-slate-400">UUID: {activeJob.job_id}</span>
              </div>
              <p className="text-[11px] text-slate-400 mt-1">
                Channel: <strong>{activeJob.channel}</strong> • Created by {activeJob.creator_name || `User #${activeJob.created_by}`}
              </p>
              {activeJob.locked_by && (
                <span className="text-[10px] text-sky-400 font-mono block mt-0.5">
                  Worker Lease: {activeJob.locked_by} {activeJob.recovery_count > 0 ? `(Recovered ${activeJob.recovery_count}x)` : ''}
                </span>
              )}
            </div>

            <div className="flex items-center gap-2 flex-wrap">
              {/* If job is queued, allow immediate manual dispatch */}
              {activeJob.status === 'queued' && (
                <button
                  type="button"
                  onClick={() => handleProcessJob(activeJob.job_id)}
                  disabled={processing}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold transition shadow-xs"
                >
                  {processing ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      Dispatching...
                    </>
                  ) : (
                    <>
                      <Play className="w-3.5 h-3.5" />
                      Simulate Immediate Dispatch
                    </>
                  )}
                </button>
              )}

              {activeJob.failed_recipients > 0 && (
                <button
                  type="button"
                  onClick={handleRetryJob}
                  disabled={retrying}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-amber-600 hover:bg-amber-700 text-white text-xs font-bold transition"
                >
                  <RotateCw className={`w-3.5 h-3.5 ${retrying ? 'animate-spin' : ''}`} />
                  Retry Failed
                </button>
              )}
              {['queued', 'pending', 'processing'].includes(activeJob.status) && (
                <button
                  type="button"
                  onClick={handleCancelJob}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-700 text-white text-xs font-bold transition"
                >
                  <XCircle className="w-3.5 h-3.5" />
                  Cancel Job
                </button>
              )}
            </div>
          </div>

          {/* Queued State Notice */}
          {activeJob.status === 'queued' && (
            <div className="p-3 rounded-xl bg-blue-950/60 border border-blue-800/80 text-blue-200 text-xs flex items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <Clock className="w-4 h-4 text-blue-400 flex-shrink-0 animate-pulse" />
                <span>
                  Job is queued in the database. A running background worker daemon will process it, or you can click <strong>Simulate Immediate Dispatch</strong> above.
                </span>
              </div>
            </div>
          )}

          {/* Metric Counter Cards */}
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 text-center">
            <div className="bg-slate-800/80 p-2.5 rounded-xl">
              <span className="text-lg font-black block">{activeJob.total_recipients}</span>
              <span className="text-[10px] text-slate-400 uppercase tracking-wider">Total</span>
            </div>
            <div className="bg-blue-900/40 border border-blue-800/60 p-2.5 rounded-xl">
              <span className="text-lg font-black text-blue-300 block">{activeJob.queued_recipients}</span>
              <span className="text-[10px] text-blue-200 uppercase tracking-wider">Queued</span>
            </div>
            <div className="bg-emerald-900/40 border border-emerald-800/60 p-2.5 rounded-xl">
              <span className="text-lg font-black text-emerald-300 block">{activeJob.delivered_recipients}</span>
              <span className="text-[10px] text-emerald-200 uppercase tracking-wider">Delivered</span>
            </div>
            <div className="bg-rose-900/40 border border-rose-800/60 p-2.5 rounded-xl">
              <span className="text-lg font-black text-rose-300 block">{activeJob.failed_recipients}</span>
              <span className="text-[10px] text-rose-200 uppercase tracking-wider">Failed</span>
            </div>
            <div className="bg-amber-900/40 border border-amber-800/60 p-2.5 rounded-xl">
              <span className="text-lg font-black text-amber-300 block">{activeJob.skipped_recipients}</span>
              <span className="text-[10px] text-amber-200 uppercase tracking-wider">Consent Skipped</span>
            </div>
          </div>
        </div>
      )}

      {/* Recipient Deliveries Log Table */}
      {activeJob && (
        <div className="space-y-3 pt-2">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <Users className="w-4 h-4 text-brand-600" />
              <h3 className="text-xs font-bold text-slate-800 uppercase tracking-wider">
                Recipient Delivery Outcomes ({totalDeliveries})
              </h3>
            </div>

            <div className="flex items-center gap-2 w-full sm:w-auto">
              <div className="relative flex-1 sm:w-48">
                <input
                  type="text"
                  placeholder="Filter address..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full pl-8 pr-3 py-1 text-xs rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-brand-500"
                />
                <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-2" />
              </div>

              <select
                value={deliveryFilter}
                onChange={(e) => setDeliveryFilter(e.target.value)}
                className="px-2.5 py-1 text-xs rounded-lg border border-slate-300 bg-white"
              >
                <option value="">All Statuses</option>
                <option value="delivered">Delivered</option>
                <option value="failed">Failed</option>
                <option value="skipped_consent">Skipped (Consent)</option>
                <option value="pending">Pending</option>
              </select>

              <button
                type="button"
                onClick={fetchDeliveries}
                className="p-1.5 text-slate-500 hover:text-slate-800 rounded-lg hover:bg-slate-100 transition"
                title="Refresh log"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${deliveriesLoading ? 'animate-spin' : ''}`} />
              </button>
            </div>
          </div>

          {/* Table */}
          <div className="overflow-x-auto border border-slate-200 rounded-xl">
            <table className="w-full text-left text-xs divide-y divide-slate-200">
              <thead className="bg-slate-50 text-[11px] font-bold text-slate-600 uppercase tracking-wider">
                <tr>
                  <th className="px-4 py-2.5">Recipient</th>
                  <th className="px-4 py-2.5">Channel</th>
                  <th className="px-4 py-2.5">Delivery Status</th>
                  <th className="px-4 py-2.5">Attempts</th>
                  <th className="px-4 py-2.5">Provider Reference / Error</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 bg-white">
                {deliveriesLoading ? (
                  <tr>
                    <td colSpan="5" className="p-8 text-center text-slate-400">Loading delivery records...</td>
                  </tr>
                ) : deliveries.length === 0 ? (
                  <tr>
                    <td colSpan="5" className="p-8 text-center text-slate-400">No delivery records matching filter.</td>
                  </tr>
                ) : (
                  deliveries.map((rec) => (
                    <tr key={rec.id} className="hover:bg-slate-50/70 transition">
                      <td className="px-4 py-2.5">
                        <div className="font-semibold text-slate-900">{rec.recipient_name || `Member #${rec.audience_member_id}`}</div>
                        <div className="text-[11px] font-mono text-slate-500" title="Masked for privacy">
                          {rec.masked_recipient_address || '—'}
                        </div>
                      </td>
                      <td className="px-4 py-2.5 font-medium text-slate-700">
                        <span className="inline-flex items-center gap-1.5">
                          {CHANNEL_ICONS[rec.channel]}
                          {rec.channel}
                        </span>
                      </td>
                      <td className="px-4 py-2.5">
                        <span className={`inline-block px-2 py-0.5 rounded-full text-[10px] font-bold border ${getDeliveryStatusBadge(rec.delivery_status)}`}>
                          {rec.delivery_status}
                        </span>
                      </td>
                      <td className="px-4 py-2.5 text-slate-600 font-mono">
                        {rec.attempt_count} / {rec.max_attempts}
                      </td>
                      <td className="px-4 py-2.5 text-[11px]">
                        {rec.provider_reference && (
                          <div className="font-mono text-slate-600 truncate max-w-xs">{rec.provider_reference}</div>
                        )}
                        {rec.error_code && (
                          <div className="text-rose-600 font-medium">{rec.error_code}: {rec.error_message}</div>
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

    </div>
  );
}
