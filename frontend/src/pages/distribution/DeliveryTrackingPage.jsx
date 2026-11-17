import React, { useState, useEffect } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import {
  SendHorizontal,
  CheckCircle2,
  XCircle,
  Clock,
  RotateCcw,
  Search,
  Filter,
  AlertCircle,
  RefreshCw,
  Mail,
  Smartphone,
  MessageSquare,
  Bell,
  Globe,
  Radio,
  Eye,
} from 'lucide-react';
import {
  listAllFailedMessages,
  retryMessage,
  retryAllFailedMessages,
  getCampaignDeliverySummary,
} from '../../services/campaignService';

export default function DeliveryTrackingPage() {
  const [searchParams] = useSearchParams();
  const campaignIdParam = searchParams.get('campaign_id');

  const [failedMessages, setFailedMessages] = useState([]);
  const [totalCount, setTotalCount] = useState(0);
  const [summaryData, setSummaryData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [retryingId, setRetryingId] = useState(null);
  const [retryingAll, setRetryingAll] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [channelFilter, setChannelFilter] = useState('');
  const [msg, setMsg] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    loadData();
  }, [campaignIdParam, channelFilter]);

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);
      const params = {};
      if (campaignIdParam) params.campaign_id = campaignIdParam;
      if (channelFilter) params.channel = channelFilter;

      const data = await listAllFailedMessages(params);
      setFailedMessages(data.items || []);
      setTotalCount(data.total || 0);

      if (campaignIdParam) {
        const sum = await getCampaignDeliverySummary(campaignIdParam);
        setSummaryData(sum);
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load delivery tracking data.');
    } finally {
      setLoading(false);
    }
  };

  const handleRetrySingle = async (messageId) => {
    try {
      setRetryingId(messageId);
      setError(null);
      const res = await retryMessage(messageId, true);
      setMsg(`Message #${messageId} retried: ${res.detail}`);
      loadData();
      setTimeout(() => setMsg(null), 4000);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to retry message.');
    } finally {
      setRetryingId(null);
    }
  };

  const handleRetryAll = async () => {
    if (!window.confirm('Are you sure you want to retry all eligible failed messages? Maximum 3 attempts per message.')) {
      return;
    }
    try {
      setRetryingAll(true);
      setError(null);
      const res = await retryAllFailedMessages();
      setMsg(
        `Batch retry completed: ${res.succeeded_count} succeeded, ${res.failed_count} failed (${res.retried_count} attempted).`
      );
      loadData();
      setTimeout(() => setMsg(null), 5000);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to execute batch retry.');
    } finally {
      setRetryingAll(false);
    }
  };

  const filteredMessages = failedMessages.filter((m) => {
    if (!searchTerm) return true;
    const term = searchTerm.toLowerCase();
    return (
      m.recipient_name?.toLowerCase().includes(term) ||
      m.recipient_address?.toLowerCase().includes(term) ||
      m.campaign_name?.toLowerCase().includes(term) ||
      m.tracking_id?.toLowerCase().includes(term) ||
      m.failure_reason?.toLowerCase().includes(term)
    );
  });

  const channelIcon = (ch) => {
    switch (ch) {
      case 'WhatsApp':
        return <MessageSquare className="w-3.5 h-3.5 text-emerald-600" />;
      case 'SMS':
        return <Smartphone className="w-3.5 h-3.5 text-blue-600" />;
      case 'Email':
        return <Mail className="w-3.5 h-3.5 text-indigo-600" />;
      case 'Push':
        return <Bell className="w-3.5 h-3.5 text-purple-600" />;
      case 'Web':
        return <Globe className="w-3.5 h-3.5 text-amber-600" />;
      default:
        return <Radio className="w-3.5 h-3.5 text-slate-600" />;
    }
  };

  return (
    <div className="p-4 sm:p-6 lg:p-8 max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight text-slate-900">Delivery Tracking & Retries</h1>
            <span className="text-xs font-bold uppercase tracking-wider px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-700 border border-indigo-200">
              Task 15
            </span>
          </div>
          <p className="text-sm text-slate-500 mt-1">
            Real-time delivery verification, provider diagnostic failure tracking, and controlled 3-attempt retries
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={loadData}
            disabled={loading}
            className="inline-flex items-center gap-2 px-3 py-2 text-xs font-semibold rounded-lg bg-white border border-slate-300 text-slate-700 hover:bg-slate-50 shadow-2xs transition"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
          <button
            onClick={handleRetryAll}
            disabled={retryingAll || failedMessages.length === 0}
            className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-bold rounded-lg bg-indigo-600 text-white hover:bg-indigo-700 shadow-2xs transition disabled:opacity-50"
          >
            <RotateCcw className={`w-3.5 h-3.5 ${retryingAll ? 'animate-spin' : ''}`} />
            {retryingAll ? 'Retrying All...' : 'Retry All Eligible'}
          </button>
        </div>
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

      {/* Campaign Summary Cards (if filtered by campaign) */}
      {summaryData && (
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
          <div className="bg-white border border-slate-200 rounded-xl p-3 shadow-2xs text-center">
            <span className="text-[11px] font-semibold text-slate-500 uppercase block">Sent</span>
            <span className="text-lg font-bold text-slate-800">{summaryData.sent_count}</span>
          </div>
          <div className="bg-white border border-slate-200 rounded-xl p-3 shadow-2xs text-center">
            <span className="text-[11px] font-semibold text-emerald-600 uppercase block">Delivered</span>
            <span className="text-lg font-bold text-emerald-700">{summaryData.delivered_count}</span>
          </div>
          <div className="bg-white border border-slate-200 rounded-xl p-3 shadow-2xs text-center">
            <span className="text-[11px] font-semibold text-rose-600 uppercase block">Failed</span>
            <span className="text-lg font-bold text-rose-700">{summaryData.failed_count}</span>
          </div>
          <div className="bg-white border border-slate-200 rounded-xl p-3 shadow-2xs text-center">
            <span className="text-[11px] font-semibold text-indigo-600 uppercase block">Opened / Read</span>
            <span className="text-lg font-bold text-indigo-700">{summaryData.opened_count}</span>
          </div>
          <div className="bg-white border border-slate-200 rounded-xl p-3 shadow-2xs text-center">
            <span className="text-[11px] font-semibold text-amber-600 uppercase block">Retried</span>
            <span className="text-lg font-bold text-amber-700">{summaryData.retried_count}</span>
          </div>
        </div>
      )}

      {/* Search & Filters */}
      <div className="bg-white border border-slate-200 rounded-xl p-3 shadow-2xs flex flex-col sm:flex-row items-center gap-3">
        <div className="relative flex-1 w-full">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
          <input
            type="text"
            placeholder="Search by recipient, campaign, tracking ID, or failure reason..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full text-xs pl-9 pr-3 py-2 border border-slate-300 rounded-lg focus:ring-1 focus:ring-indigo-500"
          />
        </div>

        <div className="flex items-center gap-2 w-full sm:w-auto">
          <Filter className="w-4 h-4 text-slate-400 shrink-0" />
          <select
            value={channelFilter}
            onChange={(e) => setChannelFilter(e.target.value)}
            className="text-xs px-3 py-2 border border-slate-300 rounded-lg bg-white w-full sm:w-40"
          >
            <option value="">All Channels</option>
            <option value="WhatsApp">WhatsApp</option>
            <option value="SMS">SMS</option>
            <option value="Email">Email</option>
            <option value="Push">Push</option>
          </select>
        </div>
      </div>

      {/* Messages Table */}
      <div className="bg-white border border-slate-200 rounded-xl overflow-hidden shadow-2xs">
        <div className="px-4 py-3 border-b border-slate-200 bg-slate-50 flex items-center justify-between">
          <h3 className="text-xs font-bold text-slate-800 uppercase tracking-wider">
            Failed Delivery Queue ({filteredMessages.length} of {totalCount})
          </h3>
          <span className="text-[11px] text-slate-500 font-mono">Max 3 attempts ceiling enforced</span>
        </div>

        {loading ? (
          <div className="text-center py-16">
            <RefreshCw className="w-6 h-6 text-indigo-500 animate-spin mx-auto mb-2" />
            <p className="text-xs text-slate-500">Loading delivery records...</p>
          </div>
        ) : filteredMessages.length === 0 ? (
          <div className="text-center py-16">
            <CheckCircle2 className="w-10 h-10 text-emerald-500 mx-auto mb-2" />
            <h4 className="text-sm font-bold text-slate-800">No failed messages found</h4>
            <p className="text-xs text-slate-500 mt-1">
              All messages are either successfully Delivered or there are no delivery issues matching your filters.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 border-b border-slate-200 text-slate-600 font-semibold">
                <tr>
                  <th className="py-2.5 px-3">Tracking ID</th>
                  <th className="py-2.5 px-3">Recipient</th>
                  <th className="py-2.5 px-3">Campaign</th>
                  <th className="py-2.5 px-3">Channel</th>
                  <th className="py-2.5 px-3">Status</th>
                  <th className="py-2.5 px-3 text-center">Attempts</th>
                  <th className="py-2.5 px-3">Diagnostic Failure Reason</th>
                  <th className="py-2.5 px-3">Last Attempt</th>
                  <th className="py-2.5 px-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {filteredMessages.map((m) => (
                  <tr key={m.id} className="hover:bg-slate-50/50 transition">
                    <td className="py-2.5 px-3 font-mono text-[11px] text-slate-600 truncate max-w-[120px]" title={m.tracking_id}>
                      {m.tracking_id}
                    </td>
                    <td className="py-2.5 px-3">
                      <span className="font-semibold text-slate-800 block">{m.recipient_name}</span>
                      <span className="text-[11px] text-slate-500 font-mono block">{m.recipient_address}</span>
                    </td>
                    <td className="py-2.5 px-3">
                      <Link
                        to={`/campaigns/${m.campaign_id}`}
                        className="text-indigo-600 hover:text-indigo-800 font-medium truncate block max-w-[150px]"
                        title={m.campaign_name}
                      >
                        {m.campaign_name || `#${m.campaign_id}`}
                      </Link>
                    </td>
                    <td className="py-2.5 px-3">
                      <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded bg-slate-100 text-slate-700 font-semibold text-[11px]">
                        {channelIcon(m.channel)}
                        {m.channel}
                      </span>
                    </td>
                    <td className="py-2.5 px-3">
                      <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-rose-50 text-rose-700 border border-rose-200">
                        {m.status}
                      </span>
                    </td>
                    <td className="py-2.5 px-3 text-center font-bold">
                      <span className={m.retry_count >= m.max_retries ? 'text-rose-600' : 'text-slate-700'}>
                        {m.retry_count} / {m.max_retries}
                      </span>
                    </td>
                    <td className="py-2.5 px-3 text-slate-600 max-w-[200px] truncate" title={m.failure_reason}>
                      {m.failure_reason || '—'}
                    </td>
                    <td className="py-2.5 px-3 text-slate-500 whitespace-nowrap text-[11px]">
                      {new Date(m.updated_at).toLocaleTimeString()}
                    </td>
                    <td className="py-2.5 px-3 text-right">
                      {m.can_retry ? (
                        <button
                          onClick={() => handleRetrySingle(m.id)}
                          disabled={retryingId === m.id}
                          className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-semibold rounded-md bg-indigo-50 text-indigo-700 hover:bg-indigo-100 border border-indigo-200 transition"
                        >
                          <RotateCcw className={`w-3 h-3 ${retryingId === m.id ? 'animate-spin' : ''}`} />
                          Retry
                        </button>
                      ) : (
                        <span className="text-[11px] text-slate-400 font-medium">Exhausted</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
