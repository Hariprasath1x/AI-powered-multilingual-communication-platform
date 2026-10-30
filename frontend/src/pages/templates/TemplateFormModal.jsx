import React, { useState, useEffect, useRef } from 'react';
import {
  X,
  FileText,
  Tag,
  Globe,
  Layers,
  Sparkles,
  AlertCircle,
  CheckCircle2,
  HelpCircle
} from 'lucide-react';
import { createTemplate, updateTemplate } from '../../services/templateService';

const ALLOWED_PLACEHOLDERS = [
  { token: '{name}', label: 'Full Name', desc: 'Recipient name' },
  { token: '{email}', label: 'Email', desc: 'Email address' },
  { token: '{phone}', label: 'Phone', desc: 'Contact number' },
  { token: '{city}', label: 'City', desc: 'Residence city' },
  { token: '{state}', label: 'State', desc: 'State / Province' },
  { token: '{preferred_language}', label: 'Language', desc: 'Language code' },
  { token: '{occupation}', label: 'Occupation', desc: 'Profession / Sector' },
  { token: '{organization_department}', label: 'Department', desc: 'Ministry or Dept' },
];

const CATEGORIES = [
  'Healthcare',
  'Disaster Management',
  'Civic Education',
  'Public Governance',
  'Emergency Alert',
  'Community Outreach',
];

