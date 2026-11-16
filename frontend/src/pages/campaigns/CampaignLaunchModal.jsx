import React, { useState, useEffect, useRef } from 'react';
import {
  SendHorizontal,
  CheckCircle2,
  AlertCircle,
  AlertTriangle,
  Loader2,
  X,
  Mail,
  Smartphone,
  ShieldCheck,
  ShieldAlert,
  Users,
  Globe,
  Radio,
  Clock,
  Sparkles,
} from 'lucide-react';
import {
  sendCampaign,
  getCampaignSendSummary,
} from '../../services/channelService';

export default function CampaignLaunchModal({
  isOpen,
  onClose,
  campaign,
  onCampaignSent,
}) {
  const [phase, setPhase] = useState('overview'); // 'overview' | 'confirm' | 'sending' | 'summary'
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [sendSummary, setSendSummary] = useState(null);
  const pollTimerRef = useRef(null);

  const isApproved = campaign?.status === 'Approved';
  const isCompleted = campaign?.status === 'Completed';

  // Calculate rough distribution statistics
  const channels = campaign?.channels || ['Email', 'SMS'];
  const hasEmail = channels.includes('Email');
  const hasSMS = channels.includes('SMS');

  // Estimate audience counts
  const audienceCount = campaign?.total_recipients || campaign?.target_audience_count || 50;
  const emailCount = hasEmail ? (hasSMS ? Math.round(audienceCount * 0.6) : audienceCount) : 0;
  const smsCount = hasSMS ? (hasEmail ? Math.round(audienceCount * 0.4) : audienceCount) : 0;

  useEffect(() => {
    if (isOpen) {
      if (isCompleted) {
        // If already completed, load summary immediately
        fetchSummary();
        setPhase('summary');
      } else {
        setPhase('overview');
        setError(null);
        setSendSummary(null);
      }
    }
    return () => {
      if (pollTimerRef.current) clearInterval(pollTimerRef.current);
    };
  }, [isOpen, campaign?.id, campaign?.status]);

  const fetchSummary = async () => {
    try {
      const data = await getCampaignSendSummary(campaign.id);
      setSendSummary(data);
    } catch (err) {
      // Ignore 404/empty summary if not yet dispatched
    }
  };

  const handleInitiateSend = async () => {
    try {
      setPhase('sending');
      setLoading(true);
      setError(null);

      // Trigger dispatch
      const summary = await sendCampaign(campaign.id, {
        channels: campaign.channels,
      });

      setSendSummary(summary);
      setPhase('summary');
      if (onCampaignSent) {
        onCampaignSent(summary);
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to dispatch campaign.');
      setPhase('overview');
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl border border-slate-200 w-full max-w-3xl overflow-hidden flex flex-col max-h-[92vh] animate-in fade-in duration-200">
        {/* Modal Top Header */}
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-gradient-to-r from-slate-900 to-indigo-950 text-white">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-indigo-500/20 border border-indigo-400/30 flex items-center justify-center shadow-inner">
              <SendHorizontal className="w-5 h-5 text-indigo-300" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base font-bold tracking-tight">Campaign Distribution Engine</h2>
                <span className="text-[10px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded-full bg-indigo-500/30 text-indigo-200 border border-indigo-400/30">
                  Task 13
                </span>
              </div>
              <p className="text-xs text-slate-300">
                Multi-channel broadcast across Email and SMS with affirmative consent enforcement
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-white/10 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-6 overflow-y-auto space-y-6 flex-1">
          {error && (
            <div className="bg-rose-50 border border-rose-200 rounded-xl p-4 flex items-center gap-3 text-rose-700 text-sm">
              <AlertCircle className="w-5 h-5 shrink-0 text-rose-500" />
              <span>{error}</span>
            </div>
          )}

          {/* Phase 1: Pre-flight Launch Overview */}
          {phase === 'overview' && (
            <div className="space-y-6">
              {/* Approval Gate Status Banner */}
              <div
                className={`p-4 rounded-xl border flex items-center justify-between ${
                  isApproved
                    ? 'bg-emerald-50 border-emerald-200 text-emerald-900'
                    : 'bg-amber-50 border-amber-200 text-amber-900'
                }`}
              >
                <div className="flex items-center gap-3">
                  {isApproved ? (
                    <ShieldCheck className="w-6 h-6 text-emerald-600 shrink-0" />
                  ) : (
                    <ShieldAlert className="w-6 h-6 text-amber-600 shrink-0" />
                  )}
                  <div>
                    <h3 className="text-sm font-bold">
                      {isApproved ? 'Campaign Verified & Approved for Broadcast' : 'Broadcast Blocked: Approval Required'}
                    </h3>
                    <p className="text-xs opacity-90 mt-0.5">
                      {isApproved
                        ? 'Editorial governance and compliance checks passed. Ready for immediate citizen delivery.'
                        : `Current status is '${campaign?.status}'. Only approved campaigns can be broadcast.`}
                    </p>
                  </div>
                </div>
                <span
                  className={`text-xs px-2.5 py-1 rounded-full font-bold uppercase tracking-wider ${
                    isApproved ? 'bg-emerald-600 text-white' : 'bg-amber-600 text-white'
                  }`}
                >
                  {campaign?.status}
                </span>
              </div>

              {/* Campaign Profile Card */}
              <div className="bg-slate-50 border border-slate-200 rounded-xl p-4 grid grid-cols-2 sm:grid-cols-4 gap-4 text-center">
                <div>
                  <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider block">
                    Campaign
                  </span>
                  <span className="text-sm font-bold text-slate-900 truncate block mt-0.5" title={campaign?.name}>
                    {campaign?.name}
                  </span>
                </div>
                <div>
                  <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider block">
                    Target Channels
                  </span>
                  <div className="flex items-center justify-center gap-1 mt-0.5">
                    {channels.map((ch) => (
                      <span
                        key={ch}
                        className="text-xs font-semibold px-2 py-0.5 rounded bg-indigo-100 text-indigo-700"
                      >
                        {ch}
                      </span>
                    ))}
                  </div>
                </div>
                <div>
                  <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider block">
                    Intended Audience
                  </span>
                  <span className="text-sm font-bold text-slate-900 block mt-0.5 flex items-center justify-center gap-1">
                    <Users className="w-3.5 h-3.5 text-slate-500" />
                    {audienceCount} Citizens
                  </span>
                </div>
                <div>
                  <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider block">
                    Consent Guard
                  </span>
                  <span className="text-xs font-semibold text-emerald-700 block mt-1">
                    Strict Opt-In Enforced
                  </span>
                </div>
              </div>

              {/* Channel Delivery Breakdown Cards */}
              <div>
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-3">
                  Channel Recipient Breakdown
                </h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  {/* Email Card */}
                  <div
                    className={`border rounded-xl p-4 space-y-2 ${
                      hasEmail ? 'bg-white border-slate-200' : 'bg-slate-50 border-slate-200 opacity-60'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <div className="w-8 h-8 rounded-lg bg-blue-50 text-blue-600 flex items-center justify-center">
                          <Mail className="w-4 h-4" />
                        </div>
                        <span className="text-sm font-bold text-slate-900">Email Broadcast</span>
                      </div>
                      <span className="text-xs font-bold text-slate-600">{emailCount} recipients</span>
                    </div>
                    <p className="text-xs text-slate-500">
                      Standard transactional dispatch with personalized subject and placeholders.
                    </p>
                  </div>

                  {/* SMS Card */}
                  <div
                    className={`border rounded-xl p-4 space-y-2 ${
                      hasSMS ? 'bg-white border-slate-200' : 'bg-slate-50 border-slate-200 opacity-60'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <div className="w-8 h-8 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center">
                          <Smartphone className="w-4 h-4" />
                        </div>
                        <span className="text-sm font-bold text-slate-900">SMS Gateway</span>
                      </div>
                      <span className="text-xs font-bold text-slate-600">{smsCount} recipients</span>
                    </div>
                    <p className="text-xs text-slate-500">
                      High-priority alert delivery adhering to telecom segmentation thresholds.
                    </p>
                  </div>
                </div>
              </div>

              {/* Language Localization Summary */}
              <div className="bg-slate-50 border border-slate-200 rounded-xl p-4 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <Globe className="w-5 h-5 text-indigo-600 shrink-0" />
                  <div>
                    <h4 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
                      Multilingual Variant Mapping
                    </h4>
                    <p className="text-xs text-slate-500 mt-0.5">
                      Recipients receive personalized copy in their preferred language (e.g. Hindi, Tamil, English)
                      derived from approved pipeline assets.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Phase 2: Confirmation Prompt */}
          {phase === 'confirm' && (
            <div className="space-y-6 text-center py-4">
              <div className="w-16 h-16 rounded-2xl bg-amber-50 border border-amber-200 text-amber-600 flex items-center justify-center mx-auto shadow-xs">
                <AlertTriangle className="w-8 h-8" />
              </div>
              <div className="max-w-md mx-auto space-y-2">
                <h3 className="text-lg font-bold text-slate-900">Confirm Citizen Broadcast</h3>
                <p className="text-sm text-slate-600">
                  You are about to broadcast <strong className="text-slate-900">"{campaign?.name}"</strong> to approximately{' '}
                  <strong className="text-slate-900">{audienceCount} citizens</strong> across{' '}
                  <strong className="text-slate-900">{channels.join(' and ')}</strong>.
                </p>
                <div className="bg-amber-50 border border-amber-100 rounded-lg p-3 text-xs text-amber-800 text-left mt-4">
                  <strong>Notice:</strong> Recipient affirmative consent will be re-validated in real-time. Any citizen
                  with revoked or unconfirmed consent will be withheld automatically.
                </div>
              </div>
            </div>
          )}

          {/* Phase 3: Sending in Progress View */}
          {phase === 'sending' && (
            <div className="space-y-6 py-8 text-center">
              <Loader2 className="w-12 h-12 text-indigo-600 animate-spin mx-auto" />
              <div className="space-y-2">
                <h3 className="text-base font-bold text-slate-900">Broadcasting Campaign Messages...</h3>
                <p className="text-xs text-slate-500">
                  Processing recipient queues, validating consent, resolving language variants, and executing delivery adapters.
                </p>
              </div>

              {/* Simulated/Live progress bar */}
              <div className="max-w-md mx-auto space-y-2">
                <div className="w-full bg-slate-100 rounded-full h-3 overflow-hidden">
                  <div
                    className="bg-indigo-600 h-full rounded-full transition-all duration-300 animate-pulse"
                    style={{ width: '85%' }}
                  />
                </div>
                <div className="flex justify-between text-xs text-slate-500 font-mono">
                  <span>Dispatching to gateways...</span>
                  <span>Please wait</span>
                </div>
              </div>
            </div>
          )}

          {/* Phase 4: Delivery Summary Report */}
          {phase === 'summary' && sendSummary && (
            <div className="space-y-6 animate-in fade-in">
              <div className="bg-emerald-50 border border-emerald-200 rounded-2xl p-5 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-emerald-600 text-white flex items-center justify-center">
                    <CheckCircle2 className="w-6 h-6" />
                  </div>
                  <div>
                    <h3 className="text-base font-bold text-emerald-950">Broadcast Execution Completed</h3>
                    <p className="text-xs text-emerald-700">
                      Campaign distribution finished with complete tracking records persisted.
                    </p>
                  </div>
                </div>
                <span className="text-xs font-bold uppercase tracking-wider px-3 py-1 rounded-full bg-emerald-200 text-emerald-900">
                  {sendSummary.campaign_status}
                </span>
              </div>

              {/* Aggregate KPI Grid */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-center">
                <div className="bg-slate-50 border border-slate-200 rounded-xl p-3">
                  <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider block">
                    Total Intended
                  </span>
                  <span className="text-xl font-bold text-slate-900 block mt-1">
                    {sendSummary.total_intended_recipients}
                  </span>
                </div>
                <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-3">
                  <span className="text-[11px] font-semibold text-emerald-700 uppercase tracking-wider block">
                    Delivered / Sent
                  </span>
                  <span className="text-xl font-bold text-emerald-900 block mt-1">
                    {sendSummary.delivered_messages + sendSummary.sent_messages}
                  </span>
                </div>
                <div className="bg-rose-50 border border-rose-200 rounded-xl p-3">
                  <span className="text-[11px] font-semibold text-rose-700 uppercase tracking-wider block">
                    Failed / Blocked
                  </span>
                  <span className="text-xl font-bold text-rose-900 block mt-1">
                    {sendSummary.failed_messages}
                  </span>
                </div>
                <div className="bg-amber-50 border border-amber-200 rounded-xl p-3">
                  <span className="text-[11px] font-semibold text-amber-700 uppercase tracking-wider block">
                    Consent Withheld
                  </span>
                  <span className="text-xl font-bold text-amber-900 block mt-1">
                    {sendSummary.opted_out_recipients}
                  </span>
                </div>
              </div>

              {/* Channel Summary Cards */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {/* Email Summary Card */}
                {sendSummary.channel_summary?.Email && (
                  <div className="border border-slate-200 rounded-xl p-4 bg-white shadow-2xs space-y-3">
                    <div className="flex items-center justify-between border-b border-slate-100 pb-2">
                      <span className="text-sm font-bold text-slate-900 flex items-center gap-2">
                        <Mail className="w-4 h-4 text-blue-600" />
                        Email Channel
                      </span>
                      <span className="text-xs font-semibold px-2 py-0.5 rounded bg-blue-50 text-blue-700">
                        Total: {sendSummary.channel_summary.Email.total}
                      </span>
                    </div>
                    <div className="grid grid-cols-3 gap-2 text-center text-xs">
                      <div className="bg-slate-50 p-2 rounded-lg">
                        <span className="text-slate-500 block">Sent</span>
                        <span className="font-bold text-slate-800">
                          {sendSummary.channel_summary.Email.sent + sendSummary.channel_summary.Email.delivered}
                        </span>
                      </div>
                      <div className="bg-rose-50 p-2 rounded-lg">
                        <span className="text-rose-600 block">Failed</span>
                        <span className="font-bold text-rose-700">
                          {sendSummary.channel_summary.Email.failed}
                        </span>
                      </div>
                      <div className="bg-slate-50 p-2 rounded-lg">
                        <span className="text-slate-500 block">Pending</span>
                        <span className="font-bold text-slate-800">
                          {sendSummary.channel_summary.Email.pending}
                        </span>
                      </div>
                    </div>
                  </div>
                )}

                {/* SMS Summary Card */}
                {sendSummary.channel_summary?.SMS && (
                  <div className="border border-slate-200 rounded-xl p-4 bg-white shadow-2xs space-y-3">
                    <div className="flex items-center justify-between border-b border-slate-100 pb-2">
                      <span className="text-sm font-bold text-slate-900 flex items-center gap-2">
                        <Smartphone className="w-4 h-4 text-emerald-600" />
                        SMS Channel
                      </span>
                      <span className="text-xs font-semibold px-2 py-0.5 rounded bg-emerald-50 text-emerald-700">
                        Total: {sendSummary.channel_summary.SMS.total}
                      </span>
                    </div>
                    <div className="grid grid-cols-3 gap-2 text-center text-xs">
                      <div className="bg-slate-50 p-2 rounded-lg">
                        <span className="text-slate-500 block">Sent</span>
                        <span className="font-bold text-slate-800">
                          {sendSummary.channel_summary.SMS.sent + sendSummary.channel_summary.SMS.delivered}
                        </span>
                      </div>
                      <div className="bg-rose-50 p-2 rounded-lg">
                        <span className="text-rose-600 block">Failed</span>
                        <span className="font-bold text-rose-700">
                          {sendSummary.channel_summary.SMS.failed}
                        </span>
                      </div>
                      <div className="bg-slate-50 p-2 rounded-lg">
                        <span className="text-slate-500 block">Pending</span>
                        <span className="font-bold text-slate-800">
                          {sendSummary.channel_summary.SMS.pending}
                        </span>
                      </div>
                    </div>
                  </div>
                )}
              </div>

              {/* Message Audit Log Sample */}
              {sendSummary.messages && sendSummary.messages.length > 0 && (
                <div className="border border-slate-200 rounded-xl overflow-hidden">
                  <div className="px-4 py-2.5 bg-slate-50 border-b border-slate-200 flex items-center justify-between">
                    <span className="text-xs font-bold text-slate-700 uppercase tracking-wider">
                      Dispatched Message Records ({sendSummary.messages.length})
                    </span>
                  </div>
                  <div className="max-h-56 overflow-y-auto">
                    <table className="w-full text-left text-xs">
                      <thead className="bg-slate-100 text-slate-600 sticky top-0">
                        <tr>
                          <th className="py-2 px-3">Tracking ID</th>
                          <th className="py-2 px-3">Recipient</th>
                          <th className="py-2 px-3">Channel</th>
                          <th className="py-2 px-3">Status</th>
                          <th className="py-2 px-3">Provider Reference</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100 font-mono text-[11px]">
                        {sendSummary.messages.map((m) => (
                          <tr key={m.id || m.tracking_id} className="hover:bg-slate-50">
                            <td className="py-2 px-3 text-indigo-600 truncate max-w-[120px]" title={m.tracking_id}>
                              {m.tracking_id}
                            </td>
                            <td className="py-2 px-3 font-sans font-medium text-slate-800">
                              {m.recipient_name} ({m.recipient_address})
                            </td>
                            <td className="py-2 px-3">
                              <span className="px-1.5 py-0.5 rounded bg-slate-100 text-slate-700">
                                {m.channel}
                              </span>
                            </td>
                            <td className="py-2 px-3">
                              <span
                                className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${
                                  m.status === 'Delivered'
                                    ? 'bg-emerald-100 text-emerald-800'
                                    : m.status === 'Sent'
                                    ? 'bg-blue-100 text-blue-800'
                                    : 'bg-rose-100 text-rose-800'
                                }`}
                              >
                                {m.status}
                              </span>
                            </td>
                            <td className="py-2 px-3 text-slate-500 truncate max-w-[140px]">
                              {m.provider_message_id || m.failure_reason || '—'}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div className="px-6 py-4 bg-slate-50 border-t border-slate-200 flex items-center justify-between">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 text-xs font-semibold rounded-lg bg-white border border-slate-300 text-slate-700 hover:bg-slate-100 transition shadow-2xs"
          >
            {phase === 'summary' ? 'Close' : 'Cancel'}
          </button>

          {phase === 'overview' && isApproved && (
            <button
              type="button"
              onClick={() => setPhase('confirm')}
              className="inline-flex items-center gap-1.5 px-5 py-2 text-xs font-bold rounded-lg bg-emerald-600 text-white hover:bg-emerald-700 shadow-sm transition"
            >
              <SendHorizontal className="w-3.5 h-3.5" />
              Send Campaign Now
            </button>
          )}

          {phase === 'confirm' && (
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => setPhase('overview')}
                className="px-4 py-2 text-xs font-semibold rounded-lg bg-white border border-slate-300 text-slate-700 hover:bg-slate-100 transition"
              >
                Back
              </button>
              <button
                type="button"
                onClick={handleInitiateSend}
                disabled={loading}
                className="inline-flex items-center gap-1.5 px-5 py-2 text-xs font-bold rounded-lg bg-emerald-600 text-white hover:bg-emerald-700 shadow-sm transition disabled:opacity-50"
              >
                {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <SendHorizontal className="w-3.5 h-3.5" />}
                Confirm & Launch Broadcast
              </button>
            </div>
          )}

          {phase === 'summary' && (
            <button
              type="button"
              onClick={onClose}
              className="inline-flex items-center gap-1.5 px-5 py-2 text-xs font-bold rounded-lg bg-indigo-600 text-white hover:bg-indigo-700 shadow-sm transition"
            >
              <CheckCircle2 className="w-3.5 h-3.5" />
              Done
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

