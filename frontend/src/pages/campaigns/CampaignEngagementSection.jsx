import React, { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import {
  MessageSquareHeart,
  Eye,
  MousePointer,
  MessageSquare,
  Sparkles,
  RefreshCw,
  Star,
  ExternalLink,
  HelpCircle,
  AlertTriangle,
  Tag,
  Layers,
  Globe,
  Radio,
  CheckCircle2,
} from 'lucide-react';
import { getCampaignEngagement } from '../../services/campaignService';

export default function CampaignEngagementSection({ campaign, isOwner }) {
  const [metrics, setMetrics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');

  const fetchMetrics = useCallback(
    async (isManualRefresh = false) => {
      if (!campaign?.id) return;
      if (isManualRefresh) {
        setRefreshing(true);
      } else {
        setLoading(true);
      }
      setError('');
      try {
        const data = await getCampaignEngagement(campaign.id);
        setMetrics(data);
      } catch (err) {
        console.error('Failed to load campaign engagement metrics:', err);
        setError(err.response?.data?.detail || 'Unable to load engagement metrics.');
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [campaign?.id]
  );

  useEffect(() => {
    fetchMetrics();
  }, [fetchMetrics]);

  if (loading) {
    return (
      <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-xs flex items-center justify-center py-12">
        <div className="flex items-center gap-2.5 text-slate-500 text-sm">
          <RefreshCw className="w-4 h-4 animate-spin text-brand-600" />
          <span>Calculating live engagement and sentiment analytics...</span>
        </div>
      </div>
    );
  }

  const sentiment = metrics?.sentiment_distribution || {
    positive: 0,
    neutral: 0,
    negative: 0,
    positive_pct: 0,
    neutral_pct: 0,
    negative_pct: 0,
    average_score: 0,
  };

  const hasEvents =
    (metrics?.total_delivered || 0) > 0 ||
    (metrics?.unique_opens || 0) > 0 ||
    (metrics?.unique_clicks || 0) > 0 ||
    (metrics?.replies_count || 0) > 0 ||
    (metrics?.participations_count || 0) > 0;

  return (
    <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-xs space-y-6">
      {/* Section Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-100 pb-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-purple-50 text-purple-700 border border-purple-200 flex items-center justify-center shadow-2xs">
            <MessageSquareHeart className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-lg font-bold text-slate-900 tracking-tight">
                Engagement Tracking & Sentiment Analysis
              </h2>
              <span className="px-2 py-0.5 text-[11px] font-bold rounded-full bg-purple-100 text-purple-800">
                Milestone 3
              </span>
            </div>
            <p className="text-xs text-slate-500">
              Live citizen opens, link click tracking, WhatsApp/SMS replies, and multilingual sentiment.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 self-start sm:self-auto">
          <button
            type="button"
            onClick={() => fetchMetrics(true)}
            disabled={refreshing}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg bg-slate-100 text-slate-700 hover:bg-slate-200 border border-slate-200 transition"
            title="Refresh engagement data"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin text-brand-600' : ''}`} />
            <span>{refreshing ? 'Refreshing...' : 'Refresh'}</span>
          </button>

          <Link
            to={`/feedback?campaign_id=${campaign.id}`}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg bg-brand-600 text-white hover:bg-brand-700 shadow-2xs transition"
          >
            <span>View Citizen Feedback</span>
            <ExternalLink className="w-3.5 h-3.5" />
          </Link>
        </div>
      </div>

      {error && (
        <div className="p-3.5 rounded-xl bg-amber-50 border border-amber-200 text-xs text-amber-800 flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 flex-shrink-0 text-amber-600" />
          <span>{error}</span>
        </div>
      )}

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3.5">
        {/* Opens */}
        <div className="bg-slate-50 p-4 rounded-xl border border-slate-200/80 space-y-1">
          <div className="flex items-center justify-between text-slate-500">
            <span className="text-[11px] font-bold uppercase tracking-wider">Unique Opens</span>
            <Eye className="w-4 h-4 text-blue-600" />
          </div>
          <div className="flex items-baseline gap-1.5">
            <span className="text-2xl font-black text-slate-900">{metrics?.unique_opens || 0}</span>
            <span className="text-xs font-semibold text-blue-700">({metrics?.open_rate || 0}%)</span>
          </div>
          <p className="text-[10px] text-slate-500 truncate">
            {metrics?.total_opens || 0} total opens ({metrics?.total_delivered || 0} delivered)
          </p>
        </div>

        {/* Link Clicks */}
        <div className="bg-slate-50 p-4 rounded-xl border border-slate-200/80 space-y-1">
          <div className="flex items-center justify-between text-slate-500">
            <span className="text-[11px] font-bold uppercase tracking-wider">Link Clicks</span>
            <MousePointer className="w-4 h-4 text-emerald-600" />
          </div>
          <div className="flex items-baseline gap-1.5">
            <span className="text-2xl font-black text-slate-900">{metrics?.unique_clicks || 0}</span>
            <span className="text-xs font-semibold text-emerald-700">({metrics?.click_through_rate || 0}%)</span>
          </div>
          <p className="text-[10px] text-slate-500 truncate">
            {metrics?.total_clicks || 0} total clicks (CTOR: {metrics?.click_to_open_rate || 0}%)
          </p>
        </div>

        {/* Replies */}
        <div className="bg-slate-50 p-4 rounded-xl border border-slate-200/80 space-y-1">
          <div className="flex items-center justify-between text-slate-500">
            <span className="text-[11px] font-bold uppercase tracking-wider">Citizen Replies</span>
            <MessageSquare className="w-4 h-4 text-purple-600" />
          </div>
          <div className="flex items-baseline gap-1.5">
            <span className="text-2xl font-black text-slate-900">{metrics?.replies_count || 0}</span>
            <span className="text-xs font-semibold text-purple-700">({metrics?.response_rate || 0}%)</span>
          </div>
          <p className="text-[10px] text-slate-500 truncate">Inbound SMS & WhatsApp messages</p>
        </div>

        {/* Participation */}
        <div className="bg-slate-50 p-4 rounded-xl border border-slate-200/80 space-y-1">
          <div className="flex items-center justify-between text-slate-500">
            <span className="text-[11px] font-bold uppercase tracking-wider">Feedback Form</span>
            <Sparkles className="w-4 h-4 text-amber-600" />
          </div>
          <div className="flex items-baseline gap-1.5">
            <span className="text-2xl font-black text-slate-900">{metrics?.participations_count || 0}</span>
            <span className="text-xs font-semibold text-amber-700">({metrics?.participation_rate || 0}%)</span>
          </div>
          <p className="text-[10px] text-slate-500 truncate">Public token submissions</p>
        </div>

        {/* Citizen Rating */}
        <div className="bg-slate-50 p-4 rounded-xl border border-slate-200/80 space-y-1 col-span-2 md:col-span-1">
          <div className="flex items-center justify-between text-slate-500">
            <span className="text-[11px] font-bold uppercase tracking-wider">Average Rating</span>
            <Star className="w-4 h-4 text-amber-500 fill-amber-500" />
          </div>
          <div className="flex items-baseline gap-1.5">
            <span className="text-2xl font-black text-slate-900">
              {metrics?.average_rating > 0 ? metrics.average_rating.toFixed(1) : '—'}
            </span>
            <span className="text-xs font-medium text-slate-500">/ 5.0</span>
          </div>
          <p className="text-[10px] text-slate-500 truncate">
            Polarity: {sentiment.average_score ? (sentiment.average_score > 0 ? `+${sentiment.average_score.toFixed(2)}` : sentiment.average_score.toFixed(2)) : '0.00'}
          </p>
        </div>
      </div>

      {!hasEvents && (
        <div className="p-4 bg-slate-50 border border-dashed border-slate-200 rounded-xl text-center space-y-1">
          <p className="text-xs font-semibold text-slate-700">No interaction events recorded yet</p>
          <p className="text-[11px] text-slate-500">
            Engagement tracking records email opens, link clicks, and citizen feedback automatically once messages are delivered.
          </p>
        </div>
      )}

      {/* Two-Column Deep-Dive */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left: Sentiment Analysis & NLP Topics */}
        <div className="bg-slate-50/60 rounded-xl p-5 border border-slate-200 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-brand-600" />
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-800">
                Citizen Sentiment & NLP Extraction
              </h3>
            </div>
            <span className="text-[11px] text-slate-500">
              {sentiment.positive + sentiment.neutral + sentiment.negative} feedback entries
            </span>
          </div>

          {/* Sentiment Proportion Bar */}
          <div className="space-y-1.5">
            <div className="flex justify-between text-[11px] font-semibold text-slate-600">
              <span className="text-emerald-700">Positive: {sentiment.positive_pct}% ({sentiment.positive})</span>
              <span className="text-slate-600">Neutral: {sentiment.neutral_pct}% ({sentiment.neutral})</span>
              <span className="text-rose-700">Negative: {sentiment.negative_pct}% ({sentiment.negative})</span>
            </div>
            <div className="h-2.5 w-full bg-slate-200 rounded-full overflow-hidden flex">
              <div
                style={{ width: `${sentiment.positive_pct}%` }}
                className="bg-emerald-500 transition-all duration-500"
                title={`Positive: ${sentiment.positive_pct}%`}
              />
              <div
                style={{ width: `${sentiment.neutral_pct}%` }}
                className="bg-slate-400 transition-all duration-500"
                title={`Neutral: ${sentiment.neutral_pct}%`}
              />
              <div
                style={{ width: `${sentiment.negative_pct}%` }}
                className="bg-rose-500 transition-all duration-500"
                title={`Negative: ${sentiment.negative_pct}%`}
              />
            </div>
          </div>

          {/* Detected Topics & Frequent Keywords */}
          <div className="space-y-2 pt-2 border-t border-slate-200">
            <div className="flex items-center gap-1.5 text-xs font-bold text-slate-700">
              <Tag className="w-3.5 h-3.5 text-slate-500" />
              <span>Extracted Topics & Keyword Frequency</span>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {metrics?.top_topics?.length > 0
                ? metrics.top_topics.map((t) => (
                    <span
                      key={t.topic}
                      className="px-2 py-1 rounded-md text-[11px] font-semibold bg-purple-100 text-purple-800 border border-purple-200"
                    >
                      {t.topic} ({t.count})
                    </span>
                  ))
                : null}
              {metrics?.top_keywords?.length > 0
                ? metrics.top_keywords.map((k) => (
                    <span
                      key={k.keyword}
                      className="px-2 py-0.5 rounded-md text-[11px] font-medium bg-white text-slate-700 border border-slate-200"
                    >
                      #{k.keyword} ({k.count})
                    </span>
                  ))
                : null}
              {(!metrics?.top_topics || metrics.top_topics.length === 0) &&
                (!metrics?.top_keywords || metrics.top_keywords.length === 0) && (
                  <span className="text-[11px] text-slate-400 italic">
                    Keywords and topics will be automatically extracted from citizen messages.
                  </span>
                )}
            </div>
          </div>

          {/* Common Questions & Concerns */}
          {(metrics?.common_questions?.length > 0 || metrics?.concerns?.length > 0) && (
            <div className="space-y-2 pt-2 border-t border-slate-200">
              {metrics?.common_questions?.length > 0 && (
                <div className="space-y-1">
                  <div className="flex items-center gap-1.5 text-[11px] font-bold text-slate-700">
                    <HelpCircle className="w-3.5 h-3.5 text-blue-600" />
                    <span>Frequently Asked Questions</span>
                  </div>
                  <ul className="text-xs text-slate-600 space-y-1 pl-4 list-disc">
                    {metrics.common_questions.map((q, idx) => (
                      <li key={idx} className="leading-snug">
                        {q}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {metrics?.concerns?.length > 0 && (
                <div className="space-y-1 pt-1">
                  <div className="flex items-center gap-1.5 text-[11px] font-bold text-rose-800">
                    <AlertTriangle className="w-3.5 h-3.5 text-rose-600" />
                    <span>Citizen Concerns Flagged</span>
                  </div>
                  <ul className="text-xs text-rose-700 space-y-1 pl-4 list-disc">
                    {metrics.concerns.map((c, idx) => (
                      <li key={idx} className="leading-snug">
                        {c}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Right: Breakdown by Channel & Language */}
        <div className="bg-slate-50/60 rounded-xl p-5 border border-slate-200 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Radio className="w-4 h-4 text-brand-600" />
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-800">
                Channel Performance Breakdown
              </h3>
            </div>
            <span className="text-[11px] text-slate-500">Multi-channel routing</span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-slate-200 text-slate-500 uppercase text-[10px] tracking-wider">
                  <th className="pb-2 font-semibold">Channel</th>
                  <th className="pb-2 font-semibold">Delivered</th>
                  <th className="pb-2 font-semibold">Opens</th>
                  <th className="pb-2 font-semibold">Clicks</th>
                  <th className="pb-2 font-semibold">Replies</th>
                  <th className="pb-2 font-semibold">Open Rate</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200/60 font-mono text-[11px]">
                {metrics?.by_channel && Object.keys(metrics.by_channel).length > 0 ? (
                  Object.entries(metrics.by_channel).map(([ch, data]) => (
                    <tr key={ch} className="hover:bg-slate-100/50">
                      <td className="py-2 font-sans font-bold text-slate-800">{ch}</td>
                      <td className="py-2 text-slate-600">{data.delivered}</td>
                      <td className="py-2 text-blue-600 font-semibold">{data.opens}</td>
                      <td className="py-2 text-emerald-600 font-semibold">{data.clicks}</td>
                      <td className="py-2 text-purple-600 font-semibold">{data.replies}</td>
                      <td className="py-2 font-sans font-semibold text-slate-800">{data.open_rate}%</td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan="6" className="py-3 text-center text-slate-400 font-sans italic">
                      No channel delivery metrics recorded yet.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          {/* Language Breakdown */}
          <div className="pt-3 border-t border-slate-200 space-y-2">
            <div className="flex items-center gap-1.5 text-xs font-bold text-slate-700">
              <Globe className="w-3.5 h-3.5 text-slate-500" />
              <span>Engagement by Recipient Language</span>
            </div>
            <div className="grid grid-cols-3 gap-2">
              {metrics?.by_language && Object.keys(metrics.by_language).length > 0 ? (
                Object.entries(metrics.by_language).map(([lang, ldata]) => (
                  <div
                    key={lang}
                    className="p-2 bg-white rounded-lg border border-slate-200 text-center space-y-0.5"
                  >
                    <span className="text-[11px] font-bold uppercase text-slate-800 block">
                      {lang === 'en' ? 'English' : lang === 'hi' ? 'Hindi' : lang === 'ta' ? 'Tamil' : lang}
                    </span>
                    <span className="text-xs font-mono font-semibold text-brand-700 block">
                      {ldata.opens + ldata.clicks + ldata.replies} interactions
                    </span>
                    <span className="text-[10px] text-slate-400 block">
                      {ldata.delivered} delivered
                    </span>
                  </div>
                ))
              ) : (
                <div className="col-span-3 text-[11px] text-slate-400 italic">
                  Multilingual metrics will populate as citizen interactions occur.
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