export default function TemplateFormModal({ isOpen, onClose, onSuccess, template = null }) {
  const isEditing = Boolean(template);
  const textareaRef = useRef(null);

  const [formData, setFormData] = useState({
    title: '',
    category: 'Healthcare',
    language: 'en',
    tags: '',
    body: '',
  });

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (template) {
      setFormData({
        title: template.title || '',
        category: template.category || 'Healthcare',
        language: template.language || 'en',
        tags: template.tags || '',
        body: template.body || '',
      });
    } else {
      setFormData({
        title: '',
        category: 'Healthcare',
        language: 'en',
        tags: '',
        body: '',
      });
    }
    setError('');
  }, [template, isOpen]);

  if (!isOpen) return null;

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
    if (error) setError('');
  };

  const insertPlaceholder = (token) => {
    const textarea = textareaRef.current;
    if (!textarea) {
      setFormData((prev) => ({ ...prev, body: prev.body + ' ' + token }));
      return;
    }

    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const currentBody = formData.body;
    const newBody = currentBody.substring(0, start) + token + currentBody.substring(end);

    setFormData((prev) => ({ ...prev, body: newBody }));

    // Reset cursor after inserted token
    setTimeout(() => {
      textarea.focus();
      textarea.setSelectionRange(start + token.length, start + token.length);
    }, 0);
  };

  const detectedPlaceholders = (formData.body.match(/\{[a-zA-Z0-9_]+\}/g) || []).filter(
    (item, idx, arr) => arr.indexOf(item) === idx
  );

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!formData.title.trim()) {
      setError('Template title is required.');
      return;
    }
    if (formData.body.trim().length < 5) {
      setError('Message body must be at least 5 characters long.');
      return;
    }

    setSubmitting(true);
    setError('');

    try {
      const payload = {
        title: formData.title.trim(),
        category: formData.category,
        language: formData.language.trim().toLowerCase(),
        tags: formData.tags.trim() || null,
        body: formData.body.trim(),
      };

      if (isEditing) {
        await updateTemplate(template.id, payload);
      } else {
        await createTemplate(payload);
      }

      onSuccess(isEditing ? 'Template updated successfully.' : 'Template created successfully.');
      onClose();
    } catch (err) {
      const detail = err.response?.data?.detail;
      if (Array.isArray(detail)) {
        setError(detail.map((d) => d.msg || `${d.loc?.join('.')}: ${d.type}`).join(', '));
      } else if (typeof detail === 'string') {
        setError(detail);
      } else {
        setError(err.message || 'Failed to save template.');
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-sm overflow-y-auto">
      <div className="relative w-full max-w-2xl bg-white rounded-2xl shadow-xl border border-slate-200 overflow-hidden my-8">
        
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100 bg-slate-50/50">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-brand-100 text-brand-600 flex items-center justify-center">
              <FileText className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-slate-900">
                {isEditing ? 'Edit Communication Template' : 'New Communication Template'}
              </h2>
              <p className="text-xs text-slate-500">
                Author reusable multi-channel announcements with dynamic citizen variables
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 text-slate-400 hover:text-slate-600 rounded-lg hover:bg-slate-100 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSubmit} className="p-6 space-y-5">
          {error && (
            <div className="p-3.5 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-xs flex items-start gap-2.5">
              <AlertCircle className="w-4 h-4 text-rose-500 flex-shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          <div className="space-y-4">
            {/* Title */}
            <div>
              <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                Template Headline Title *
              </label>
              <input
                type="text"
                name="title"
                value={formData.title}
                onChange={handleChange}
                placeholder="e.g. Dengue Prevention & Monsoon Advisory"
                className="w-full px-3.5 py-2.5 bg-white border border-slate-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-brand-500 transition"
                required
              />
            </div>

            {/* Category & Language Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                  Thematic Category *
                </label>
                <div className="relative">
                  <select
                    name="category"
                    value={formData.category}
                    onChange={handleChange}
                    className="w-full px-3.5 py-2.5 bg-white border border-slate-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-brand-500 transition appearance-none"
                  >
                    {CATEGORIES.map((cat) => (
                      <option key={cat} value={cat}>
                        {cat}
                      </option>
                    ))}
                  </select>
                  <Layers className="w-4 h-4 text-slate-400 absolute right-3.5 top-3 pointer-events-none" />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                  Language Code *
                </label>
                <div className="relative">
                  <input
                    type="text"
                    name="language"
                    value={formData.language}
                    onChange={handleChange}
                    placeholder="en, hi, ta, te, mr, bn"
                    className="w-full px-3.5 py-2.5 bg-white border border-slate-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-brand-500 transition"
                    required
                  />
                  <Globe className="w-4 h-4 text-slate-400 absolute right-3.5 top-3 pointer-events-none" />
                </div>
              </div>
            </div>

            {/* Keyword Tags */}
            <div>
              <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                Keyword Tags (Optional)
              </label>
              <div className="relative">
                <input
                  type="text"
                  name="tags"
                  value={formData.tags}
                  onChange={handleChange}
                  placeholder="e.g. monsoon, health, advisory, emergency"
                  className="w-full px-3.5 py-2.5 bg-white border border-slate-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-brand-500 transition"
                />
                <Tag className="w-4 h-4 text-slate-400 absolute right-3.5 top-3 pointer-events-none" />
              </div>
            </div>

            {/* Placeholder Chip Insertion Panel */}
            <div className="bg-slate-50 p-3.5 rounded-xl border border-slate-200 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-slate-700 flex items-center gap-1.5">
                  <Sparkles className="w-3.5 h-3.5 text-brand-600" />
                  Insert Dynamic Variables:
                </span>
                <span className="text-[11px] text-slate-400">Click to insert at cursor</span>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {ALLOWED_PLACEHOLDERS.map((ph) => (
                  <button
                    key={ph.token}
                    type="button"
                    onClick={() => insertPlaceholder(ph.token)}
                    title={ph.desc}
                    className="px-2.5 py-1 text-xs font-mono font-medium rounded-lg bg-white border border-slate-200 text-slate-700 hover:border-brand-400 hover:bg-brand-50 hover:text-brand-700 transition shadow-2xs"
                  >
                    {ph.token}
                  </button>
                ))}
              </div>
            </div>

            {/* Message Body */}
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider">
                  Template Content Body *
                </label>
                <span className="text-xs text-slate-400">
                  {formData.body.length} characters
                </span>
              </div>
              <textarea
                ref={textareaRef}
                name="body"
                rows={5}
                value={formData.body}
                onChange={handleChange}
                placeholder="Dear {name}, this is an official awareness broadcast for residents in {city}. Please note..."
                className="w-full px-3.5 py-2.5 bg-white border border-slate-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-brand-500 font-normal leading-relaxed transition"
                required
              />
            </div>

            {/* Detected placeholders summary */}
            {detectedPlaceholders.length > 0 && (
              <div className="flex items-center gap-2 text-xs text-slate-600">
                <span className="font-semibold text-slate-700">Active variables:</span>
                <div className="flex flex-wrap gap-1">
                  {detectedPlaceholders.map((ph) => (
                    <span
                      key={ph}
                      className="px-2 py-0.5 rounded-md bg-emerald-50 text-emerald-700 border border-emerald-200 font-mono text-[11px]"
                    >
                      {ph}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Footer Actions */}
          <div className="pt-4 border-t border-slate-100 flex items-center justify-end gap-3">
            <button
              type="button"
              onClick={onClose}
              disabled={submitting}
              className="px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100 rounded-xl transition"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="inline-flex items-center gap-1.5 px-5 py-2 text-sm font-semibold text-white bg-brand-600 hover:bg-brand-700 rounded-xl shadow-sm hover:shadow-brand-500/25 transition disabled:opacity-50"
            >
              {submitting ? 'Saving...' : isEditing ? 'Update Template' : 'Create Template'}
            </button>
          </div>
        </form>

      </div>
    </div>
  );
}

