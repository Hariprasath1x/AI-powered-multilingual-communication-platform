import React, { useState } from 'react';
import { X, Sparkles, AlertCircle, Loader2, Info } from 'lucide-react';
import { generateContent } from '../../services/contentService';

const CATEGORIES = [
  'Healthcare',
  'Disaster Preparedness',
  'Education',
  'Civic Services',
  'Environment',
  'Public Announcement',
];

const TONES = [
  { value: 'informative', label: 'Informative (Clear & Factual)' },
  { value: 'formal', label: 'Formal (Official & Authoritative)' },
  { value: 'urgent', label: 'Urgent (Emergency Action Needed)' },
  { value: 'friendly', label: 'Friendly (Approachable & Encouraging)' },
  { value: 'empathetic', label: 'Empathetic (Caring & Supportive)' },
];

const CHANNELS = ['Email', 'SMS', 'WhatsApp', 'Voice'];

const LANGUAGES = [
  { code: 'en', name: 'English' },
  { code: 'hi', name: 'Hindi (हिन्दी)' },
  { code: 'ta', name: 'Tamil (தமிழ்)' },
  { code: 'te', name: 'Telugu (తెలుగు)' },
  { code: 'bn', name: 'Bengali (বাংলা)' },
  { code: 'mr', name: 'Marathi (मराठी)' },
];

export default function ContentGeneratorModal({ isOpen, onClose, onGenerated }) {
  const [formData, setFormData] = useState({
    topic: '',
    objective: '',
    audience_description: '',
    category: 'Healthcare',
    tone: 'informative',
    channel: 'Email',
    source_language: 'en',
    facts: '',
    constraints: '',
  });

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  if (!isOpen) return null;

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      const generated = await generateContent(formData);
      onGenerated(generated);
      onClose();
    } catch (err) {
      console.error('Content generation failed:', err);
      const detail = err.response?.data?.detail;
      setError(
        typeof detail === 'string'
          ? detail
          : 'Failed to generate content. Please verify your inputs and try again.'
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-sm overflow-y-auto">
      <div className="relative w-full max-w-2xl bg-white rounded-2xl shadow-2xl border border-slate-200 overflow-hidden my-8">
        
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 bg-gradient-to-r from-brand-50 to-indigo-50/50">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-xl bg-brand-600 text-white flex items-center justify-center shadow-sm">
              <Sparkles className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-lg font-bold text-slate-900">AI Content Generator</h3>
              <p className="text-xs text-slate-500">Craft channel-optimized public awareness messages from a structured brief</p>
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

        {/* Responsible AI Notice */}
        <div className="mx-6 mt-4 p-3 rounded-xl bg-amber-50 border border-amber-200 text-amber-900 text-xs flex items-start gap-2.5">
          <Info className="w-4 h-4 text-amber-600 flex-shrink-0 mt-0.5" />
          <p className="leading-relaxed">
            <strong>Factual Integrity Guard:</strong> MassCommAI generates drafts based strictly on your provided facts.
            Emergency helplines, official dates, and schemes are never invented. All generated copy requires human review before campaign use.
          </p>
        </div>

        {/* Error Alert */}
        {error && (
          <div className="mx-6 mt-4 p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-rose-600 flex-shrink-0" />
            <span className="flex-grow">{error}</span>
            <button onClick={() => setError(null)} className="text-rose-600 hover:text-rose-800 font-semibold text-xs">
              Dismiss
            </button>
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            
            {/* Topic */}
            <div className="md:col-span-2">
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Campaign Topic or Focus Area <span className="text-rose-500">*</span>
              </label>
              <input
                type="text"
                name="topic"
                required
                minLength={3}
                maxLength={200}
                placeholder="e.g. Cyclone Monsoon Warning & Relief Protocols"
                value={formData.topic}
                onChange={handleChange}
                disabled={loading}
                className="w-full px-3.5 py-2 text-sm rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-brand-500"
              />
            </div>

            {/* Objective */}
            <div className="md:col-span-2">
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Primary Communication Objective <span className="text-rose-500">*</span>
              </label>
              <textarea
                name="objective"
                required
                minLength={5}
                maxLength={500}
                rows={2}
                placeholder="e.g. Urge coastal residents to relocate to designated evacuation shelters before 6 PM"
                value={formData.objective}
                onChange={handleChange}
                disabled={loading}
                className="w-full px-3.5 py-2 text-sm rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-brand-500"
              />
            </div>

            {/* Category */}
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Category <span className="text-rose-500">*</span>
              </label>
              <select
                name="category"
                value={formData.category}
                onChange={handleChange}
                disabled={loading}
                className="w-full px-3.5 py-2 text-sm rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-brand-500 bg-white"
              >
                {CATEGORIES.map((cat) => (
                  <option key={cat} value={cat}>{cat}</option>
                ))}
              </select>
            </div>

            {/* Tone */}
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Desired Tone <span className="text-rose-500">*</span>
              </label>
              <select
                name="tone"
                value={formData.tone}
                onChange={handleChange}
                disabled={loading}
                className="w-full px-3.5 py-2 text-sm rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-brand-500 bg-white"
              >
                {TONES.map((t) => (
                  <option key={t.value} value={t.value}>{t.label}</option>
                ))}
              </select>
            </div>

            {/* Channel */}
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Distribution Channel <span className="text-rose-500">*</span>
              </label>
              <select
                name="channel"
                value={formData.channel}
                onChange={handleChange}
                disabled={loading}
                className="w-full px-3.5 py-2 text-sm rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-brand-500 bg-white"
              >
                {CHANNELS.map((ch) => (
                  <option key={ch} value={ch}>{ch}</option>
                ))}
              </select>
            </div>

            {/* Source Language */}
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Source Language <span className="text-rose-500">*</span>
              </label>
              <select
                name="source_language"
                value={formData.source_language}
                onChange={handleChange}
                disabled={loading}
                className="w-full px-3.5 py-2 text-sm rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-brand-500 bg-white"
              >
                {LANGUAGES.map((lang) => (
                  <option key={lang.code} value={lang.code}>{lang.name}</option>
                ))}
              </select>
            </div>

            {/* Audience Description */}
            <div className="md:col-span-2">
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Target Audience Context (Optional)
              </label>
              <input
                type="text"
                name="audience_description"
                maxLength={500}
                placeholder="e.g. Fishermen and coastal residents across coastal districts"
                value={formData.audience_description}
                onChange={handleChange}
                disabled={loading}
                className="w-full px-3.5 py-2 text-sm rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-brand-500"
              />
            </div>

            {/* Verified Facts & Helplines */}
            <div className="md:col-span-2">
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Verified Facts, Contacts & Official Directives (Optional)
              </label>
              <textarea
                name="facts"
                rows={2}
                maxLength={2000}
                placeholder="e.g. 24x7 Control Room: 1070. Free shelter at Municipal Stadium. Water packets available."
                value={formData.facts}
                onChange={handleChange}
                disabled={loading}
                className="w-full px-3.5 py-2 text-sm rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-brand-500 font-mono text-xs"
              />
              <span className="text-[11px] text-slate-400">
                The AI will explicitly incorporate these exact verified details.
              </span>
            </div>
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
              className="inline-flex items-center gap-2 px-5 py-2 text-sm font-semibold text-white bg-brand-600 hover:bg-brand-700 rounded-xl shadow-sm transition disabled:opacity-50"
            >
              {loading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Generating Draft...
                </>
              ) : (
                <>
                  <Sparkles className="w-4 h-4" />
                  Generate Draft
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

