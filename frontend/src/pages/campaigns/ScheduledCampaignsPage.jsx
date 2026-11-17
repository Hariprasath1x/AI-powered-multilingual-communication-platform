import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import {
  Calendar,
  Clock,
  Play,
  Pause,
  XCircle,
  AlertCircle,
  CheckCircle2,
  RefreshCw,
  Repeat,
  Globe,
  Radio,
  ChevronRight,
} from 'lucide-react';
import {
  listScheduledCampaigns,
  pauseCampaignSchedule,
  resumeCampaignSchedule,
  cancelCampaignSchedule,
} from '../../services/campaignService';

export default function ScheduledCampaignsPage() {
  const [scheduledList, setScheduledList] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [statusFilter, setStatusFilter] = useState(''); // '' for all, or 'active', 'paused', 'completed', 'cancelled'
  const [actionLoading, setActionLoading] = useState(null);
  const [msg, setMsg] = useState(null);

  useEffect(() => {
    fetchSchedules();
  }, [statusFilter]);

  const fetchSchedules = async () => {
    try {
      setLoading(true);
      setError(null);
      const params = statusFilter ? { status: statusFilter } : {};
      const data = await listScheduledCampaigns(params);
      setScheduledList(data.items || []);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load scheduled campaigns.');
    } finally {
      setLoading(false);
    }
  };

  const handlePause = async (campaignId) => {
    try {
      setActionLoading(campaignId);
      await pauseCampaignSchedule(campaignId);
      setMsg(`Campaign #${campaignId} schedule paused.`);
      fetchSchedules();
      setTimeout(() => setMsg(null), 3000);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to pause schedule.');
    } finally {
      setActionLoading(null);
    }
  };

  const handleResume = async (campaignId) => {
    try {
      setActionLoading(campaignId);
      await resumeCampaignSchedule(campaignId);
      setMsg(`Campaign #${campaignId} schedule resumed.`);
      fetchSchedules();
      setTimeout(() => setMsg(null), 3000);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to resume schedule.');
    } finally {
      setActionLoading(null);
    }
  };

  const handleCancel = async (campaignId) => {
    if (!window.confirm('Are you sure you want to cancel this campaign schedule?')) return;
    try {
      setActionLoading(campaignId);
      await cancelCampaignSchedule(campaignId);
      setMsg(`Campaign #${campaignId} schedule cancelled.`);
      fetchSchedules();
      setTimeout(() => setMsg(null), 3000);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to cancel schedule.');
    } finally {
      setActionLoading(null);
    }
  };

  const statusBadge = (st) => {
    const map = {
      active: 'bg-emerald-50 text-emerald-700 border-emerald-200',
      paused: 'bg-amber-50 text-amber-700 border-amber-200',
      completed: 'bg-blue-50 text-blue-700 border-blue-200',
      cancelled: 'bg-slate-100 text-slate-600 border-slate-200',
    };
    return (
      <span className={`px-2.5 py-0.5 rounded-full text-xs font-bold border uppercase tracking-wider ${map[st] || 'bg-slate-100 text-slate-700'}`}>
        {st}
      </span>
    );
  };

  return (
    <div className="p-4 sm:p-6 lg:p-8 max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight text-slate-900">Scheduled Campaigns</h1>
            <span className="text-xs font-bold uppercase tracking-wider px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-700 border border-indigo-200">
              Task 15
            </span>
          </div>
          <p className="text-sm text-slate-500 mt-1">
            Automated calendar scheduling, recurrence intervals, and background execution lifecycle
          </p>
        </div>

        <button
          onClick={fetchSchedules}
          disabled={loading}
          className="inline-flex items-center gap-2 px-3.5 py-2 text-xs font-semibold rounded-lg bg-white border border-slate-300 text-slate-700 hover:bg-slate-50 shadow-2xs transition self-start sm:self-auto"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {/* Notifications */}
      {error && (
        <div className="bg-rose-50 border border-rose-200 rounded-xl p-4 flex items-center gap-3 text-rose-700 text-sm">
          <AlertCircle className="w-5 h-5 shrink-0 text-rose-500" />
          <span>{error}</span>
        </div>
      )}

      {msg && (
        <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-4 flex items-center gap-3 text-emerald-800 text-sm">
          <CheckCircle2 className="w-5 h-5 shrink-0 text-emerald-600" />
          <span>{msg}</span>
        </div>
      )}

      {/* Status Filter Tabs */}
      <div className="flex items-center gap-2 border-b border-slate-200 pb-2 overflow-x-auto text-xs font-semibold">
        {[
          { label: 'All Schedules', value: '' },
          { label: 'Active', value: 'active' },
          { label: 'Paused', value: 'paused' },
          { label: 'Completed', value: 'completed' },
          { label: 'Cancelled', value: 'cancelled' },
        ].map((tab) => (
          <button
            key={tab.value}
            onClick={() => setStatusFilter(tab.value)}
            className={`px-3 py-1.5 rounded-lg transition whitespace-nowrap ${
              statusFilter === tab.value
                ? 'bg-indigo-600 text-white shadow-2xs'
                : 'text-slate-600 hover:bg-slate-100'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Schedules List / Cards */}
      {loading ? (
        <div className="text-center py-16 bg-white rounded-2xl border border-slate-200">
          <RefreshCw className="w-8 h-8 text-indigo-500 animate-spin mx-auto mb-2" />
          <p className="text-xs text-slate-500">Loading schedules...</p>
        </div>
      ) : scheduledList.length === 0 ? (
        <div className="text-center py-16 bg-white rounded-2xl border border-dashed border-slate-200">
          <Calendar className="w-10 h-10 text-slate-400 mx-auto mb-3" />
          <h3 className="text-sm font-bold text-slate-800">No scheduled campaigns found</h3>
          <p className="text-xs text-slate-500 max-w-sm mx-auto mt-1 mb-4">
            Campaigns configured for one-time future broadcast or recurring daily/weekly schedules will appear here.
          </p>
          <Link
            to="/campaigns"
            className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-bold rounded-lg bg-indigo-600 text-white hover:bg-indigo-700 shadow-2xs transition"
          >
            View Campaigns Studio
          </Link>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {scheduledList.map((item) => (
            <div
              key={item.schedule_id}
              className="bg-white rounded-2xl border border-slate-200 p-5 shadow-2xs hover:shadow-md transition flex flex-col justify-between"
            >
              <div className="space-y-3">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <Link
                      to={`/campaigns/${item.campaign_id}`}
                      className="text-sm font-bold text-slate-900 hover:text-indigo-600 transition flex items-center gap-1"
                    >
                      {item.campaign_name}
                      <ChevronRight className="w-3.5 h-3.5 text-slate-400" />
                    </Link>
                    <span className="text-[11px] text-slate-500">{item.campaign_type}</span>
                  </div>
                  {statusBadge(item.status)}
                </div>

                <div className="p-3 bg-slate-50 rounded-xl space-y-2 text-xs">
                  <div className="flex items-center justify-between text-slate-600">
                    <span className="flex items-center gap-1.5">
                      <Repeat className="w-3.5 h-3.5 text-indigo-500" />
                      Type:
                    </span>
                    <strong className="text-slate-800 uppercase font-mono text-[11px]">
                      {item.schedule_type}
                    </strong>
                  </div>

                  {item.schedule_type === 'weekly' && item.recurrence_days?.length > 0 && (
                    <div className="flex items-center justify-between text-slate-600">
                      <span>Days:</span>
                      <span className="font-semibold text-slate-800 uppercase font-mono text-[11px]">
                        {item.recurrence_days.join(', ')}
                      </span>
                    </div>
                  )}

                  {item.recurrence_time && (
                    <div className="flex items-center justify-between text-slate-600">
                      <span>Target Time:</span>
                      <span className="font-semibold text-slate-800 font-mono text-[11px]">
                        {item.recurrence_time}
                      </span>
                    </div>
                  )}

                  <div className="flex items-center justify-between text-slate-600">
                    <span className="flex items-center gap-1.5">
                      <Globe className="w-3.5 h-3.5 text-indigo-500" />
                      Timezone:
                    </span>
                    <span className="font-mono text-slate-700 text-[11px]">{item.timezone}</span>
                  </div>

                  <div className="flex items-center justify-between text-slate-600">
                    <span className="flex items-center gap-1.5">
                      <Clock className="w-3.5 h-3.5 text-indigo-500" />
                      Next Run:
                    </span>
                    <span className="font-semibold text-indigo-900">
                      {item.next_run_at ? new Date(item.next_run_at).toLocaleString() : '—'}
                    </span>
                  </div>

                  <div className="flex items-center justify-between text-slate-500 text-[11px]">
                    <span>Executions:</span>
                    <span className="font-bold text-slate-700">{item.execution_count}</span>
                  </div>
                </div>

                {item.channels?.length > 0 && (
                  <div className="flex items-center gap-1.5 flex-wrap">
                    {item.channels.map((ch) => (
                      <span
                        key={ch}
                        className="px-2 py-0.5 rounded bg-slate-100 text-slate-700 text-[10px] font-bold"
                      >
                        {ch}
                      </span>
                    ))}
                  </div>
                )}
              </div>

              {/* Actions Footer */}
              <div className="pt-4 mt-4 border-t border-slate-100 flex items-center justify-between gap-2">
                {item.status === 'active' && (
                  <button
                    onClick={() => handlePause(item.campaign_id)}
                    disabled={actionLoading === item.campaign_id}
                    className="inline-flex items-center gap-1 px-3 py-1.5 text-xs font-semibold rounded-lg bg-amber-50 text-amber-700 hover:bg-amber-100 border border-amber-200 transition"
                  >
                    <Pause className="w-3 h-3" />
                    Pause
                  </button>
                )}

                {item.status === 'paused' && (
                  <button
                    onClick={() => handleResume(item.campaign_id)}
                    disabled={actionLoading === item.campaign_id}
                    className="inline-flex items-center gap-1 px-3 py-1.5 text-xs font-semibold rounded-lg bg-emerald-50 text-emerald-700 hover:bg-emerald-100 border border-emerald-200 transition"
                  >
                    <Play className="w-3 h-3" />
                    Resume
                  </button>
                )}

                {item.status !== 'cancelled' && (
                  <button
                    onClick={() => handleCancel(item.campaign_id)}
                    disabled={actionLoading === item.campaign_id}
                    className="inline-flex items-center gap-1 px-3 py-1.5 text-xs font-semibold rounded-lg bg-slate-50 text-rose-600 hover:bg-rose-50 border border-slate-200 transition ml-auto"
                  >
                    <XCircle className="w-3 h-3" />
                    Cancel
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
