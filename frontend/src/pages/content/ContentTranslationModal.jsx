import React, { useState } from 'react';
import { X, Languages, AlertCircle, Loader2, ShieldCheck, CheckSquare, Square, Layers } from 'lucide-react';
import { translateContent, translateContentBatch } from '../../services/contentService';

const INDIAN_LANGUAGES = [
  { code: 'hi', name: 'Hindi (हिन्दी)' },
  { code: 'kn', name: 'Kannada (ಕನ್ನಡ)' },
  { code: 'ta', name: 'Tamil (தமிழ்)' },
  { code: 'te', name: 'Telugu (తెలుగు)' },
  { code: 'mr', name: 'Marathi (मराठी)' },
  { code: 'bn', name: 'Bengali (বাংলা)' },
  { code: 'gu', name: 'Gujarati (ગુજરાતી)' },
  { code: 'ml', name: 'Malayalam (മലയാളം)' },
  { code: 'pa', name: 'Punjabi (ਪੰਜਾਬੀ)' },
  { code: 'ur', name: 'Urdu (اردو)' },
  { code: 'en', name: 'English' },
];

export default function ContentTranslationModal({ isOpen, onClose, asset, onTranslated }) {
  const [isBatchMode, setIsBatchMode] = useState(false);
  const [targetLanguage, setTargetLanguage] = useState('hi');
  const [selectedBatchLanguages, setSelectedBatchLanguages] = useState(['hi', 'ta']);
  const [notes, setNotes] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [batchResults, setBatchResults] = useState(null);

  if (!isOpen || !asset) return null;

  const currentLang = (asset.target_language || asset.source_language || 'en').toLowerCase();
  const availableLanguages = INDIAN_LANGUAGES.filter((l) => l.code !== currentLang);

  const toggleBatchLanguage = (code) => {
    setSelectedBatchLanguages((prev) =>
      prev.includes(code) ? prev.filter((c) => c !== code) : [...prev, code]
    );
  };

  const handleSelectAll = () => {
    if (selectedBatchLanguages.length === availableLanguages.length) {
      setSelectedBatchLanguages([]);
    } else {
      setSelectedBatchLanguages(availableLanguages.map((l) => l.code));
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setBatchResults(null);
    setLoading(true);

    try {
      if (isBatchMode) {
        if (selectedBatchLanguages.length === 0) {
          setError('Please select at least one target language for batch translation.');
          setLoading(false);
          return;
        }

        const batchRes = await translateContentBatch(asset.id, {
          target_languages: selectedBatchLanguages,
          notes: notes.trim() || undefined,
        });

        setBatchResults(batchRes);
        if (onTranslated) {
          onTranslated(batchRes);
        }

        if (batchRes.total_failed === 0) {
          setTimeout(() => {
            onClose();
          }, 800);
        }
      } else {
        const translated = await translateContent(asset.id, {
          target_language: targetLanguage,
          notes: notes.trim() || undefined,
        });
        if (onTranslated) {
          onTranslated(translated);
        }
        onClose();
      }
    } catch (err) {
      console.error('Translation failed:', err);
      const detail = err.response?.data?.detail;
      setError(
        typeof detail === 'string'
          ? detail
          : 'Translation failed. Please check the target language and retry.'
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-sm overflow-y-auto">
      <div className="relative w-full max-w-lg bg-white rounded-xl shadow-xl border border-slate-200 overflow-hidden my-8">
        
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 bg-slate-50">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-lg bg-blue-50 text-blue-600 border border-blue-100 flex items-center justify-center shadow-xs">
              <Languages className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-lg font-bold text-slate-900 tracking-tight">Multilingual Translation</h3>
              <p className="text-xs text-slate-500">Supports 10 Indian languages with occurrence-aware placeholder preservation</p>
            </div>
          </div>
          <button
            onClick={onClose}
            disabled={loading}
            className="p-1.5 rounded-lg text-slate-500 hover:text-slate-700 hover:bg-slate-100 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Mode Selector Tabs */}
        <div className="px-6 pt-3 flex border-b border-slate-200 bg-white gap-4 text-xs font-semibold">
          <button
            type="button"
            onClick={() => setIsBatchMode(false)}
            className={`pb-2.5 border-b-2 transition ${
              !isBatchMode
                ? 'border-blue-600 text-blue-600 font-bold'
                : 'border-transparent text-slate-500 hover:text-slate-700'
            }`}
          >
            Single Language
          </button>
          <button
            type="button"
            onClick={() => setIsBatchMode(true)}
            className={`pb-2.5 border-b-2 transition flex items-center gap-1.5 ${
              isBatchMode
                ? 'border-blue-600 text-blue-600 font-bold'
                : 'border-transparent text-slate-500 hover:text-slate-700'
            }`}
          >
            <Layers className="w-3.5 h-3.5" />
            Batch Multi-Language
          </button>
        </div>

        {/* Placeholder Preservation Safeguard Notice */}
        <div className="mx-6 mt-4 p-3 rounded-lg bg-emerald-50 border border-emerald-200 text-emerald-950 text-xs flex items-start gap-2.5">
          <ShieldCheck className="w-4 h-4 text-emerald-700 flex-shrink-0 mt-0.5" />
          <div className="space-y-1">
            <p className="font-semibold text-emerald-900">Placeholder & Factual Preservation Guard:</p>
            <p className="text-emerald-800 text-[11px] leading-relaxed">
              Placeholders like {asset.detected_placeholders?.length > 0 ? (
                asset.detected_placeholders.map((ph) => (
                  <code key={ph} className="bg-emerald-100 text-emerald-900 px-1 py-0.5 rounded text-[10px] mx-0.5 font-mono">
                    {ph}
                  </code>
                ))
              ) : (
                <span className="italic">no dynamic placeholders</span>
              )} are verified by occurrence-aware safety checks and preserved unaltered.
            </p>
          </div>
        </div>

        {/* Error Alert */}
        {error && (
          <div className="mx-6 mt-4 p-3 rounded-lg bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-rose-600 flex-shrink-0" />
            <span className="flex-grow">{error}</span>
          </div>
        )}

        {/* Batch Execution Results Notification */}
        {batchResults && (
          <div className="mx-6 mt-4 p-3 rounded-lg bg-blue-50 border border-blue-200 text-blue-900 text-xs space-y-1">
            <p className="font-bold">
              Batch Translation: {batchResults.total_succeeded} / {batchResults.total_requested} Succeeded
            </p>
            {batchResults.failures?.length > 0 && (
              <ul className="text-rose-700 list-disc list-inside text-[11px]">
                {batchResults.failures.map((f) => (
                  <li key={f.target_language}>
                    {f.target_language.toUpperCase()}: {f.error}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">
              Source Content Language
            </label>
            <div className="px-3.5 py-2 text-sm bg-slate-50 border border-slate-200 rounded-lg text-slate-800 font-medium">
              {INDIAN_LANGUAGES.find((l) => l.code === currentLang)?.name || currentLang}
            </div>
          </div>

          {!isBatchMode ? (
            <div>
              <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">
                Select Target Indian Language <span className="text-blue-600">*</span>
              </label>
              <select
                value={targetLanguage}
                onChange={(e) => setTargetLanguage(e.target.value)}
                disabled={loading}
                className="w-full px-3.5 py-2 text-sm rounded-lg border border-slate-300 text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 bg-white"
              >
                {availableLanguages.map((lang) => (
                  <option key={lang.code} value={lang.code}>
                    {lang.name}
                  </option>
                ))}
              </select>
            </div>
          ) : (
            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="text-xs font-semibold text-slate-700 uppercase tracking-wider">
                  Select Target Indian Languages ({selectedBatchLanguages.length} selected)
                </label>
                <button
                  type="button"
                  onClick={handleSelectAll}
                  className="text-xs text-blue-600 hover:text-blue-800 font-medium"
                >
                  {selectedBatchLanguages.length === availableLanguages.length
                    ? 'Deselect All'
                    : 'Select All'}
                </button>
              </div>

              <div className="grid grid-cols-2 gap-2 max-h-44 overflow-y-auto p-2 rounded-lg border border-slate-200 bg-slate-50/50">
                {availableLanguages.map((lang) => {
                  const isChecked = selectedBatchLanguages.includes(lang.code);
                  return (
                    <button
                      type="button"
                      key={lang.code}
                      onClick={() => toggleBatchLanguage(lang.code)}
                      disabled={loading}
                      className={`flex items-center gap-2 px-2.5 py-1.5 rounded-lg border text-left text-xs transition ${
                        isChecked
                          ? 'bg-blue-50 border-blue-300 text-blue-900 font-semibold'
                          : 'bg-white border-slate-200 text-slate-700 hover:bg-slate-50'
                      }`}
                    >
                      {isChecked ? (
                        <CheckSquare className="w-3.5 h-3.5 text-blue-600 flex-shrink-0" />
                      ) : (
                        <Square className="w-3.5 h-3.5 text-slate-400 flex-shrink-0" />
                      )}
                      <span className="truncate">{lang.name}</span>
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          <div>
            <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">
              Context or Regional Dialect Notes (Optional)
            </label>
            <textarea
              rows={2}
              maxLength={500}
              placeholder="e.g. Formal tone suitable for official public health broadcast"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              disabled={loading}
              className="w-full px-3.5 py-2 text-sm rounded-lg border border-slate-300 text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
            />
          </div>

          {/* Actions */}
          <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-200">
            <button
              type="button"
              onClick={onClose}
              disabled={loading}
              className="px-4 py-2 text-sm font-medium text-slate-700 hover:text-slate-900 hover:bg-slate-100 border border-slate-200 rounded-lg transition"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading || (isBatchMode && selectedBatchLanguages.length === 0)}
              className="inline-flex items-center gap-2 px-5 py-2 text-sm font-semibold text-white bg-blue-600 hover:bg-blue-700 rounded-lg shadow-sm transition disabled:opacity-50"
            >
              {loading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  {isBatchMode ? 'Batch Translating...' : 'Translating...'}
                </>
              ) : (
                <>
                  <Languages className="w-4 h-4" />
                  {isBatchMode
                    ? `Translate (${selectedBatchLanguages.length} Languages)`
                    : 'Translate Content'}
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

