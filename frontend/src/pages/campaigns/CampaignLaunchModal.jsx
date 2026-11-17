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
  MessageSquare,
  Bell,
  Globe,
  ShieldCheck,
  ShieldAlert,
  Users,
  Radio,
  ArrowRight,
  Layers,
  Calendar,
  Clock,
  Repeat,
} from 'lucide-react';
import {
  sendCampaign,
  getCampaignSendSummary,
} from '../../services/channelService';
import {
  scheduleCampaign,
} from '../../services/campaignService';

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

  // Configurable channel selection
  const allAvailableChannels = ['WhatsApp', 'SMS', 'Email', 'Push', 'Web'];
  const [selectedChannels, setSelectedChannels] = useState(['WhatsApp', 'SMS', 'Email']);
  const [fallbackOrder, setFallbackOrder] = useState(['WhatsApp', 'SMS', 'Email']);
  const [enableFallback, setEnableFallback] = useState(true);

  // Scheduling state (Task 15)
  const [scheduleMode, setScheduleMode] = useState('now'); // 'now' or 'scheduled'
  const [scheduleType, setScheduleType] = useState('once'); // 'once', 'daily', 'weekly'
  const [scheduledDate, setScheduledDate] = useState('');
  const [scheduledTime, setScheduledTime] = useState('09:00');
  const [selectedTimezone, setSelectedTimezone] = useState('Asia/Kolkata');
  const [weeklyDays, setWeeklyDays] = useState(['mon', 'wed', 'fri']);
  const [scheduleResult, setScheduleResult] = useState(null);

  // Estimate audience counts
  const audienceCount = campaign?.total_recipients || campaign?.target_audience_count || 50;

  useEffect(() => {
    if (isOpen) {
      if (isCompleted) {
        fetchSummary();
        setPhase('summary');
      } else {
        setPhase('overview');
        setError(null);
        setSendSummary(null);
        const campChannels = campaign?.channels?.length
          ? campaign.channels.filter((c) => allAvailableChannels.includes(c))
          : ['WhatsApp', 'SMS', 'Email'];
        setSelectedChannels(campChannels);
        const defaultOrder = ['WhatsApp', 'SMS', 'Email', 'Push'].filter((c) => campChannels.includes(c));
        setFallbackOrder(defaultOrder.length ? defaultOrder : campChannels);
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

  const toggleChannel = (channel) => {
    setSelectedChannels((prev) => {
      const next = prev.includes(channel) ? prev.filter((c) => c !== channel) : [...prev, channel];
      return next.length > 0 ? next : prev;
    });
  };

  const handleInitiateSend = async () => {
    try {
      setPhase('sending');
      setLoading(true);
      setError(null);

      if (scheduleMode === 'scheduled') {
        let targetDt = null;
        if (scheduleType === 'once') {
          if (!scheduledDate) {
            setError('Please pick a future date for one-time scheduling.');
            setPhase('overview');
            setLoading(false);
            return;
          }
          targetDt = new Date(`${scheduledDate}T${scheduledTime || '09:00'}:00`).toISOString();
        }

        const res = await scheduleCampaign(campaign.id, {
          schedule_type: scheduleType,
          scheduled_at: targetDt,
          recurrence_time: scheduledTime || '09:00',
          recurrence_days: scheduleType === 'weekly' ? weeklyDays : [],
          timezone: selectedTimezone,
          channels: selectedChannels,
          fallback_order: fallbackOrder,
          enable_fallback: enableFallback,
        });

        setScheduleResult(res);
        setPhase('scheduled_confirmed');
        if (onCampaignSent) {
          onCampaignSent(res);
        }
      } else {
        // Trigger immediate omnichannel dispatch with fallback configuration
        const summary = await sendCampaign(campaign.id, {
          channels: selectedChannels,
          fallback_order: fallbackOrder,
          enable_fallback: enableFallback,
        });

        setSendSummary(summary);
        setPhase('summary');
        if (onCampaignSent) {
          onCampaignSent(summary);
        }
      }
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to process campaign launch/schedule.');
      setPhase('overview');
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl border border-slate-200 w-full max-w-4xl overflow-hidden flex flex-col max-h-[92vh] animate-in fade-in duration-200">
        {/* Modal Top Header */}
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-gradient-to-r from-slate-900 to-indigo-950 text-white">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-indigo-500/20 border border-indigo-400/30 flex items-center justify-center shadow-inner">
              <SendHorizontal className="w-5 h-5 text-indigo-300" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base font-bold tracking-tight">Omnichannel Distribution Engine</h2>
                <span className="text-[10px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded-full bg-indigo-500/30 text-indigo-200 border border-indigo-400/30">
                  Task 14
                </span>
              </div>
              <p className="text-xs text-slate-300">
                Omnichannel delivery across WhatsApp, Push, Web Broadcast, SMS, and Email with sequential fallback
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
                        ? 'Editorial governance and compliance checks passed. Ready for immediate citizen distribution.'
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

              {/* Omnichannel Selector */}
              <div className="bg-slate-50 border border-slate-200 rounded-xl p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center gap-1.5">
                    <Layers className="w-4 h-4 text-indigo-600" />
                    Target Distribution Channels
                  </h3>
                  <span className="text-xs text-slate-500">Select channels for this campaign</span>
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
                  {[
                    { id: 'WhatsApp', label: 'WhatsApp', icon: MessageSquare },
                    { id: 'SMS', label: 'SMS', icon: Smartphone },
                    { id: 'Email', label: 'Email', icon: Mail },
                    { id: 'Push', label: 'Push', icon: Bell },
                    { id: 'Web', label: 'Web Alert', icon: Globe },
                  ].map((ch) => {
                    const Icon = ch.icon;
                    const isSelected = selectedChannels.includes(ch.id);
                    return (
                      <button
                        key={ch.id}
                        type="button"
                        onClick={() => toggleChannel(ch.id)}
                        className={`flex items-center gap-2 p-2.5 rounded-lg border text-xs font-semibold transition ${
                          isSelected
                            ? 'bg-indigo-600 text-white border-indigo-700 shadow-xs'
                            : 'bg-white text-slate-600 border-slate-300 hover:bg-slate-100'
                        }`}
                      >
                        <Icon className="w-4 h-4 shrink-0" />
                        <span>{ch.label}</span>
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Multi-channel Fallback Configuration */}
              <div className="bg-white border border-slate-200 rounded-xl p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center gap-1.5">
                      <Radio className="w-4 h-4 text-indigo-600" />
                      Sequential Multi-Channel Fallback
                    </h3>
                    <p className="text-xs text-slate-500 mt-0.5">
                      If primary channel fails or recipient lacks credentials, system falls back sequentially without duplicating successful messages.
                    </p>
                  </div>
                  <label className="flex items-center gap-2 cursor-pointer text-xs font-medium text-slate-700">
                    <input
                      type="checkbox"
                      checked={enableFallback}
                      onChange={(e) => setEnableFallback(e.target.checked)}
                      className="rounded text-indigo-600 focus:ring-indigo-500"
                    />
                    Enable Fallback
                  </label>
                </div>

                {enableFallback && (
                  <div className="flex items-center gap-2 p-3 bg-indigo-50/60 border border-indigo-100 rounded-lg text-xs font-mono text-indigo-900 overflow-x-auto">
                    <span className="font-semibold text-slate-700">Sequence:</span>
                    <span className="px-2 py-0.5 rounded bg-white shadow-2xs border border-indigo-200 font-bold text-indigo-700">
                      1. WhatsApp
                    </span>
                    <ArrowRight className="w-3.5 h-3.5 text-indigo-400 shrink-0" />
                    <span className="px-2 py-0.5 rounded bg-white shadow-2xs border border-indigo-200 font-bold text-indigo-700">
                      2. SMS
                    </span>
                    <ArrowRight className="w-3.5 h-3.5 text-indigo-400 shrink-0" />
                    <span className="px-2 py-0.5 rounded bg-white shadow-2xs border border-indigo-200 font-bold text-indigo-700">
                      3. Email
                    </span>
                  </div>
                )}
              </div>

              {/* Execution Timing & Scheduling (Task 15) */}
              <div className="border border-slate-200 rounded-xl p-4 bg-white shadow-2xs space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Calendar className="w-4 h-4 text-indigo-600" />
                    <h3 className="text-xs font-bold text-slate-800 uppercase tracking-wider">
                      Dispatch Schedule & Recurrence (Task 15)
                    </h3>
                  </div>
                  <div className="flex items-center gap-2 bg-slate-100 p-1 rounded-lg">
                    <button
                      type="button"
                      onClick={() => setScheduleMode('now')}
                      className={`px-3 py-1 text-xs font-semibold rounded-md transition ${
                        scheduleMode === 'now' ? 'bg-white text-slate-900 shadow-2xs' : 'text-slate-600 hover:text-slate-900'
                      }`}
                    >
                      Send Now
                    </button>
                    <button
                      type="button"
                      onClick={() => setScheduleMode('scheduled')}
                      className={`px-3 py-1 text-xs font-semibold rounded-md transition ${
                        scheduleMode === 'scheduled' ? 'bg-white text-indigo-700 shadow-2xs' : 'text-slate-600 hover:text-slate-900'
                      }`}
                    >
                      Schedule Broadcast
                    </button>
                  </div>
                </div>

                {scheduleMode === 'scheduled' && (
                  <div className="p-3 bg-indigo-50/50 border border-indigo-100 rounded-xl space-y-3 text-xs">
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                      <div>
                        <label className="block text-slate-600 font-semibold mb-1">Recurrence Pattern</label>
                        <select
                          value={scheduleType}
                          onChange={(e) => setScheduleType(e.target.value)}
                          className="w-full text-xs px-2.5 py-1.5 border border-slate-300 rounded-lg bg-white"
                        >
                          <option value="once">One-Time Future Date</option>
                          <option value="daily">Daily Recurrence</option>
                          <option value="weekly">Weekly Recurrence</option>
                        </select>
                      </div>

                      {scheduleType === 'once' && (
                        <div>
                          <label className="block text-slate-600 font-semibold mb-1">Execution Date</label>
                          <input
                            type="date"
                            value={scheduledDate}
                            onChange={(e) => setScheduledDate(e.target.value)}
                            min={new Date().toISOString().split('T')[0]}
                            className="w-full text-xs px-2.5 py-1.5 border border-slate-300 rounded-lg bg-white"
                          />
                        </div>
                      )}

                      <div>
                        <label className="block text-slate-600 font-semibold mb-1">Target Time (HH:MM)</label>
                        <input
                          type="time"
                          value={scheduledTime}
                          onChange={(e) => setScheduledTime(e.target.value)}
                          className="w-full text-xs px-2.5 py-1.5 border border-slate-300 rounded-lg bg-white"
                        >
                        </input>
                      </div>

                      <div>
                        <label className="block text-slate-600 font-semibold mb-1">Timezone</label>
                        <select
                          value={selectedTimezone}
                          onChange={(e) => setSelectedTimezone(e.target.value)}
                          className="w-full text-xs px-2.5 py-1.5 border border-slate-300 rounded-lg bg-white"
                        >
                          <option value="Asia/Kolkata">Asia/Kolkata (IST)</option>
                          <option value="UTC">UTC (Universal)</option>
                          <option value="America/New_York">America/New_York (EST)</option>
                          <option value="Europe/London">Europe/London (GMT)</option>
                          <option value="Asia/Dubai">Asia/Dubai (GST)</option>
                        </select>
                      </div>
                    </div>

                    {scheduleType === 'weekly' && (
                      <div>
                        <label className="block text-slate-600 font-semibold mb-1">Recurrence Days</label>
                        <div className="flex gap-1.5">
                          {['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'].map((d) => (
                            <button
                              key={d}
                              type="button"
                              onClick={() =>
                                setWeeklyDays((prev) =>
                                  prev.includes(d) ? prev.filter((x) => x !== d) : [...prev, d]
                                )
                              }
                              className={`px-2.5 py-1 rounded text-[11px] font-bold uppercase transition ${
                                weeklyDays.includes(d)
                                  ? 'bg-indigo-600 text-white'
                                  : 'bg-white border border-slate-300 text-slate-600 hover:bg-slate-100'
                              }`}
                            >
                              {d}
                            </button>
                          ))}
                        </div>
                      </div>
                    )}

                    <div className="p-2 bg-white rounded-lg border border-indigo-100 flex items-center justify-between text-slate-700">
                      <span className="font-semibold text-indigo-900">Summary:</span>
                      <span className="font-mono text-[11px]">
                        {scheduleType === 'once'
                          ? `One-time on ${scheduledDate || 'selected date'} at ${scheduledTime} (${selectedTimezone})`
                          : scheduleType === 'daily'
                          ? `Daily at ${scheduledTime} (${selectedTimezone})`
                          : `Weekly on [${weeklyDays.join(', ')}] at ${scheduledTime} (${selectedTimezone})`}
                      </span>
                    </div>
                  </div>
                )}
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
                <div>
                  <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider block">
                    Privacy Protection
                  </span>
                  <span className="text-xs font-semibold text-indigo-700 block mt-1">
                    Zero Public PII Leakage
                  </span>
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
                  <strong className="text-slate-900">{selectedChannels.join(', ')}</strong>.
                </p>
                <div className="bg-amber-50 border border-amber-100 rounded-lg p-3 text-xs text-amber-800 text-left mt-4 space-y-1">
                  <p><strong>Compliance Notice:</strong> Recipient affirmative consent is strictly re-validated in real-time.</p>
                  <p><strong>Multi-Channel Fallback:</strong> {enableFallback ? 'Enabled (WhatsApp -> SMS -> Email).' : 'Disabled (Single preferred channel).'}</p>
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
                  Validating consent, executing omnichannel adapters, handling carrier fallbacks, and updating live logs.
                </p>
              </div>

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
                      Campaign distribution finished with complete tracking and fallback records persisted.
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
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                {Object.entries(sendSummary.channel_summary || {}).map(([ch, stat]) => (
                  <div key={ch} className="border border-slate-200 rounded-xl p-3 bg-white shadow-2xs space-y-2">
                    <div className="flex items-center justify-between border-b border-slate-100 pb-1.5">
                      <span className="text-xs font-bold text-slate-900">{ch} Channel</span>
                      <span className="text-[11px] font-semibold px-1.5 py-0.5 rounded bg-slate-100 text-slate-700">
                        Total: {stat.total}
                      </span>
                    </div>
                    <div className="grid grid-cols-2 gap-1.5 text-center text-[11px]">
                      <div className="bg-emerald-50 p-1.5 rounded">
                        <span className="text-emerald-700 block">Sent/Delivered</span>
                        <span className="font-bold text-emerald-900">{stat.sent + stat.delivered}</span>
                      </div>
                      <div className="bg-rose-50 p-1.5 rounded">
                        <span className="text-rose-600 block">Failed</span>
                        <span className="font-bold text-rose-800">{stat.failed}</span>
                      </div>
                    </div>
                  </div>
                ))}
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
                          <th className="py-2 px-3">Final Channel</th>
                          <th className="py-2 px-3">Status</th>
                          <th className="py-2 px-3">Fallback Attempts</th>
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
                            <td className="py-2 px-3 text-slate-600">
                              {m.fallback_attempts && m.fallback_attempts.length > 0 ? (
                                <span className="font-semibold text-indigo-600">
                                  {m.fallback_attempts.length} attempt(s)
                                </span>
                              ) : (
                                'Direct'
                              )}
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

          {/* Phase: Schedule Confirmed */}
          {phase === 'scheduled_confirmed' && (
            <div className="space-y-6 py-6 text-center">
              <div className="w-16 h-16 rounded-2xl bg-indigo-50 border border-indigo-200 text-indigo-600 flex items-center justify-center mx-auto shadow-xs">
                <Calendar className="w-8 h-8" />
              </div>
              <div className="max-w-md mx-auto space-y-2">
                <h3 className="text-lg font-bold text-slate-900">Campaign Broadcast Scheduled!</h3>
                <p className="text-sm text-slate-600">
                  <strong className="text-slate-900">"{campaign?.name}"</strong> has been successfully registered with the background scheduler.
                </p>

                <div className="bg-indigo-50/60 border border-indigo-100 rounded-xl p-4 text-xs text-left space-y-2 mt-4 font-mono">
                  <div className="flex justify-between">
                    <span className="text-slate-600">Schedule Type:</span>
                    <strong className="text-indigo-900 uppercase">{scheduleResult?.schedule_type || scheduleType}</strong>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-600">Next Scheduled Run:</span>
                    <strong className="text-indigo-900">
                      {scheduleResult?.next_run_at ? new Date(scheduleResult.next_run_at).toLocaleString() : 'Pending calculation'}
                    </strong>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-600">Timezone:</span>
                    <span className="text-slate-800">{scheduleResult?.timezone || selectedTimezone}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-600">Channels:</span>
                    <span className="text-slate-800">{selectedChannels.join(', ')}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-600">Survives Restarts:</span>
                    <span className="text-emerald-700 font-bold">Yes (PostgreSQL Persisted)</span>
                  </div>
                </div>
              </div>
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
              {scheduleMode === 'scheduled' ? <Calendar className="w-3.5 h-3.5" /> : <SendHorizontal className="w-3.5 h-3.5" />}
              {scheduleMode === 'scheduled' ? 'Review & Schedule Campaign' : 'Configure & Send Campaign'}
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
                {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : scheduleMode === 'scheduled' ? <Calendar className="w-3.5 h-3.5" /> : <SendHorizontal className="w-3.5 h-3.5" />}
                {scheduleMode === 'scheduled' ? 'Confirm & Schedule Campaign' : 'Confirm & Launch Broadcast'}
              </button>
            </div>
          )}

          {(phase === 'summary' || phase === 'scheduled_confirmed') && (
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
