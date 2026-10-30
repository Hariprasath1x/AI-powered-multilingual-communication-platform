import React, { useState } from 'react';
import { X, Languages, AlertCircle, Loader2, ShieldCheck } from 'lucide-react';
import { translateContent } from '../../services/contentService';

const INDIAN_LANGUAGES = [
  { code: 'hi', name: 'Hindi (हिन्दी)' },
  { code: 'ta', name: 'Tamil (தமிழ்)' },
  { code: 'te', name: 'Telugu (తెలుగు)' },
  { code: 'bn', name: 'Bengali (বাংলা)' },
  { code: 'mr', name: 'Marathi (मराठी)' },
  { code: 'en', name: 'English' },
];

export default function ContentTranslationModal({ isOpen, onClose, asset, onTranslated }) {
  const [targetLanguage, setTargetLanguage] = useState('ta');
  const [notes, setNotes] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  if (!isOpen || !asset) return null;

  const currentLang = asset.target_language || asset.source_language;
  const availableLanguages = INDIAN_LANGUAGES.filter((l) => l.code !== currentLang);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      const translated = await translateContent(asset.id, {
        target_language: targetLanguage,
        notes: notes.trim() || undefined,
      });
      onTranslated(translated);
      onClose();
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
      <div className="relative w-full max-w-lg bg-white rounded-2xl shadow-2xl border border-slate-200 overflow-hidden my-8">
        
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 bg-gradient-to-r from-indigo-50 to-purple-50">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-xl bg-indigo-600 text-white flex items-center justify-center shadow-sm">
              <Languages className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-lg font-bold text-slate-900">Multilingual Translation</h3>
              <p className="text-xs text-slate-500">Translate while strictly preserving placeholders and factual accuracy</p>
            </div>
          </div>
          <button
            onClick={onClose}
            disabled={loading}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Placeholder Preservation Safeguard Notice */}
        <div className="mx-6 mt-4 p-3 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-900 text-xs flex items-start gap-2.5">
          <ShieldCheck className="w-4 h-4 text-emerald-600 flex-shrink-0 mt-0.5" />
          <div className="space-y-1">
            <p className="font-semibold">Placeholder & Factual Preservation Guard:</p>
            <p className="text-emerald-800 text-[11px] leading-relaxed">
              Placeholders like {asset.detected_placeholders?.length > 0 ? (
                asset.detected_placeholders.map((ph) => (
                  <code key={ph} className="bg-emerald-100 text-emerald-900 px-1 py-0.5 rounded text-[10px] mx-0.5">
                    {ph}
                  </code>
                ))
              ) : (
                <span className="italic">no dynamic placeholders</span>
              )} are verified by backend safety checks and preserved unaltered.
            </p>
          </div>
        </div>

        {/* Error Alert */}
        {error && (
          <div className="mx-6 mt-4 p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-rose-600 flex-shrink-0" />
            <span className="flex-grow">{error}</span>
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              Source Content Language
            </label>
            <div className="px-3.5 py-2 text-sm bg-slate-100 rounded-xl text-slate-600 font-medium">
              {INDIAN_LANGUAGES.find((l) => l.code === currentLang)?.name || currentLang}
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              Select Target Indian Language <span className="text-rose-500">*</span>
            </label>
            <select
              value={targetLanguage}
              onChange={(e) => setTargetLanguage(e.target.value)}
              disabled={loading}
              className="w-full px-3.5 py-2 text-sm rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-indigo-500 bg-white"
            >
              {availableLanguages.map((lang) => (
                <option key={lang.code} value={lang.code}>
                  {lang.name}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              Context or Regional Dialect Notes (Optional)
            </label>
            <textarea
              rows={2}
              maxLength={500}
              placeholder="e.g. Formal tone suitable for official public health broadcast"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              disabled={loading}
              className="w-full px-3.5 py-2 text-sm rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>

          {/* Actions */}
          <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-200">
            <button
              type="button"
              onClick={onClose}
              disabled={loading}
              className="px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-100 rounded-xl transition"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="inline-flex items-center gap-2 px-5 py-2 text-sm font-semibold text-white bg-indigo-600 hover:bg-indigo-700 rounded-xl shadow-sm transition disabled:opacity-50"
            >
              {loading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Translating...
                </>
              ) : (
                <>
                  <Languages className="w-4 h-4" />
                  Translate Content
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

