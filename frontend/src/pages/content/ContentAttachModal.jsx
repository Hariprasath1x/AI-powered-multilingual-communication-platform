import React, { useState, useEffect } from 'react';
import { X, Link2, FileText, Megaphone, AlertCircle, Loader2, CheckCircle2 } from 'lucide-react';
import { attachToCampaignOrTemplate } from '../../services/contentService';
import { listCampaigns } from '../../services/campaignService';

export default function ContentAttachModal({ isOpen, onClose, asset, onAttached }) {
  const [campaigns, setCampaigns] = useState([]);
  const [selectedCampaignId, setSelectedCampaignId] = useState('');
  const [saveAsTemplate, setSaveAsTemplate] = useState(false);
  const [templateName, setTemplateName] = useState('');
  const [loading, setLoading] = useState(false);
  const [fetchingCampaigns, setFetchingCampaigns] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  useEffect(() => {
    if (isOpen) {
      setTemplateName(asset ? `Template: ${asset.title}` : '');
      setFetchingCampaigns(true);
      listCampaigns({ page: 1, page_size: 50 })
        .then((res) => {
          setCampaigns(res.items || []);
        })
        .catch((err) => {
          console.error('Failed to load campaigns:', err);
        })
        .finally(() => {
          setFetchingCampaigns(false);
        });
    }
  }, [isOpen, asset]);

  if (!isOpen || !asset) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    setLoading(true);

    try {
      const payload = {
        campaign_id: selectedCampaignId ? parseInt(selectedCampaignId, 10) : undefined,
        save_as_template: saveAsTemplate,
        template_name: saveAsTemplate ? templateName.trim() : undefined,
      };

      const res = await attachToCampaignOrTemplate(asset.id, payload);
      setSuccess('Content successfully linked!');
      if (onAttached) onAttached(res);
      setTimeout(() => {
        onClose();
      }, 1000);
    } catch (err) {
      console.error('Attach failed:', err);
      const detail = err.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Failed to attach content.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-sm overflow-y-auto">
      <div className="relative w-full max-w-lg bg-white rounded-2xl shadow-2xl border border-slate-200 overflow-hidden my-8">
        
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 bg-gradient-to-r from-emerald-50 to-teal-50">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-xl bg-emerald-600 text-white flex items-center justify-center shadow-sm">
              <Link2 className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-lg font-bold text-slate-900">Attach to Campaign or Library</h3>
              <p className="text-xs text-slate-500">Connect content with existing workflows</p>
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

        {/* Success Alert */}
        {success && (
          <div className="mx-6 mt-4 p-3 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0" />
            <span>{success}</span>
          </div>
        )}

        {/* Error Alert */}
        {error && (
          <div className="mx-6 mt-4 p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-rose-600 flex-shrink-0" />
            <span className="flex-grow">{error}</span>
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-6 space-y-5">
          {/* Campaign Selection */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1 flex items-center gap-1.5">
              <Megaphone className="w-3.5 h-3.5 text-slate-500" />
              Link to Existing Campaign (Optional)
            </label>
            {fetchingCampaigns ? (
              <div className="flex items-center gap-2 text-xs text-slate-500 py-2">
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                Loading campaigns...
              </div>
            ) : (
              <select
                value={selectedCampaignId}
                onChange={(e) => setSelectedCampaignId(e.target.value)}
                disabled={loading}
                className="w-full px-3.5 py-2 text-sm rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-emerald-500 bg-white"
              >
                <option value="">-- Do not link to a campaign --</option>
                {campaigns.map((camp) => (
                  <option key={camp.id} value={camp.id}>
                    #{camp.id} - {camp.name} ({camp.status})
                  </option>
                ))}
              </select>
            )}
            <p className="text-[11px] text-slate-400 mt-1">
              Updates campaign draft body while strictly preserving approval rules.
            </p>
          </div>

          {/* Save as Reusable Template Checkbox */}
          <div className="p-3.5 rounded-xl border border-slate-200 bg-slate-50 space-y-3">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={saveAsTemplate}
                onChange={(e) => setSaveAsTemplate(e.target.checked)}
                disabled={loading}
                className="w-4 h-4 text-emerald-600 rounded border-slate-300 focus:ring-emerald-500"
              />
              <span className="text-xs font-semibold text-slate-800 flex items-center gap-1.5">
                <FileText className="w-3.5 h-3.5 text-slate-600" />
                Save as Reusable Communication Template
              </span>
            </label>

            {saveAsTemplate && (
              <div className="pt-2 border-t border-slate-200">
                <label className="block text-[11px] font-semibold text-slate-600 mb-1">
                  Template Title
                </label>
                <input
                  type="text"
                  required={saveAsTemplate}
                  maxLength={150}
                  value={templateName}
                  onChange={(e) => setTemplateName(e.target.value)}
                  disabled={loading}
                  className="w-full px-3 py-1.5 text-xs rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-emerald-500"
                />
              </div>
            )}
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
              disabled={loading || (!selectedCampaignId && !saveAsTemplate)}
              className="inline-flex items-center gap-2 px-5 py-2 text-sm font-semibold text-white bg-emerald-600 hover:bg-emerald-700 rounded-xl shadow-sm transition disabled:opacity-50"
            >
              {loading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Saving...
                </>
              ) : (
                <>
                  <Link2 className="w-4 h-4" />
                  Confirm Attachment
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

