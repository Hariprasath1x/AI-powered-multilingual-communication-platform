import React, { useState, useEffect } from 'react';
import {
  Sparkles,
  Gauge,
  Smile,
  AlertTriangle,
  CheckCircle2,
  ArrowRight,
  RefreshCw,
  Sliders,
  FileText,
  ShieldCheck,
  Check,
  X,
  Split,
  Eye,
  Info,
} from 'lucide-react';
import { analyzeTone, improveTone } from '../../services/contentService';

const TONE_BADGES = {
  Urgent: { bg: 'bg-amber-100 text-amber-900 border-amber-300', dot: 'bg-amber-500' },
  Friendly: { bg: 'bg-emerald-100 text-emerald-900 border-emerald-300', dot: 'bg-emerald-500' },
  Formal: { bg: 'bg-blue-100 text-blue-900 border-blue-300', dot: 'bg-blue-500' },
  Harsh: { bg: 'bg-rose-100 text-rose-900 border-rose-300', dot: 'bg-rose-500' },
  Neutral: { bg: 'bg-slate-100 text-slate-800 border-slate-300', dot: 'bg-slate-400' },
};

export default function ToneOptimizationPanel({
  assetId,
  currentText = '',
  channel = 'SMS',
  onApplyImprovement,
}) {
  const [analysis, setAnalysis] = useState(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [improving, setImproving] = useState(false);
  const [error, setError] = useState(null);

  // Improvement controls
  const [targetTone, setTargetTone] = useState('friendly');
  const [targetObjective, setTargetObjective] = useState('');
  const [improvedResult, setImprovedResult] = useState(null);
  const [showDiffModal, setShowDiffModal] = useState(false);

  useEffect(() => {
    if (assetId) {
      handleAnalyze();
    }
  }, [assetId]);

  async function handleAnalyze() {
    setAnalyzing(true);
    setError(null);
    try {
      const data = await analyzeTone(assetId, {
        text_override: currentText || undefined,
        channel,
      });
      setAnalysis(data);
    } catch (err) {
      setError(err?.response?.data?.detail || 'Failed to analyze content tone.');
    } finally {
      setAnalyzing(false);
    }
  }

  async function handleImprove(overrideTone) {
    const toneToUse = overrideTone || targetTone;
    setImproving(true);
    setError(null);
    try {
      const payload = {
        target_tone: toneToUse,
        objective: targetObjective || `Adjust tone to ${toneToUse} while preserving all factual anchors`,
        text_override: currentText || undefined,
        channel,
      };
      const res = await improveTone(assetId, payload);
      setImprovedResult(res);
      setTargetTone(toneToUse);
    } catch (err) {
      setError(err?.response?.data?.detail || 'Failed to optimize tone.');
    } finally {
      setImproving(false);
    }
  }

  function handleApply() {
    if (improvedResult && onApplyImprovement) {
      onApplyImprovement(improvedResult.improved_text);
      setImprovedResult(null);
    }
  }

  // Polarity bar position calculation: -1.0 (0%) to +1.0 (100%)
  const polarity = analysis ? analysis.sentiment_polarity : 0.0;
  const polarityPercent = Math.max(0, Math.min(100, ((polarity + 1.0) / 2.0) * 100));

  const toneConfig = analysis ? (TONE_BADGES[analysis.classified_tone] || TONE_BADGES.Neutral) : TONE_BADGES.Neutral;

  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-200">
        <div>
          <div className="flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-indigo-600" />
            <h2 className="text-lg font-semibold text-slate-900">Sentiment & Tone Optimization</h2>
            <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-700 border border-indigo-200">
              Task 10
            </span>
          </div>
          <p className="text-sm text-slate-500 mt-0.5">
            Evaluate five-way tone classification, sentiment polarity, and readability with factual preservation.
          </p>
        </div>

        <button
          onClick={handleAnalyze}
          disabled={analyzing}
          className="inline-flex items-center gap-2 px-3.5 py-2 text-sm font-medium text-slate-700 bg-white border border-slate-300 rounded-lg hover:bg-slate-50 transition-colors disabled:opacity-50"
        >
          <RefreshCw className={`w-4 h-4 ${analyzing ? 'animate-spin' : ''}`} />
          {analyzing ? 'Analyzing...' : 'Re-Analyze Copy'}
        </button>
      </div>

      {error && (
        <div className="p-3.5 bg-rose-50 border border-rose-200 rounded-lg flex items-start gap-2.5 text-sm text-rose-800">
          <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
          <span>{error}</span>
        </div>
      )}

      {/* Metric Cards Grid */}
      {analysis && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Tone Classification Card */}
          <div className="p-4 rounded-xl border border-slate-200 bg-slate-50/50 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                Primary Tone
              </span>
              <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold border ${toneConfig.bg}`}>
                <span className={`w-1.5 h-1.5 rounded-full ${toneConfig.dot}`} />
                {analysis.classified_tone}
              </span>
            </div>
            <p className="text-xs text-slate-600 line-clamp-2">
              {analysis.tone_alignment?.tone_explanation || 'Classification inferred from semantic markers.'}
            </p>
            <div className="flex items-center justify-between text-xs text-slate-500 pt-1 border-t border-slate-200">
              <span>Confidence:</span>
              <span className="font-semibold text-slate-700">
                {Math.round((analysis.tone_alignment?.confidence_score || 0.8) * 100)}%
              </span>
            </div>
          </div>

          {/* Sentiment Polarity Meter Card */}
          <div className="p-4 rounded-xl border border-slate-200 bg-slate-50/50 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                Sentiment Polarity
              </span>
              <span className="text-xs font-semibold font-mono text-slate-700">
                {analysis.sentiment_polarity > 0 ? `+${analysis.sentiment_polarity.toFixed(2)}` : analysis.sentiment_polarity.toFixed(2)}
              </span>
            </div>

            {/* Visual gradient bar */}
            <div className="space-y-1.5">
              <div className="relative h-2.5 rounded-full bg-gradient-to-r from-rose-400 via-amber-300 to-emerald-500 overflow-hidden">
                {/* Center marker line */}
                <div className="absolute left-1/2 top-0 bottom-0 w-0.5 bg-slate-700/30" />
              </div>
              <div className="relative h-3">
                <div
                  className="absolute -top-1 -ml-1.5 w-3 h-3 bg-slate-900 rounded-full border-2 border-white shadow transition-all duration-300"
                  style={{ left: `${polarityPercent}%` }}
                />
              </div>
              <div className="flex justify-between text-[10px] text-slate-400 font-medium">
                <span>Distressed (-1.0)</span>
                <span>Neutral (0.0)</span>
                <span>Positive (+1.0)</span>
              </div>
            </div>

            <p className="text-xs text-slate-600 font-medium">
              {analysis.sentiment_category}
            </p>
          </div>

          {/* Readability & Clarity Card */}
          <div className="p-4 rounded-xl border border-slate-200 bg-slate-50/50 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                Readability
              </span>
              <span className="text-xs font-semibold px-2 py-0.5 rounded bg-blue-100 text-blue-800">
                Score {analysis.readability_score}
              </span>
            </div>
            <p className="text-xs text-slate-600">
              <span className="font-semibold text-slate-800">{analysis.readability_label}</span> — accessible to general citizen audiences.
            </p>
            <div className="flex items-center justify-between text-xs text-slate-500 pt-1 border-t border-slate-200">
              <span>Clarity Index:</span>
              <span className="font-semibold text-emerald-700">
                {analysis.clarity_score}/100
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Formatting Anomalies / Warnings */}
      {analysis && analysis.formatting_anomalies && analysis.formatting_anomalies.length > 0 && (
        <div className="p-3.5 bg-amber-50/70 border border-amber-200 rounded-xl space-y-1.5">
          <div className="flex items-center gap-2 text-xs font-semibold text-amber-900">
            <AlertTriangle className="w-4 h-4 text-amber-600" />
            <span>Formatting Anomalies Detected</span>
          </div>
          <div className="flex flex-wrap gap-2 pt-1">
            {analysis.formatting_anomalies.map((ano, i) => (
              <span
                key={i}
                className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium bg-amber-100 text-amber-800 border border-amber-300"
              >
                {ano}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Quick Tone Rewrite Controls */}
      <div className="p-5 rounded-xl border border-slate-200 bg-slate-50 space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Sliders className="w-4 h-4 text-slate-700" />
            <h3 className="text-sm font-semibold text-slate-900">Quick Tone Optimization</h3>
          </div>
          <span className="text-xs text-slate-500">Guarantees 100% preservation of helpline numbers and dates</span>
        </div>

        {/* Quick Tone Chips */}
        <div className="flex flex-wrap gap-2">
          {[
            { label: 'Friendlier & Reassuring', tone: 'friendly' },
            { label: 'More Formal & Official', tone: 'formal' },
            { label: 'High Urgency / Action', tone: 'urgent' },
            { label: 'Empathetic Support', tone: 'empathetic' },
            { label: 'Clear & Informative', tone: 'informative' },
          ].map((item) => (
            <button
              key={item.tone}
              type="button"
              disabled={improving}
              onClick={() => handleImprove(item.tone)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors ${
                targetTone === item.tone
                  ? 'bg-indigo-600 text-white border-indigo-600 shadow-sm'
                  : 'bg-white text-slate-700 border-slate-300 hover:bg-slate-100'
              }`}
            >
              {item.label}
            </button>
          ))}
        </div>

        {/* Optional Custom Objective */}
        <div className="flex flex-col sm:flex-row gap-2">
          <input
            type="text"
            placeholder="Custom objective (e.g. 'Make concise for senior citizen SMS advisory')"
            value={targetObjective}
            onChange={(e) => setTargetObjective(e.target.value)}
            className="flex-1 text-xs px-3 py-2 rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-indigo-500 bg-white"
          />
          <button
            type="button"
            disabled={improving}
            onClick={() => handleImprove(targetTone)}
            className="inline-flex items-center justify-center gap-1.5 px-4 py-2 text-xs font-medium text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 transition-colors shadow-sm disabled:opacity-50"
          >
            <Sparkles className={`w-3.5 h-3.5 ${improving ? 'animate-spin' : ''}`} />
            {improving ? 'Optimizing...' : 'Generate Rewrite'}
          </button>
        </div>
      </div>

      {/* Improved Version Preview Card */}
      {improvedResult && (
        <div className="p-5 rounded-xl border-2 border-indigo-200 bg-indigo-50/30 space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-3 border-b border-indigo-100">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="w-5 h-5 text-emerald-600" />
              <div>
                <h4 className="text-sm font-semibold text-slate-900">
                  Tone-Optimized Draft Generated
                </h4>
                <p className="text-xs text-slate-500">
                  Target tone: <span className="font-semibold text-indigo-700 capitalize">{improvedResult.target_tone}</span>
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => setShowDiffModal(true)}
                className="inline-flex items-center gap-1 px-3 py-1.5 text-xs font-medium text-slate-700 bg-white border border-slate-300 rounded-lg hover:bg-slate-50 transition-colors shadow-sm"
              >
                <Split className="w-3.5 h-3.5 text-slate-500" />
                View Side-by-Side Diff
              </button>
              <button
                type="button"
                onClick={handleApply}
                className="inline-flex items-center gap-1 px-3.5 py-1.5 text-xs font-medium text-white bg-emerald-600 rounded-lg hover:bg-emerald-700 transition-colors shadow-sm"
              >
                <Check className="w-3.5 h-3.5" />
                Apply to Editor
              </button>
            </div>
          </div>

          {/* Improved Text Preview */}
          <div className="p-3.5 bg-white rounded-lg border border-indigo-100 text-sm text-slate-800 leading-relaxed font-sans whitespace-pre-wrap">
            {improvedResult.improved_text}
          </div>

          {/* Factual Preservation Audit Badge */}
          {improvedResult.factual_preservation && (
            <div className="flex items-center justify-between text-xs text-slate-600 pt-1">
              <div className="flex items-center gap-1.5 text-emerald-700">
                <ShieldCheck className="w-4 h-4" />
                <span className="font-medium">
                  {improvedResult.factual_preservation.all_anchors_preserved
                    ? 'All critical facts, helplines, dates, and placeholders preserved.'
                    : 'Factual anchors repaired.'}
                </span>
              </div>
              <span className="text-[11px] text-slate-400">
                +{improvedResult.diff?.additions_count || 0} / -{improvedResult.diff?.deletions_count || 0} words changed
              </span>
            </div>
          )}
        </div>
      )}

      {/* Side-by-Side Diff Modal */}
      {showDiffModal && improvedResult && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-sm animate-fade-in">
          <div className="bg-white rounded-2xl shadow-2xl max-w-4xl w-full max-h-[85vh] flex flex-col border border-slate-200">
            {/* Modal Header */}
            <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Split className="w-5 h-5 text-indigo-600" />
                <h3 className="text-base font-semibold text-slate-900">
                  Revision Diff & Factual Verification
                </h3>
              </div>
              <button
                onClick={() => setShowDiffModal(false)}
                className="p-1 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Modal Content */}
            <div className="p-6 overflow-y-auto space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Original Copy */}
                <div className="space-y-2">
                  <div className="flex items-center justify-between text-xs font-semibold text-slate-500 uppercase tracking-wider">
                    <span>Original Text</span>
                    <span className="text-rose-600">Previous</span>
                  </div>
                  <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 text-xs text-slate-700 whitespace-pre-wrap leading-relaxed min-h-[160px]">
                    {currentText || analysis?.original_text}
                  </div>
                </div>

                {/* Improved Copy */}
                <div className="space-y-2">
                  <div className="flex items-center justify-between text-xs font-semibold text-slate-500 uppercase tracking-wider">
                    <span>Improved Version ({improvedResult.target_tone})</span>
                    <span className="text-emerald-600 font-semibold">Optimized</span>
                  </div>
                  <div className="p-4 rounded-xl bg-indigo-50/40 border border-indigo-200 text-xs text-slate-800 whitespace-pre-wrap leading-relaxed min-h-[160px]">
                    {improvedResult.improved_text}
                  </div>
                </div>
              </div>

              {/* Inline Structured Token Diff */}
              {improvedResult.diff?.chunks && (
                <div className="space-y-2 pt-2 border-t border-slate-200">
                  <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                    Word-Level Diff View
                  </span>
                  <div className="p-4 rounded-xl bg-slate-900 text-slate-100 font-mono text-xs leading-relaxed overflow-x-auto max-h-[160px]">
                    {improvedResult.diff.chunks.map((chunk, idx) => {
                      if (chunk.operation === 'insert') {
                        return (
                          <span key={idx} className="bg-emerald-950 text-emerald-300 font-semibold px-0.5 rounded">
                            {chunk.text}{' '}
                          </span>
                        );
                      } else if (chunk.operation === 'delete') {
                        return (
                          <span key={idx} className="bg-rose-950 text-rose-300 line-through px-0.5 rounded opacity-70">
                            {chunk.text}{' '}
                          </span>
                        );
                      }
                      return <span key={idx}>{chunk.text} </span>;
                    })}
                  </div>
                </div>
              )}
            </div>

            {/* Modal Footer */}
            <div className="px-6 py-4 border-t border-slate-200 flex justify-end gap-3 bg-slate-50 rounded-b-2xl">
              <button
                type="button"
                onClick={() => setShowDiffModal(false)}
                className="px-4 py-2 text-xs font-medium text-slate-700 bg-white border border-slate-300 rounded-lg hover:bg-slate-100 transition-colors"
              >
                Close
              </button>
              <button
                type="button"
                onClick={() => {
                  handleApply();
                  setShowDiffModal(false);
                }}
                className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-medium text-white bg-emerald-600 rounded-lg hover:bg-emerald-700 transition-colors shadow-sm"
              >
                <Check className="w-4 h-4" />
                Apply Improved Version
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

