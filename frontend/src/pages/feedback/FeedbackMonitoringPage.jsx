import React, { useState, useEffect } from 'react';
import {
  MessageSquare,
  Star,
  ThumbsUp,
  Minus,
  ThumbsDown,
  Filter,
  RefreshCw,
  Search,
  CheckCircle2,
  Clock,
  Send,
  AlertCircle,
  HelpCircle,
  Hash,
  Eye,
  ShieldCheck,
  ChevronDown,
  Globe,
  Radio,
  X,
  Loader2,
} from 'lucide-react';
import {
  listFeedback,
  resolveFeedback,
  replyToFeedback,
  getFeedbackTopics,
} from '../../services/campaignService';

export default function FeedbackMonitoringPage() {
  const [feedbacks, setFeedbacks] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState({
    positive: 0,
    neutral: 0,
    negative: 0,
    averageRating: 0.0,
  });

  // Filters
  const [sentimentFilter, setSentimentFilter] = useState('');
  const [channelFilter, setChannelFilter] = useState('');
  const [languageFilter, setLanguageFilter] = useState('');
  const [resolvedFilter, setResolvedFilter] = useState('');
  const [searchQuery, setSearchQuery] = useState('');

  // Topics and Keywords panel
  const [nlpTopics, setNlpTopics] = useState({
    keywords: [],
    topics: [],
    common_questions: [],
    concerns: [],
  });

  // Modals
  const [selectedFeedback, setSelectedFeedback] = useState(null);
  const [detailModalOpen, setDetailModalOpen] = useState(false);

  const [resolveModalOpen, setResolveModalOpen] = useState(false);
  const [resolveNotes, setResolveNotes] = useState('');
  const [resolving, setResolving] = useState(false);

  const [replyModalOpen, setReplyModalOpen] = useState(false);
  const [replyText, setReplyText] = useState('');
  const [replyChannelOverride, setReplyChannelOverride] = useState('');
  const [replying, setReplying] = useState(false);
  const [actionError, setActionError] = useState(null);
  const [actionSuccess, setActionSuccess] = useState(null);

  const fetchFeedbackData = async () => {
    try {
      setLoading(true);
      const params = {};
      if (sentimentFilter) params.sentiment = sentimentFilter;
      if (channelFilter) params.channel = channelFilter;
      if (languageFilter) params.language = languageFilter;
      if (resolvedFilter !== '') params.is_resolved = resolvedFilter === 'true';

      const data = await listFeedback(params);
      setFeedbacks(data.items || []);
      setTotal(data.total || 0);
      setStats({
        positive: data.positive_count || 0,
        neutral: data.neutral_count || 0,
        negative: data.negative_count || 0,
        averageRating: data.average_rating || 0.0,
      });

      // Also fetch topics
      const topicsData = await getFeedbackTopics();
      setNlpTopics(topicsData || {});
    } catch (err) {
      console.error('Failed to load feedback records:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchFeedbackData();
  }, [sentimentFilter, channelFilter, languageFilter, resolvedFilter]);

  const handleOpenResolve = (fb) => {
    setSelectedFeedback(fb);
    setResolveNotes('');
    setActionError(null);
    setResolveModalOpen(true);
  };

  const handleConfirmResolve = async () => {
    if (!selectedFeedback) return;
    try {
      setResolving(true);
      setActionError(null);
      await resolveFeedback(selectedFeedback.id, resolveNotes);
      setActionSuccess(`Feedback #${selectedFeedback.id} marked as resolved.`);
      setResolveModalOpen(false);
      fetchFeedbackData();
    } catch (err) {
      setActionError(err.response?.data?.detail || 'Failed to resolve feedback.');
    } finally {
      setResolving(false);
    }
  };

  const handleOpenReply = (fb) => {
    setSelectedFeedback(fb);
    setReplyText('');
    setReplyChannelOverride(fb.channel || 'SMS');
    setActionError(null);
    setReplyModalOpen(true);
  };

  const handleConfirmReply = async () => {
    if (!selectedFeedback || !replyText.trim()) return;
    try {
      setReplying(true);
      setActionError(null);
      const res = await replyToFeedback(
        selectedFeedback.id,
        replyText.trim(),
        replyChannelOverride || null
      );
      setActionSuccess(res.detail || 'Reply sent successfully.');
      setReplyModalOpen(false);
      fetchFeedbackData();
    } catch (err) {
      setActionError(err.response?.data?.detail || 'Failed to dispatch reply.');
    } finally {
      setReplying(false);
    }
  };

  const filteredItems = feedbacks.filter((fb) => {
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase();
    return (
      (fb.comment && fb.comment.toLowerCase().includes(q)) ||
      (fb.campaign_name && fb.campaign_name.toLowerCase().includes(q)) ||
      (fb.recipient_contact && fb.recipient_contact.toLowerCase().includes(q))
    );
  });

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Citizen Feedback Monitoring</h1>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-indigo-50 text-indigo-700 border border-indigo-200">
              Task 16 Sentiment AI
            </span>
          </div>
          <p className="text-sm text-slate-500 mt-1">
            Track citizen responses, monitor sentiment trends, and resolve inquiries across all communication channels.
          </p>
        </div>
        <button
          onClick={fetchFeedbackData}
          disabled={loading}
          className="inline-flex items-center gap-2 px-4 py-2 bg-white border border-slate-200 hover:bg-slate-50 text-slate-700 rounded-xl text-sm font-semibold shadow-xs transition"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin text-indigo-600' : ''}`} />
          Refresh
        </button>
      </div>

      {actionSuccess && (
        <div className="p-4 rounded-2xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-sm flex items-center justify-between">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0" />
            <span>{actionSuccess}</span>
          </div>
          <button onClick={() => setActionSuccess(null)} className="text-emerald-600 hover:text-emerald-800">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* KPI Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
        <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-xs">
          <div className="flex items-center justify-between text-slate-500 text-xs font-semibold uppercase">
            <span>Total Responses</span>
            <MessageSquare className="w-4 h-4 text-indigo-600" />
          </div>
          <div className="text-2xl font-extrabold text-slate-900 mt-2">{total}</div>
          <div className="text-xs text-slate-400 mt-1">Citizen feedback entries</div>
        </div>

        <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-xs">
          <div className="flex items-center justify-between text-slate-500 text-xs font-semibold uppercase">
            <span>Average Rating</span>
            <Star className="w-4 h-4 text-amber-500 fill-amber-500" />
          </div>
          <div className="text-2xl font-extrabold text-slate-900 mt-2">
            {stats.averageRating > 0 ? `${stats.averageRating} / 5` : 'N/A'}
          </div>
          <div className="text-xs text-amber-600 font-medium mt-1">1 to 5 star satisfaction</div>
        </div>

        <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-xs">
          <div className="flex items-center justify-between text-emerald-700 text-xs font-semibold uppercase">
            <span>Positive</span>
            <ThumbsUp className="w-4 h-4 text-emerald-600" />
          </div>
          <div className="text-2xl font-extrabold text-emerald-700 mt-2">{stats.positive}</div>
          <div className="text-xs text-emerald-600 mt-1">
            {total > 0 ? `${Math.round((stats.positive / total) * 100)}% of total` : '0%'}
          </div>
        </div>

        <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-xs">
          <div className="flex items-center justify-between text-slate-600 text-xs font-semibold uppercase">
            <span>Neutral</span>
            <Minus className="w-4 h-4 text-slate-500" />
          </div>
          <div className="text-2xl font-extrabold text-slate-800 mt-2">{stats.neutral}</div>
          <div className="text-xs text-slate-500 mt-1">
            {total > 0 ? `${Math.round((stats.neutral / total) * 100)}% of total` : '0%'}
          </div>
        </div>

        <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-xs">
          <div className="flex items-center justify-between text-red-600 text-xs font-semibold uppercase">
            <span>Negative</span>
            <ThumbsDown className="w-4 h-4 text-red-600" />
          </div>
          <div className="text-2xl font-extrabold text-red-700 mt-2">{stats.negative}</div>
          <div className="text-xs text-red-600 mt-1">
            {total > 0 ? `${Math.round((stats.negative / total) * 100)}% of total` : '0%'}
          </div>
        </div>
      </div>

      {/* NLP Topics & Citizen Questions Panel */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Prominent Topics */}
        <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs">
          <h3 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-3 flex items-center gap-1.5">
            <Radio className="w-3.5 h-3.5 text-indigo-600" />
            Detected Topics
          </h3>
          <div className="flex flex-wrap gap-2">
            {nlpTopics.topics && nlpTopics.topics.length > 0 ? (
              nlpTopics.topics.map((t, idx) => (
                <span
                  key={idx}
                  className="inline-flex items-center gap-1 px-3 py-1 rounded-xl bg-slate-50 border border-slate-200 text-xs font-semibold text-slate-700"
                >
                  {t.topic}
                  <span className="text-xs bg-slate-200/70 text-slate-600 px-1.5 py-0.2 rounded-md">
                    {t.count}
                  </span>
                </span>
              ))
            ) : (
              <p className="text-xs text-slate-400 italic">No topics extracted yet.</p>
            )}
          </div>
        </div>

        {/* Top Keywords */}
        <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs">
          <h3 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-3 flex items-center gap-1.5">
            <Hash className="w-3.5 h-3.5 text-indigo-600" />
            Frequent Keywords
          </h3>
          <div className="flex flex-wrap gap-1.5">
            {nlpTopics.keywords && nlpTopics.keywords.length > 0 ? (
              nlpTopics.keywords.slice(0, 10).map((k, idx) => (
                <span
                  key={idx}
                  className="px-2.5 py-1 rounded-lg bg-indigo-50/70 text-indigo-700 text-xs font-medium border border-indigo-100"
                >
                  #{k.keyword} <span className="text-indigo-400">({k.count})</span>
                </span>
              ))
            ) : (
              <p className="text-xs text-slate-400 italic">No keywords extracted yet.</p>
            )}
          </div>
        </div>

        {/* Common Questions */}
        <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs">
          <h3 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-3 flex items-center gap-1.5">
            <HelpCircle className="w-3.5 h-3.5 text-amber-500" />
            Common Citizen Questions
          </h3>
          <div className="space-y-1.5">
            {nlpTopics.common_questions && nlpTopics.common_questions.length > 0 ? (
              nlpTopics.common_questions.slice(0, 3).map((q, idx) => (
                <p key={idx} className="text-xs text-slate-600 bg-amber-50/50 p-2 rounded-xl border border-amber-100/60 line-clamp-2">
                  "{q}"
                </p>
              ))
            ) : (
              <p className="text-xs text-slate-400 italic">No direct questions identified.</p>
            )}
          </div>
        </div>
      </div>

      {/* Filter Toolbar */}
      <div className="bg-white p-4 rounded-2xl border border-slate-200 shadow-xs flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          {/* Search */}
          <div className="relative">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Search comment or citizen..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-9 pr-3 py-1.5 text-xs bg-slate-50 border border-slate-200 rounded-xl w-48 sm:w-60 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>

          {/* Sentiment Filter */}
          <select
            value={sentimentFilter}
            onChange={(e) => setSentimentFilter(e.target.value)}
            className="px-3 py-1.5 text-xs bg-slate-50 border border-slate-200 rounded-xl text-slate-700 font-medium focus:outline-none focus:ring-2 focus:ring-indigo-500"
          >
            <option value="">All Sentiments</option>
            <option value="Positive">Positive</option>
            <option value="Neutral">Neutral</option>
            <option value="Negative">Negative</option>
          </select>

          {/* Channel Filter */}
          <select
            value={channelFilter}
            onChange={(e) => setChannelFilter(e.target.value)}
            className="px-3 py-1.5 text-xs bg-slate-50 border border-slate-200 rounded-xl text-slate-700 font-medium focus:outline-none focus:ring-2 focus:ring-indigo-500"
          >
            <option value="">All Channels</option>
            <option value="Web">Web Portal</option>
            <option value="SMS">SMS Reply</option>
            <option value="WhatsApp">WhatsApp</option>
            <option value="Email">Email</option>
          </select>

          {/* Resolution Filter */}
          <select
            value={resolvedFilter}
            onChange={(e) => setResolvedFilter(e.target.value)}
            className="px-3 py-1.5 text-xs bg-slate-50 border border-slate-200 rounded-xl text-slate-700 font-medium focus:outline-none focus:ring-2 focus:ring-indigo-500"
          >
            <option value="">All Statuses</option>
            <option value="false">Unresolved</option>
            <option value="true">Resolved</option>
          </select>
        </div>

        <span className="text-xs text-slate-400">
          Showing {filteredItems.length} of {total} records
        </span>
      </div>

      {/* Feedback Table */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-xs overflow-hidden">
        {loading ? (
          <div className="p-12 text-center text-slate-500">
            <Loader2 className="w-8 h-8 animate-spin text-indigo-600 mx-auto mb-2" />
            <p className="text-sm font-medium">Loading feedback records...</p>
          </div>
        ) : filteredItems.length === 0 ? (
          <div className="p-12 text-center text-slate-500">
            <MessageSquare className="w-12 h-12 text-slate-300 mx-auto mb-3" />
            <h3 className="text-base font-bold text-slate-800">No Feedback Matches Found</h3>
            <p className="text-xs text-slate-400 mt-1 max-w-sm mx-auto">
              No feedback records match the current filter criteria. Try adjusting filters or search query.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="bg-slate-50/80 border-b border-slate-200 text-slate-500 font-semibold uppercase">
                  <th className="py-3.5 px-4">Rating & Sentiment</th>
                  <th className="py-3.5 px-4">Citizen Comment</th>
                  <th className="py-3.5 px-4">Campaign & Channel</th>
                  <th className="py-3.5 px-4">Citizen Contact</th>
                  <th className="py-3.5 px-4">Status</th>
                  <th className="py-3.5 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {filteredItems.map((fb) => {
                  let sentimentBadge = (
                    <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-slate-100 text-slate-700">
                      <Minus className="w-3 h-3 text-slate-400" />
                      Neutral
                    </span>
                  );
                  if (fb.sentiment_label === 'Positive') {
                    sentimentBadge = (
                      <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                        <ThumbsUp className="w-3 h-3 text-emerald-600" />
                        Positive ({fb.sentiment_score > 0 ? `+${fb.sentiment_score}` : fb.sentiment_score})
                      </span>
                    );
                  } else if (fb.sentiment_label === 'Negative') {
                    sentimentBadge = (
                      <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-red-50 text-red-700 border border-red-200">
                        <ThumbsDown className="w-3 h-3 text-red-600" />
                        Negative ({fb.sentiment_score})
                      </span>
                    );
                  }

                  return (
                    <tr key={fb.id} className="hover:bg-slate-50/50 transition">
                      <td className="py-3.5 px-4">
                        <div className="flex flex-col gap-1.5">
                          <div className="flex items-center gap-1">
                            {fb.rating ? (
                              [...Array(5)].map((_, i) => (
                                <Star
                                  key={i}
                                  className={`w-3.5 h-3.5 ${
                                    i < fb.rating ? 'fill-amber-400 text-amber-400' : 'text-slate-200'
                                  }`}
                                />
                              ))
                            ) : (
                              <span className="text-slate-400 text-xs">No star rating</span>
                            )}
                          </div>
                          <div>{sentimentBadge}</div>
                        </div>
                      </td>
                      <td className="py-3.5 px-4 max-w-xs sm:max-w-md">
                        <p className="text-slate-800 font-medium line-clamp-2">
                          {fb.comment || <span className="text-slate-400 italic">No comment provided</span>}
                        </p>
                        <span className="text-slate-400 text-[10px]">
                          Lang: {fb.language || 'en'} • {new Date(fb.created_at).toLocaleString()}
                        </span>
                      </td>
                      <td className="py-3.5 px-4">
                        <div className="font-semibold text-slate-800">{fb.campaign_name}</div>
                        <span className="inline-block mt-0.5 px-2 py-0.5 rounded-md bg-slate-100 text-slate-600 text-[10px] font-medium">
                          {fb.channel || 'Web'}
                        </span>
                      </td>
                      <td className="py-3.5 px-4">
                        <div className="font-medium text-slate-700">{fb.recipient_name}</div>
                        <div className="text-slate-400 text-[11px] font-mono">{fb.recipient_contact || 'Anonymous'}</div>
                      </td>
                      <td className="py-3.5 px-4">
                        {fb.is_resolved ? (
                          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                            <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                            Resolved
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-amber-50 text-amber-700 border border-amber-200">
                            <Clock className="w-3 h-3 text-amber-600" />
                            Pending
                          </span>
                        )}
                      </td>
                      <td className="py-3.5 px-4 text-right space-x-1.5 whitespace-nowrap">
                        <button
                          onClick={() => {
                            setSelectedFeedback(fb);
                            setDetailModalOpen(true);
                          }}
                          className="px-2.5 py-1 text-slate-600 hover:text-slate-900 bg-slate-100 hover:bg-slate-200 rounded-lg text-xs font-medium transition"
                        >
                          View
                        </button>
                        {!fb.is_resolved && (
                          <button
                            onClick={() => handleOpenResolve(fb)}
                            className="px-2.5 py-1 text-emerald-700 hover:text-emerald-900 bg-emerald-50 hover:bg-emerald-100 border border-emerald-200 rounded-lg text-xs font-semibold transition"
                          >
                            Resolve
                          </button>
                        )}
                        <button
                          onClick={() => handleOpenReply(fb)}
                          className="px-2.5 py-1 text-indigo-700 hover:text-indigo-900 bg-indigo-50 hover:bg-indigo-100 border border-indigo-200 rounded-lg text-xs font-semibold transition"
                        >
                          Reply
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Detail Modal */}
      {detailModalOpen && selectedFeedback && (
        <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-3xl shadow-2xl border border-slate-200 w-full max-w-lg p-6 space-y-4 animate-in fade-in duration-200">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <h3 className="text-base font-bold text-slate-900">Feedback Record #{selectedFeedback.id}</h3>
              <button onClick={() => setDetailModalOpen(false)} className="text-slate-400 hover:text-slate-600">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="space-y-3 text-xs text-slate-600">
              <div className="bg-slate-50 p-3 rounded-xl border border-slate-200/60 space-y-1">
                <p><strong>Campaign:</strong> {selectedFeedback.campaign_name}</p>
                <p><strong>Channel:</strong> {selectedFeedback.channel} • <strong>Language:</strong> {selectedFeedback.language}</p>
                <p><strong>Citizen:</strong> {selectedFeedback.recipient_name} ({selectedFeedback.recipient_contact})</p>
                <p><strong>Submitted:</strong> {new Date(selectedFeedback.created_at).toLocaleString()}</p>
              </div>
              <div>
                <p className="font-semibold text-slate-700 mb-1">Citizen Comment:</p>
                <div className="p-3 rounded-xl bg-slate-100 text-slate-800 italic">
                  "{selectedFeedback.comment || 'No comment text provided'}"
                </div>
              </div>
              <div className="flex items-center justify-between p-3 rounded-xl bg-slate-50 border border-slate-200/60">
                <span>Rating: <strong>{selectedFeedback.rating || 'N/A'} Stars</strong></span>
                <span>Sentiment: <strong>{selectedFeedback.sentiment_label} ({selectedFeedback.sentiment_score})</strong></span>
              </div>
              {selectedFeedback.is_resolved && (
                <div className="p-3 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800">
                  <p className="font-semibold">Resolution Notes:</p>
                  <p className="mt-0.5">{selectedFeedback.resolution_notes || 'Marked as resolved'}</p>
                  {selectedFeedback.resolved_at && (
                    <p className="text-[10px] text-emerald-600 mt-1">Resolved at {new Date(selectedFeedback.resolved_at).toLocaleString()}</p>
                  )}
                </div>
              )}
            </div>
            <div className="pt-2 flex justify-end gap-2">
              <button
                onClick={() => setDetailModalOpen(false)}
                className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl text-xs font-semibold"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Resolve Modal */}
      {resolveModalOpen && selectedFeedback && (
        <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-3xl shadow-2xl border border-slate-200 w-full max-w-md p-6 space-y-4 animate-in fade-in duration-200">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <h3 className="text-base font-bold text-slate-900">Resolve Citizen Feedback</h3>
              <button onClick={() => setResolveModalOpen(false)} className="text-slate-400 hover:text-slate-600">
                <X className="w-5 h-5" />
              </button>
            </div>
            {actionError && (
              <div className="p-3 rounded-xl bg-red-50 text-red-700 text-xs border border-red-200">
                {actionError}
              </div>
            )}
            <p className="text-xs text-slate-600">
              Provide resolution notes summarizing the corrective action taken or inquiry handled:
            </p>
            <textarea
              rows={3}
              value={resolveNotes}
              onChange={(e) => setResolveNotes(e.target.value)}
              placeholder="e.g. Center timing verified and medical officer deployed additional nurse..."
              className="w-full p-3 rounded-xl border border-slate-300 text-xs text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
            <div className="flex justify-end gap-2 pt-2">
              <button
                onClick={() => setResolveModalOpen(false)}
                className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl text-xs font-semibold"
              >
                Cancel
              </button>
              <button
                onClick={handleConfirmResolve}
                disabled={resolving}
                className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-xs font-semibold flex items-center gap-1.5 disabled:opacity-50"
              >
                {resolving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <CheckCircle2 className="w-3.5 h-3.5" />}
                Confirm Resolution
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Reply Modal */}
      {replyModalOpen && selectedFeedback && (
        <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-3xl shadow-2xl border border-slate-200 w-full max-w-lg p-6 space-y-4 animate-in fade-in duration-200">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <h3 className="text-base font-bold text-slate-900">Reply to Citizen Response</h3>
              <button onClick={() => setReplyModalOpen(false)} className="text-slate-400 hover:text-slate-600">
                <X className="w-5 h-5" />
              </button>
            </div>
            {actionError && (
              <div className="p-3 rounded-xl bg-red-50 text-red-700 text-xs border border-red-200">
                {actionError}
              </div>
            )}
            <div className="p-3 rounded-xl bg-slate-50 border border-slate-200 text-xs text-slate-600 space-y-1">
              <p><strong>Recipient:</strong> {selectedFeedback.recipient_name} ({selectedFeedback.recipient_contact})</p>
              <p><strong>Citizen Inquired / Remarked:</strong> "{selectedFeedback.comment || 'No comment text'}"</p>
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Dispatch Channel:</label>
              <select
                value={replyChannelOverride}
                onChange={(e) => setReplyChannelOverride(e.target.value)}
                className="w-full p-2.5 rounded-xl border border-slate-300 text-xs text-slate-800 bg-white"
              >
                <option value="SMS">SMS Gateway</option>
                <option value="WhatsApp">Meta WhatsApp Official</option>
                <option value="Email">Official Email</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Official Response Text:</label>
              <textarea
                rows={4}
                value={replyText}
                onChange={(e) => setReplyText(e.target.value)}
                placeholder="Type your official government response..."
                className="w-full p-3 rounded-xl border border-slate-300 text-xs text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button
                onClick={() => setReplyModalOpen(false)}
                className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl text-xs font-semibold"
              >
                Cancel
              </button>
              <button
                onClick={handleConfirmReply}
                disabled={replying || !replyText.trim()}
                className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl text-xs font-semibold flex items-center gap-1.5 disabled:opacity-50"
              >
                {replying ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
                Dispatch Reply
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
