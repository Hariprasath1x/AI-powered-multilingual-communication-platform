import React, { useState, useEffect } from 'react';
import { X, History, Clock, FileCheck2, Loader2, AlertCircle } from 'lucide-react';
import { getQualityAssessmentHistory } from '../../services/contentQualityService';

export default function ContentAssessmentHistoryModal({ isOpen, onClose, assetId }) {
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (isOpen && assetId) {
      setLoading(true);
      setError(null);
      getQualityAssessmentHistory(assetId)
        .then((data) => setHistory(data || []))
        .catch((err) => {
          console.error('Failed to load quality history:', err);
          setError('Failed to load assessment history.');
        })
        .finally(() => setLoading(false));
    }
  }, [isOpen, assetId]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-sm overflow-y-auto">
      <div className="relative w-full max-w-xl bg-white rounded-2xl shadow-2xl border border-slate-200 overflow-hidden my-8">
        
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 bg-slate-50">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-indigo-600 text-white flex items-center justify-center shadow-sm">
              <History className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-base font-bold text-slate-900">Quality Assessment Audit Trail</h3>
              <p className="text-xs text-slate-500">Historical evaluations performed on Asset #{assetId}</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 max-h-[500px] overflow-y-auto space-y-4">
          {loading ? (
            <div className="py-8 text-center text-xs text-slate-500 flex items-center justify-center gap-2">
              <Loader2 className="w-4 h-4 animate-spin text-indigo-600" />
              Loading audit trail...
            </div>
          ) : error ? (
            <div className="p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-center gap-2">
              <AlertCircle className="w-4 h-4" />
              <span>{error}</span>
            </div>
          ) : history.length === 0 ? (
            <div className="py-8 text-center text-xs text-slate-500">
              No historical assessments recorded for this asset yet.
            </div>
          ) : (
            history.map((item, idx) => (
              <div
                key={item.id}
                className="p-4 rounded-xl border border-slate-200 bg-slate-50/50 space-y-2 text-xs"
              >
                <div className="flex items-center justify-between">
                  <span className="font-bold text-slate-800 flex items-center gap-1.5">
                    <FileCheck2 className="w-3.5 h-3.5 text-indigo-600" />
                    Assessment #{item.id} {idx === 0 && <span className="text-[10px] bg-emerald-100 text-emerald-800 px-1.5 py-0.2 rounded font-semibold">(Latest)</span>}
                  </span>
                  <span className="text-slate-400 text-[11px]">
                    {new Date(item.created_at).toLocaleString()}
                  </span>
                </div>

                <div className="flex items-center justify-between pt-1">
                  <div className="space-x-2 text-[11px]">
                    <span className="font-semibold text-slate-700">Score:</span>
                    <strong className={item.overall_score >= 80 ? 'text-emerald-700' : 'text-amber-700'}>
                      {Math.round(item.overall_score)}/100
                    </strong>
                    <span>•</span>
                    <span className="capitalize text-slate-600">{item.evaluator_type} Evaluator</span>
                  </div>

                  <div className="flex items-center gap-1.5 text-[10px] font-semibold">
                    <span className="text-rose-600">{item.critical_issues_count} Critical</span>
                    <span>•</span>
                    <span className="text-orange-600">{item.high_issues_count} High</span>
                    <span>•</span>
                    <span className="text-slate-600">{item.findings?.length || 0} Total</span>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>

        <div className="px-6 py-3 border-t border-slate-200 bg-slate-50 text-right">
          <button
            onClick={onClose}
            className="px-4 py-1.5 text-xs font-semibold text-slate-700 bg-white border border-slate-300 rounded-lg hover:bg-slate-50"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}

