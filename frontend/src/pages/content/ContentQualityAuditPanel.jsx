import React, { useState } from 'react';
import {
  ShieldAlert,
  CheckCircle2,
  AlertTriangle,
  AlertCircle,
  Info,
  Sparkles,
  RotateCcw,
  Check,
  X,
  FileCheck2,
  Sliders,
  History,
  Clock,
  Layers,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';
import {
  updateFindingDecision,
} from '../../services/contentQualityService';

const SEVERITY_COLORS = {
  critical: 'bg-rose-100 text-rose-800 border-rose-300',
  high: 'bg-orange-100 text-orange-800 border-orange-300',
  medium: 'bg-amber-100 text-amber-800 border-amber-300',
  low: 'bg-sky-100 text-sky-800 border-sky-300',
  informational: 'bg-slate-100 text-slate-800 border-slate-300',
};

const CATEGORY_LABELS = {
  grammar: 'Language & Grammar',
  readability: 'Readability',
  tone: 'Tone & Sentiment',
  translation: 'Translation Fidelity',
  factual: 'Factual Consistency',
  channel: 'Channel Compliance',
  safety_sensitive: 'Sensitive & Safety',
  placeholder: 'Placeholders',
  completeness: 'Completeness',
};

export default function ContentQualityAuditPanel({
  assessment,
  asset,
  onRunAudit,
  evaluating,
  onFindingUpdated,
  onViewHistory,
}) {
  const [severityFilter, setSeverityFilter] = useState('all');
  const [factsInput, setFactsInput] = useState('');
  const [showFactsInput, setShowFactsInput] = useState(false);
  const [decisionNotes, setDecisionNotes] = useState({});
  const [updatingFindingId, setUpdatingFindingId] = useState(null);
  const [activeNoteFindingId, setActiveNoteFindingId] = useState(null);

  const findings = assessment?.findings || [];
  const filteredFindings = findings.filter((f) => {
    if (severityFilter === 'all') return true;
    return f.severity === severityFilter;
  });

  const handleDecision = async (findingId, decision) => {
    setUpdatingFindingId(findingId);
    try {
      const note = decisionNotes[findingId] || undefined;
      const updated = await updateFindingDecision(asset.id, findingId, {
        reviewer_decision: decision,
        decision_notes: note,
      });
      if (onFindingUpdated) {
        onFindingUpdated(updated);
      }
      setActiveNoteFindingId(null);
    } catch (err) {
      console.error('Failed to update finding decision:', err);
    } finally {
      setUpdatingFindingId(null);
    }
  };

  const getScoreColor = (score, criticalCount) => {
    if (criticalCount > 0 || score < 50) return 'text-rose-600';
    if (score < 75) return 'text-amber-600';
    return 'text-emerald-600';
  };

  const getScoreBg = (score, criticalCount) => {
    if (criticalCount > 0 || score < 50) return 'bg-rose-50 border-rose-200';
    if (score < 75) return 'bg-amber-50 border-amber-200';
    return 'bg-emerald-50 border-emerald-200';
  };

  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-2xs p-6 space-y-6">
      
      {/* Panel Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 pb-4 border-b border-slate-200">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-800 flex items-center gap-1.5 font-mono">
              <FileCheck2 className="w-4 h-4 text-blue-600" />
              Content Quality, Compliance & Editorial Intelligence
            </span>
            {assessment?.is_outdated && (
              <span className="text-[11px] font-semibold px-2 py-0.5 rounded-full bg-amber-50 text-amber-900 border border-amber-300 flex items-center gap-1">
                <Clock className="w-3 h-3 text-amber-600" />
                Assessment Outdated
              </span>
            )}
          </div>
          <p className="text-xs text-slate-500 mt-1">
            Evaluates grammar, readability, tone sentiment, translation consistency, and channel constraints before human approval.
          </p>
        </div>

        <div className="flex items-center gap-2">
          {onViewHistory && (
            <button
              onClick={onViewHistory}
              className="inline-flex items-center gap-1.5 text-xs font-semibold px-3 py-1.5 rounded-lg border border-slate-200 text-slate-700 hover:bg-slate-50 transition"
              title="View past evaluations"
            >
              <History className="w-3.5 h-3.5 text-slate-500" />
              History
            </button>
          )}

          <button
            onClick={() => onRunAudit(factsInput.trim() || undefined)}
            disabled={evaluating}
            className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-semibold text-white bg-blue-600 hover:bg-blue-700 rounded-lg shadow-2xs transition disabled:opacity-50"
          >
            <Sparkles className="w-3.5 h-3.5" />
            {evaluating ? 'Auditing...' : assessment ? 'Re-Run Audit' : 'Run Quality Audit'}
          </button>
        </div>
      </div>

      {/* Optional Reference Facts Toggle */}
      <div className="space-y-2">
        <button
          type="button"
          onClick={() => setShowFactsInput(!showFactsInput)}
          className="text-xs font-semibold text-slate-700 hover:text-blue-600 flex items-center gap-1 transition"
        >
          {showFactsInput ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
          {showFactsInput ? 'Hide Reference Facts Option' : 'Verify Against Explicit Facts & Helplines (Optional)'}
        </button>

        {showFactsInput && (
          <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg space-y-2 animate-fadeIn">
            <label className="block text-[11px] font-semibold text-slate-700">
              Reference Facts, Helplines & Departmental Directives
            </label>
            <textarea
              rows={2}
              maxLength={2000}
              placeholder="e.g. 24x7 Helpline: 1070. Evacuation shelter at Government College. Water packets available."
              value={factsInput}
              onChange={(e) => setFactsInput(e.target.value)}
              className="w-full px-3 py-1.5 text-xs rounded-lg border border-slate-300 text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 font-mono"
            />
            <p className="text-[10px] text-slate-500">
              The engine checks that key numbers (e.g. 1070, 104) and dates are preserved and flags unsupported claims.
            </p>
          </div>
        )}
      </div>

      {assessment ? (
        <div className="space-y-6">
          
          {/* Top Score & Metrics Card */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-6 gap-3">
            
            {/* Overall Score */}
            <div className={`sm:col-span-2 p-4 rounded-xl border flex items-center gap-4 ${getScoreBg(assessment.overall_score, assessment.critical_issues_count)}`}>
              <div className="flex flex-col items-center justify-center w-16 h-16 rounded-full bg-white shadow-sm border border-slate-100 flex-shrink-0">
                <span className={`text-2xl font-black ${getScoreColor(assessment.overall_score, assessment.critical_issues_count)}`}>
                  {Math.round(assessment.overall_score)}
                </span>
                <span className="text-[9px] text-slate-400 -mt-1 font-bold">/ 100</span>
              </div>
              <div className="space-y-1">
                <span className="text-xs font-bold text-slate-800">Overall Quality Index</span>
                <p className="text-[11px] text-slate-600 leading-tight">
                  {assessment.critical_issues_count > 0 ? (
                    <strong className="text-rose-600">Critical safety issues detected. Score capped at 49.0.</strong>
                  ) : assessment.overall_score >= 80 ? (
                    <span className="text-emerald-700">High editorial quality. Ready for reviewer sign-off.</span>
                  ) : (
                    <span className="text-amber-700">Requires editorial refinement before approval.</span>
                  )}
                </p>
              </div>
            </div>

            {/* Finding Severity Counts */}
            <div className="p-3 rounded-xl bg-slate-50 border border-slate-200 text-center space-y-1">
              <span className="text-[10px] uppercase font-bold text-slate-500">Critical</span>
              <div className="text-xl font-bold text-rose-600">{assessment.critical_issues_count}</div>
              <span className="text-[9px] text-slate-400">Blocks Approval</span>
            </div>

            <div className="p-3 rounded-xl bg-slate-50 border border-slate-200 text-center space-y-1">
              <span className="text-[10px] uppercase font-bold text-slate-500">High</span>
              <div className="text-xl font-bold text-orange-600">{assessment.high_issues_count}</div>
              <span className="text-[9px] text-slate-400">Major Advisory</span>
            </div>

            <div className="p-3 rounded-xl bg-slate-50 border border-slate-200 text-center space-y-1">
              <span className="text-[10px] uppercase font-bold text-slate-500">Medium</span>
              <div className="text-xl font-bold text-amber-600">{assessment.medium_issues_count}</div>
              <span className="text-[9px] text-slate-400">Tone/Clarity</span>
            </div>

            <div className="p-3 rounded-xl bg-slate-50 border border-slate-200 text-center space-y-1">
              <span className="text-[10px] uppercase font-bold text-slate-500">Low & Info</span>
              <div className="text-xl font-bold text-slate-700">{assessment.low_issues_count + assessment.info_issues_count}</div>
              <span className="text-[9px] text-slate-400">Minor Polish</span>
            </div>
          </div>

          {/* Dimension Breakdown Cards */}
          <div className="space-y-2">
            <span className="text-xs font-bold text-slate-700 uppercase tracking-wider flex items-center gap-1.5">
              <Sliders className="w-3.5 h-3.5 text-slate-500" />
              Dimension-Level Scores
            </span>

            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2.5">
              {Object.entries(assessment.dimension_scores || {}).map(([dim, score]) => {
                if (score === null || score === undefined) return null;
                const label = CATEGORY_LABELS[dim] || dim.replace('_', ' ').toUpperCase();
                return (
                  <div key={dim} className="p-2.5 rounded-xl border border-slate-200 bg-slate-50/70 space-y-1.5">
                    <div className="flex items-center justify-between text-[11px]">
                      <span className="font-semibold text-slate-700 truncate">{label}</span>
                      <span className="font-bold text-slate-900">{Math.round(score)}%</span>
                    </div>
                    <div className="w-full bg-slate-200 rounded-full h-1.5 overflow-hidden">
                      <div
                        className={`h-1.5 rounded-full ${score >= 80 ? 'bg-emerald-500' : score >= 60 ? 'bg-amber-500' : 'bg-rose-500'}`}
                        style={{ width: `${Math.max(5, score)}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Findings Filter & List */}
          <div className="space-y-3 pt-2">
            <div className="flex items-center justify-between flex-wrap gap-2">
              <span className="text-xs font-bold text-slate-700 uppercase tracking-wider flex items-center gap-1.5">
                <AlertCircle className="w-3.5 h-3.5 text-slate-500" />
                Editorial Findings ({findings.length})
              </span>

              {/* Severity Filter Pills */}
              <div className="flex items-center gap-1 bg-slate-100 p-0.5 rounded-lg text-xs">
                {['all', 'critical', 'high', 'medium', 'low'].map((sev) => (
                  <button
                    key={sev}
                    onClick={() => setSeverityFilter(sev)}
                    className={`px-2 py-0.5 rounded-md font-semibold capitalize transition ${
                      severityFilter === sev ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-600 hover:text-slate-900'
                    }`}
                  >
                    {sev}
                  </button>
                ))}
              </div>
            </div>

            {filteredFindings.length === 0 ? (
              <div className="p-6 text-center text-xs text-slate-500 bg-slate-50 rounded-xl border border-slate-200">
                <CheckCircle2 className="w-6 h-6 text-emerald-500 mx-auto mb-1.5" />
                No findings match the selected filter.
              </div>
            ) : (
              <div className="space-y-3">
                {filteredFindings.map((finding) => {
                  const isPending = finding.reviewer_decision === 'pending';
                  const isUpdating = updatingFindingId === finding.id;
                  const isNoteOpen = activeNoteFindingId === finding.id;

                  return (
                    <div
                      key={finding.id}
                      className={`p-4 rounded-xl border transition space-y-2.5 ${
                        finding.severity === 'critical'
                          ? 'border-rose-200 bg-rose-50/30'
                          : 'border-slate-200 bg-white hover:bg-slate-50/50'
                      }`}
                    >
                      {/* Finding Meta Line */}
                      <div className="flex items-center justify-between flex-wrap gap-2">
                        <div className="flex items-center gap-2">
                          <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full border uppercase tracking-wider ${SEVERITY_COLORS[finding.severity] || SEVERITY_COLORS.medium}`}>
                            {finding.severity}
                          </span>
                          <span className="text-[11px] font-bold text-slate-800">
                            {CATEGORY_LABELS[finding.category] || finding.category}
                          </span>
                          <span className="text-[10px] text-slate-400">
                            {finding.evaluation_source === 'deterministic' ? (
                              <span className="text-slate-500 font-mono">[{finding.rule_id || 'RULE'}]</span>
                            ) : (
                              <span className="text-indigo-600 font-medium">AI Evaluator ({Math.round((finding.confidence || 0.85) * 100)}%)</span>
                            )}
                          </span>
                        </div>

                        {/* Reviewer Decision Status */}
                        <div className="flex items-center gap-1.5 text-xs">
                          {finding.reviewer_decision === 'pending' ? (
                            <span className="text-[11px] font-semibold text-amber-700 bg-amber-100 px-2 py-0.5 rounded-full">
                              Decision Pending
                            </span>
                          ) : (
                            <span className={`text-[11px] font-semibold px-2 py-0.5 rounded-full capitalize ${
                              finding.reviewer_decision === 'accepted'
                                ? 'bg-sky-100 text-sky-800'
                                : finding.reviewer_decision === 'corrected'
                                ? 'bg-emerald-100 text-emerald-800'
                                : 'bg-slate-100 text-slate-700'
                            }`}>
                              ✓ {finding.reviewer_decision}
                            </span>
                          )}
                        </div>
                      </div>

                      {/* Title & Explanation */}
                      <div>
                        <h4 className="text-xs font-bold text-slate-900">{finding.title}</h4>
                        <p className="text-xs text-slate-600 leading-relaxed mt-0.5">{finding.explanation}</p>
                      </div>

                      {/* Affected Text Box */}
                      {finding.affected_text && (
                        <div className="p-2 rounded-lg bg-rose-50/80 border border-rose-200 text-[11px] text-rose-900 font-mono">
                          <span className="font-semibold text-rose-700">Flagged Text:</span> "{finding.affected_text}"
                        </div>
                      )}

                      {/* Suggested Correction Box */}
                      {finding.suggested_correction && (
                        <div className="p-2.5 rounded-lg bg-emerald-50 border border-emerald-200 text-[11px] text-emerald-900 space-y-1">
                          <span className="font-semibold text-emerald-800 flex items-center gap-1">
                            💡 Suggested Improvement:
                          </span>
                          <p className="leading-relaxed">{finding.suggested_correction}</p>
                        </div>
                      )}

                      {/* Reviewer Resolution Actions */}
                      <div className="pt-2 border-t border-slate-100 flex items-center justify-between flex-wrap gap-2 text-xs">
                        <div className="flex items-center gap-2">
                          <span className="text-[11px] text-slate-500">Reviewer Action:</span>
                          <button
                            onClick={() => handleDecision(finding.id, 'accepted')}
                            disabled={isUpdating}
                            className={`px-2.5 py-1 rounded-lg text-xs font-semibold transition ${
                              finding.reviewer_decision === 'accepted'
                                ? 'bg-sky-600 text-white'
                                : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                            }`}
                          >
                            Accept
                          </button>
                          <button
                            onClick={() => handleDecision(finding.id, 'corrected')}
                            disabled={isUpdating}
                            className={`px-2.5 py-1 rounded-lg text-xs font-semibold transition ${
                              finding.reviewer_decision === 'corrected'
                                ? 'bg-emerald-600 text-white'
                                : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                            }`}
                          >
                            Mark Corrected
                          </button>
                          <button
                            onClick={() => handleDecision(finding.id, 'rejected')}
                            disabled={isUpdating}
                            className={`px-2.5 py-1 rounded-lg text-xs font-semibold transition ${
                              finding.reviewer_decision === 'rejected'
                                ? 'bg-slate-700 text-white'
                                : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                            }`}
                          >
                            Reject
                          </button>
                        </div>

                        <button
                          type="button"
                          onClick={() => setActiveNoteFindingId(isNoteOpen ? null : finding.id)}
                          className="text-[11px] text-indigo-600 hover:text-indigo-800 font-medium"
                        >
                          {isNoteOpen ? 'Hide Notes' : '+ Add Decision Notes'}
                        </button>
                      </div>

                      {/* Expandable Decision Notes Input */}
                      {isNoteOpen && (
                        <div className="pt-2 animate-fadeIn">
                          <input
                            type="text"
                            placeholder="Add editorial rationale or verification reference..."
                            value={decisionNotes[finding.id] || finding.decision_notes || ''}
                            onChange={(e) => setDecisionNotes({ ...decisionNotes, [finding.id]: e.target.value })}
                            className="w-full px-3 py-1.5 text-xs rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                          />
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      ) : (
        /* Empty State: Not yet audited */
        <div className="p-8 text-center text-slate-500 bg-slate-50 rounded-xl border border-slate-200 space-y-3">
          <FileCheck2 className="w-10 h-10 text-slate-300 mx-auto" />
          <h4 className="text-sm font-bold text-slate-800">Quality Evaluation Not Performed</h4>
          <p className="text-xs text-slate-500 max-w-sm mx-auto">
            Audit this content asset for grammar, readability, tone sentiment, and channel compliance before editorial approval.
          </p>
          <button
            onClick={() => onRunAudit(factsInput.trim() || undefined)}
            disabled={evaluating}
            className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-700 rounded-xl shadow-sm transition"
          >
            <Sparkles className="w-3.5 h-3.5" />
            {evaluating ? 'Evaluating...' : 'Run Initial Audit'}
          </button>
        </div>
      )}
    </div>
  );
}

