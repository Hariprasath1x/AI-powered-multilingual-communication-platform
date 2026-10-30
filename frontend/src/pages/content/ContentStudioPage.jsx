import React, { useState, useEffect } from 'react';
import {
  Sparkles,
  Languages,
  FileText,
  Megaphone,
  CheckCircle2,
  Clock,
  AlertCircle,
  Eye,
  Edit3,
  Trash2,
  Search,
  Filter,
  Plus,
  ArrowRight,
  ShieldAlert,
  Smartphone,
  Mail,
  MessageSquare,
  Volume2,
  Save,
  RotateCcw,
  Check,
  X,
  Link2,
} from 'lucide-react';
import {
  listContentAssets,
  getContentAsset,
  updateContentAsset,
  getContentVariants,
  updateReviewStatus,
  deleteContentAsset,
} from '../../services/contentService';
import ContentGeneratorModal from './ContentGeneratorModal';
import ContentTranslationModal from './ContentTranslationModal';
import ContentAttachModal from './ContentAttachModal';
import { useAuth } from '../../context/AuthContext';

const LANGUAGE_LABELS = {
  en: 'English',
  hi: 'Hindi (हिन्दी)',
  ta: 'Tamil (தமிழ்)',
  te: 'Telugu (తెలుగు)',
  bn: 'Bengali (বাংলা)',
  mr: 'Marathi (मराठी)',
};

export default function ContentStudioPage() {
  const { user } = useAuth();
  const [assets, setAssets] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [channelFilter, setChannelFilter] = useState('');
  const [reviewFilter, setReviewFilter] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [actionSuccess, setActionSuccess] = useState(null);

  // Active Selected Asset & Studio state
  const [selectedAsset, setSelectedAsset] = useState(null);
  const [variants, setVariants] = useState([]);
  const [activePreviewChannel, setActivePreviewChannel] = useState('Email');
  const [isEditing, setIsEditing] = useState(false);
  const [editForm, setEditForm] = useState({ title: '', body: '', call_to_action: '' });
  const [savingEdit, setSavingEdit] = useState(false);

  // Modals
  const [generatorOpen, setGeneratorOpen] = useState(false);
  const [translationOpen, setTranslationOpen] = useState(false);
  const [attachOpen, setAttachOpen] = useState(false);

  // Review Status action state
  const [reviewNotes, setReviewNotes] = useState('');
  const [reviewActionLoading, setReviewActionLoading] = useState(false);

  // Load content assets list
  const loadAssets = async (pageIndex = 1) => {
    setLoading(true);
    setError(null);
    try {
      const res = await listContentAssets({
        page: pageIndex,
        size: 10,
        search: search.trim() || undefined,
        channel: channelFilter || undefined,
        review_status: reviewFilter || undefined,
      });
      setAssets(res.items || []);
      setTotal(res.total || 0);
      setPage(res.page || 1);

      // Auto-select first asset if none selected
      if (!selectedAsset && res.items?.length > 0) {
        selectAsset(res.items[0]);
      }
    } catch (err) {
      console.error('Failed to load content assets:', err);
      setError('Unable to load content assets. Please check your connection.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAssets(1);
  }, [channelFilter, reviewFilter]);

  const handleSearchSubmit = (e) => {
    e.preventDefault();
    loadAssets(1);
  };

  // Select an asset to display in Studio workspace
  const selectAsset = async (asset) => {
    setSelectedAsset(asset);
    setIsEditing(false);
    setEditForm({
      title: asset.title || '',
      body: asset.body || '',
      call_to_action: asset.call_to_action || '',
    });
    setActivePreviewChannel(asset.channel || 'Email');

    // Fetch lineage variants
    try {
      const varList = await getContentVariants(asset.id);
      setVariants(varList || []);
    } catch (err) {
      console.error('Failed to fetch variants:', err);
      setVariants([]);
    }
  };

  // Refresh active asset details
  const refreshActiveAsset = async (assetId) => {
    try {
      const fresh = await getContentAsset(assetId);
      selectAsset(fresh);
      loadAssets(page);
    } catch (err) {
      console.error('Failed to refresh asset:', err);
    }
  };

  // Handle newly generated content
  const handleGenerated = (newAsset) => {
    setActionSuccess('Draft generated successfully!');
    loadAssets(1);
    selectAsset(newAsset);
    setTimeout(() => setActionSuccess(null), 3000);
  };

  // Handle newly translated content
  const handleTranslated = (newVariant) => {
    setActionSuccess('Translation generated successfully!');
    refreshActiveAsset(newVariant.id);
    setTimeout(() => setActionSuccess(null), 3000);
  };

  // Save manual/human edits
  const handleSaveEdits = async () => {
    if (!selectedAsset) return;
    setSavingEdit(true);
    setError(null);
    try {
      const updated = await updateContentAsset(selectedAsset.id, {
        title: editForm.title.trim(),
        body: editForm.body.trim(),
        call_to_action: editForm.call_to_action.trim() || null,
      });
      setIsEditing(false);
      setActionSuccess('Content updated. Marked as human-edited.');
      refreshActiveAsset(updated.id);
      setTimeout(() => setActionSuccess(null), 3000);
    } catch (err) {
      console.error('Failed to update content:', err);
      setError('Failed to save edits. Please ensure all required fields are filled.');
    } finally {
      setSavingEdit(false);
    }
  };

  // Review Status transition
  const handleReviewTransition = async (targetStatus) => {
    if (!selectedAsset) return;
    setReviewActionLoading(true);
    setError(null);
    try {
      const updated = await updateReviewStatus(selectedAsset.id, {
        review_status: targetStatus,
        review_notes: reviewNotes.trim() || undefined,
      });
      setReviewNotes('');
      setActionSuccess(`Review status transitioned to ${targetStatus}`);
      refreshActiveAsset(updated.id);
      setTimeout(() => setActionSuccess(null), 3000);
    } catch (err) {
      console.error('Review transition failed:', err);
      setError(err.response?.data?.detail || 'Review transition failed.');
    } finally {
      setReviewActionLoading(false);
    }
  };

  // Delete draft asset
  const handleDeleteAsset = async (assetId) => {
    if (!window.confirm('Are you sure you want to delete this content asset? This action cannot be undone.')) {
      return;
    }
    try {
      await deleteContentAsset(assetId);
      setActionSuccess('Asset deleted.');
      if (selectedAsset?.id === assetId) {
        setSelectedAsset(null);
      }
      loadAssets(page);
      setTimeout(() => setActionSuccess(null), 3000);
    } catch (err) {
      console.error('Delete failed:', err);
      setError(err.response?.data?.detail || 'Failed to delete content asset.');
    }
  };

  const getReviewBadge = (status) => {
    switch (status) {
      case 'Approved':
        return 'bg-emerald-100 text-emerald-800 border-emerald-200';
      case 'In Review':
        return 'bg-amber-100 text-amber-800 border-amber-200';
      case 'Rejected':
        return 'bg-rose-100 text-rose-800 border-rose-200';
      case 'Draft':
      default:
        return 'bg-slate-100 text-slate-800 border-slate-200';
    }
  };

  const getChannelIcon = (ch) => {
    switch (ch) {
      case 'SMS':
        return <Smartphone className="w-3.5 h-3.5 text-sky-600" />;
      case 'WhatsApp':
        return <MessageSquare className="w-3.5 h-3.5 text-emerald-600" />;
      case 'Voice':
        return <Volume2 className="w-3.5 h-3.5 text-indigo-600" />;
      case 'Email':
      default:
        return <Mail className="w-3.5 h-3.5 text-purple-600" />;
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      
      {/* Studio Header */}
      <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div>
          <div className="inline-flex items-center gap-2 text-xs font-semibold px-2.5 py-0.5 rounded-full bg-brand-50 text-brand-700 border border-brand-200 mb-1.5">
            <Sparkles className="w-3.5 h-3.5 text-brand-600" />
            AI Multilingual Studio Active
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">
            Content & Translation Studio
          </h1>
          <p className="text-sm text-slate-600">
            Generate, translate, review, and channel-optimize public awareness communications across 6 Indian languages.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => setGeneratorOpen(true)}
            className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl font-semibold text-white bg-brand-600 hover:bg-brand-700 transition shadow-sm text-sm"
          >
            <Sparkles className="w-4 h-4" />
            Generate with AI
          </button>
        </div>
      </div>

      {/* Mandatory Human Review Guard Notice */}
      <div className="bg-gradient-to-r from-amber-50 to-orange-50 border border-amber-200 rounded-2xl p-4 sm:p-5 flex items-start gap-3.5">
        <ShieldAlert className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
        <div className="space-y-1 text-xs text-amber-900 leading-relaxed">
          <p className="font-bold text-sm text-amber-950">Responsible AI & Human-in-the-Loop Governance</p>
          <p>
            All AI-generated copy and machine translations are initialized in <strong>Draft</strong> status.
            Official public service announcements, emergency alerts, and health directives require verified human review
            before approval or campaign association. Placeholders such as <code className="bg-amber-100 px-1 py-0.5 rounded font-mono text-[11px]">{'{name}'}</code> and <code className="bg-amber-100 px-1 py-0.5 rounded font-mono text-[11px]">{'{city}'}</code> are strictly preserved across language variants.
          </p>
        </div>
      </div>

      {/* Notifications */}
      {actionSuccess && (
        <div className="p-3.5 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs flex items-center gap-2 animate-fadeIn">
          <CheckCircle2 className="w-4 h-4 text-emerald-600" />
          <span>{actionSuccess}</span>
        </div>
      )}
      {error && (
        <div className="p-3.5 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-center gap-2">
          <AlertCircle className="w-4 h-4 text-rose-600" />
          <span className="flex-grow">{error}</span>
          <button onClick={() => setError(null)} className="text-rose-600 font-bold hover:underline">Dismiss</button>
        </div>
      )}

      {/* Main Workspace Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        
        {/* Left Column: Drafts & Lineage Library (4 cols) */}
        <div className="lg:col-span-5 bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden flex flex-col h-[750px]">
          
          {/* Library Header & Search */}
          <div className="p-4 border-b border-slate-200 space-y-3 bg-slate-50/50">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-slate-700 uppercase tracking-wider flex items-center gap-1.5">
                <FileText className="w-3.5 h-3.5 text-brand-600" /> Content Library ({total})
              </span>
              <button
                onClick={() => loadAssets(1)}
                className="text-xs text-brand-600 hover:text-brand-700 font-semibold"
              >
                Refresh
              </button>
            </div>

            <form onSubmit={handleSearchSubmit} className="relative">
              <input
                type="text"
                placeholder="Search topic or body..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full pl-9 pr-3 py-1.5 text-xs rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-brand-500"
              />
              <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-2.5" />
            </form>

            <div className="flex items-center gap-2">
              <select
                value={channelFilter}
                onChange={(e) => setChannelFilter(e.target.value)}
                className="text-xs px-2 py-1 rounded-lg border border-slate-300 bg-white flex-1"
              >
                <option value="">All Channels</option>
                <option value="Email">Email</option>
                <option value="SMS">SMS</option>
                <option value="WhatsApp">WhatsApp</option>
                <option value="Voice">Voice</option>
              </select>

              <select
                value={reviewFilter}
                onChange={(e) => setReviewFilter(e.target.value)}
                className="text-xs px-2 py-1 rounded-lg border border-slate-300 bg-white flex-1"
              >
                <option value="">All Review States</option>
                <option value="Draft">Draft</option>
                <option value="In Review">In Review</option>
                <option value="Approved">Approved</option>
                <option value="Rejected">Rejected</option>
              </select>
            </div>
          </div>

          {/* List of Assets */}
          <div className="flex-1 overflow-y-auto divide-y divide-slate-100">
            {loading ? (
              <div className="p-8 text-center text-xs text-slate-500">Loading library...</div>
            ) : assets.length === 0 ? (
              <div className="p-8 text-center text-xs text-slate-500 space-y-2">
                <FileText className="w-8 h-8 text-slate-300 mx-auto" />
                <p>No content drafts found matching filters.</p>
                <button
                  onClick={() => setGeneratorOpen(true)}
                  className="text-brand-600 font-semibold underline"
                >
                  Generate your first draft
                </button>
              </div>
            ) : (
              assets.map((asset) => {
                const isSelected = selectedAsset?.id === asset.id;
                const lang = asset.target_language || asset.source_language;
                return (
                  <div
                    key={asset.id}
                    onClick={() => selectAsset(asset)}
                    className={`p-3.5 cursor-pointer transition flex flex-col gap-1.5 ${
                      isSelected
                        ? 'bg-brand-50/70 border-l-4 border-l-brand-600'
                        : 'hover:bg-slate-50'
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-xs font-bold text-slate-900 truncate">
                        {asset.title}
                      </span>
                      <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border ${getReviewBadge(asset.review_status)}`}>
                        {asset.review_status}
                      </span>
                    </div>

                    <p className="text-[11px] text-slate-600 line-clamp-2 leading-relaxed">
                      {asset.body}
                    </p>

                    <div className="flex items-center justify-between text-[10px] text-slate-400 pt-1">
                      <div className="flex items-center gap-2">
                        <span className="flex items-center gap-1 font-medium text-slate-600">
                          {getChannelIcon(asset.channel)}
                          {asset.channel}
                        </span>
                        <span>•</span>
                        <span className="font-semibold text-indigo-700 bg-indigo-50 px-1.5 py-0.5 rounded">
                          {LANGUAGE_LABELS[lang] || lang}
                        </span>
                        {asset.operation_type === 'translation' && (
                          <span className="text-purple-700 bg-purple-50 px-1 py-0.5 rounded text-[9px] font-semibold">
                            Variant
                          </span>
                        )}
                      </div>
                      <span>#{asset.id}</span>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Right Column: Studio Workspace & Simulation (7 cols) */}
        <div className="lg:col-span-7 space-y-6">
          
          {selectedAsset ? (
            <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 space-y-6">
              
              {/* Asset Header & Lineage Variant Tabs */}
              <div className="space-y-3 pb-4 border-b border-slate-200">
                <div className="flex items-center justify-between flex-wrap gap-2">
                  <div className="flex items-center gap-2">
                    <span className={`text-xs font-bold px-2.5 py-0.5 rounded-full border ${getReviewBadge(selectedAsset.review_status)}`}>
                      {selectedAsset.review_status}
                    </span>
                    <span className="text-xs text-slate-400">ID #{selectedAsset.id}</span>
                    <span className="text-xs text-slate-400">•</span>
                    <span className="text-xs text-slate-600 font-medium">Category: {selectedAsset.category}</span>
                  </div>

                  {/* Actions: Translate, Attach, Delete */}
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => setTranslationOpen(true)}
                      className="inline-flex items-center gap-1 text-xs font-semibold px-2.5 py-1.5 rounded-lg bg-indigo-50 text-indigo-700 hover:bg-indigo-100 transition"
                      title="Translate to another Indian language"
                    >
                      <Languages className="w-3.5 h-3.5" />
                      Translate
                    </button>
                    <button
                      onClick={() => setAttachOpen(true)}
                      className="inline-flex items-center gap-1 text-xs font-semibold px-2.5 py-1.5 rounded-lg bg-emerald-50 text-emerald-700 hover:bg-emerald-100 transition"
                      title="Attach to Campaign or save as Template"
                    >
                      <Link2 className="w-3.5 h-3.5" />
                      Attach
                    </button>
                    <button
                      onClick={() => handleDeleteAsset(selectedAsset.id)}
                      className="p-1.5 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition"
                      title="Delete draft"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>

                {/* Lineage Variant Tabs */}
                {variants.length > 1 && (
                  <div className="space-y-1 pt-1">
                    <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
                      Language Lineage Variants:
                    </span>
                    <div className="flex items-center gap-2 overflow-x-auto pb-1">
                      {variants.map((v) => {
                        const vLang = v.target_language || v.source_language;
                        const isCurrent = v.id === selectedAsset.id;
                        return (
                          <button
                            key={v.id}
                            onClick={() => refreshActiveAsset(v.id)}
                            className={`px-3 py-1 text-xs rounded-xl font-semibold transition whitespace-nowrap flex items-center gap-1.5 ${
                              isCurrent
                                ? 'bg-indigo-600 text-white shadow-sm'
                                : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                            }`}
                          >
                            <Languages className="w-3 h-3" />
                            {LANGUAGE_LABELS[vLang] || vLang}
                            {v.parent_id === null && ' (Original)'}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                )}
              </div>

              {/* Editable Draft View */}
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="text-base font-bold text-slate-900">
                    {isEditing ? 'Editing Draft Content' : selectedAsset.title}
                  </h3>
                  {!isEditing ? (
                    <button
                      onClick={() => setIsEditing(true)}
                      className="inline-flex items-center gap-1 text-xs font-semibold text-brand-600 hover:text-brand-700 p-1"
                    >
                      <Edit3 className="w-3.5 h-3.5" />
                      Edit Copy
                    </button>
                  ) : (
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => setIsEditing(false)}
                        className="text-xs text-slate-500 hover:text-slate-700 px-2 py-1"
                      >
                        Cancel
                      </button>
                      <button
                        onClick={handleSaveEdits}
                        disabled={savingEdit}
                        className="inline-flex items-center gap-1.5 text-xs font-semibold text-white bg-brand-600 hover:bg-brand-700 px-3 py-1.5 rounded-lg shadow-sm"
                      >
                        <Save className="w-3.5 h-3.5" />
                        {savingEdit ? 'Saving...' : 'Save Draft'}
                      </button>
                    </div>
                  )}
                </div>

                {isEditing ? (
                  <div className="space-y-3">
                    <div>
                      <label className="block text-xs font-semibold text-slate-700 mb-1">Title</label>
                      <input
                        type="text"
                        value={editForm.title}
                        onChange={(e) => setEditForm({ ...editForm, title: e.target.value })}
                        className="w-full px-3 py-2 text-sm rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-brand-500"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-semibold text-slate-700 mb-1">Body Text</label>
                      <textarea
                        rows={6}
                        value={editForm.body}
                        onChange={(e) => setEditForm({ ...editForm, body: e.target.value })}
                        className="w-full px-3 py-2 text-sm rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-brand-500 font-mono text-xs leading-relaxed"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-semibold text-slate-700 mb-1">Call to Action</label>
                      <input
                        type="text"
                        value={editForm.call_to_action}
                        onChange={(e) => setEditForm({ ...editForm, call_to_action: e.target.value })}
                        className="w-full px-3 py-2 text-sm rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-brand-500"
                      />
                    </div>
                  </div>
                ) : (
                  <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 text-sm leading-relaxed text-slate-800 font-sans whitespace-pre-line">
                    {selectedAsset.body}
                  </div>
                )}

                {/* Detected Placeholders Chips */}
                <div className="flex items-center gap-2 flex-wrap pt-1">
                  <span className="text-[11px] font-semibold text-slate-500">Detected Dynamic Placeholders:</span>
                  {selectedAsset.detected_placeholders?.length > 0 ? (
                    selectedAsset.detected_placeholders.map((ph) => (
                      <span
                        key={ph}
                        className="text-[11px] font-mono px-2 py-0.5 rounded-md bg-brand-50 text-brand-700 border border-brand-200 font-medium"
                      >
                        {ph}
                      </span>
                    ))
                  ) : (
                    <span className="text-[11px] text-slate-400 italic">None</span>
                  )}
                </div>
              </div>

              {/* Multi-Channel Simulation Preview */}
              <div className="space-y-3 pt-4 border-t border-slate-200">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-slate-700 uppercase tracking-wider flex items-center gap-1.5">
                    <Eye className="w-3.5 h-3.5 text-brand-600" /> Multi-Channel Simulated Preview
                  </span>
                  <div className="flex items-center gap-1 p-0.5 bg-slate-100 rounded-lg">
                    {['Email', 'SMS', 'WhatsApp', 'Voice'].map((ch) => (
                      <button
                        key={ch}
                        onClick={() => setActivePreviewChannel(ch)}
                        className={`px-2.5 py-1 text-xs font-semibold rounded-md transition ${
                          activePreviewChannel === ch
                            ? 'bg-white text-slate-900 shadow-sm'
                            : 'text-slate-600 hover:text-slate-900'
                        }`}
                      >
                        {ch}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Channel-Specific Mockups */}
                {activePreviewChannel === 'SMS' && (
                  <div className="p-4 rounded-2xl bg-slate-900 text-white max-w-sm mx-auto shadow-inner space-y-3">
                    <div className="text-[11px] text-slate-400 flex items-center justify-between border-b border-slate-800 pb-2">
                      <span>SMS Direct Delivery</span>
                      <span>SIM 1 • GovAlert</span>
                    </div>
                    <div className="bg-sky-600 text-white p-3 rounded-2xl rounded-tl-sm text-xs leading-relaxed">
                      {selectedAsset.body}
                    </div>
                    <div className="text-[10px] text-slate-400 flex items-center justify-between pt-1">
                      <span>{selectedAsset.character_count} chars</span>
                      <span>
                        {selectedAsset.sms_segment_count} SMS segment(s)
                      </span>
                    </div>
                  </div>
                )}

                {activePreviewChannel === 'WhatsApp' && (
                  <div className="p-4 rounded-2xl bg-[#0b141a] text-white max-w-sm mx-auto shadow-inner space-y-3 font-sans">
                    <div className="text-[11px] text-emerald-400 flex items-center justify-between border-b border-slate-800 pb-2">
                      <span className="font-semibold flex items-center gap-1">
                        MassCommAI Official <CheckCircle2 className="w-3 h-3 text-emerald-500 fill-emerald-500 text-slate-900" />
                      </span>
                      <span className="text-slate-500 text-[10px]">Verified Account</span>
                    </div>
                    <div className="bg-[#005c4b] text-white p-3 rounded-xl rounded-tl-sm text-xs leading-relaxed whitespace-pre-line">
                      {selectedAsset.body}
                      {selectedAsset.call_to_action && (
                        <div className="mt-2.5 pt-2 border-t border-emerald-600/50 text-[11px] font-semibold text-emerald-200">
                          👉 {selectedAsset.call_to_action}
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {activePreviewChannel === 'Voice' && (
                  <div className="p-5 rounded-2xl bg-gradient-to-br from-indigo-950 to-slate-900 text-white max-w-md mx-auto shadow-md space-y-4">
                    <div className="flex items-center justify-between border-b border-slate-800 pb-2 text-xs text-indigo-300">
                      <span className="flex items-center gap-1.5">
                        <Volume2 className="w-4 h-4 text-indigo-400" /> Spoken IVR Telephony
                      </span>
                      <span>~{selectedAsset.voice_duration_seconds} seconds</span>
                    </div>
                    <div className="p-3 rounded-xl bg-slate-800/80 border border-slate-700 text-xs text-slate-200 italic leading-relaxed">
                      "{selectedAsset.body}"
                    </div>
                    <div className="text-[11px] text-slate-400 flex items-center justify-between">
                      <span>Audio Pacing: Natural 150 WPM</span>
                      <span className="text-emerald-400 font-semibold">Simulated IVR Ready</span>
                    </div>
                  </div>
                )}

                {activePreviewChannel === 'Email' && (
                  <div className="p-4 rounded-2xl bg-slate-50 border border-slate-300 text-slate-900 space-y-3 text-xs">
                    <div className="space-y-1 border-b border-slate-200 pb-2 text-[11px] text-slate-600">
                      <div><strong className="text-slate-800">Subject:</strong> {selectedAsset.title}</div>
                      <div><strong className="text-slate-800">From:</strong> public.awareness@masscommai.gov.in</div>
                      <div><strong className="text-slate-800">To:</strong> recipient.citizen@example.gov.in</div>
                    </div>
                    <div className="py-2 text-xs leading-relaxed whitespace-pre-line text-slate-800">
                      {selectedAsset.body}
                    </div>
                    {selectedAsset.call_to_action && (
                      <div className="pt-2">
                        <span className="inline-block px-4 py-2 rounded-lg bg-brand-600 text-white font-semibold text-xs shadow-sm">
                          {selectedAsset.call_to_action}
                        </span>
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* Review Lifecycle Actions Bar */}
              <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-3">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-bold text-slate-800 flex items-center gap-1.5">
                    <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                    Human Review & Editorial Sign-Off
                  </span>
                  <span className="text-[11px] text-slate-500">
                    Current: <strong>{selectedAsset.review_status}</strong>
                  </span>
                </div>

                <div className="flex items-center gap-2">
                  <input
                    type="text"
                    placeholder="Review notes or editorial verification remarks..."
                    value={reviewNotes}
                    onChange={(e) => setReviewNotes(e.target.value)}
                    className="flex-1 px-3 py-1.5 text-xs rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-brand-500"
                  />
                  {selectedAsset.review_status === 'Draft' && (
                    <button
                      onClick={() => handleReviewTransition('In Review')}
                      disabled={reviewActionLoading}
                      className="px-3 py-1.5 text-xs font-semibold text-white bg-amber-600 hover:bg-amber-700 rounded-lg shadow-sm transition"
                    >
                      Submit for Review
                    </button>
                  )}
                  {selectedAsset.review_status === 'In Review' && (
                    <>
                      <button
                        onClick={() => handleReviewTransition('Approved')}
                        disabled={reviewActionLoading}
                        className="px-3 py-1.5 text-xs font-semibold text-white bg-emerald-600 hover:bg-emerald-700 rounded-lg shadow-sm transition"
                      >
                        Approve Content
                      </button>
                      <button
                        onClick={() => handleReviewTransition('Rejected')}
                        disabled={reviewActionLoading}
                        className="px-3 py-1.5 text-xs font-semibold text-rose-700 bg-rose-100 hover:bg-rose-200 rounded-lg transition"
                      >
                        Reject
                      </button>
                    </>
                  )}
                  {selectedAsset.review_status === 'Approved' && (
                    <button
                      onClick={() => handleReviewTransition('Draft')}
                      disabled={reviewActionLoading}
                      className="px-3 py-1.5 text-xs font-semibold text-slate-700 bg-slate-200 hover:bg-slate-300 rounded-lg transition"
                    >
                      Reopen for Edit
                    </button>
                  )}
                </div>
              </div>

            </div>
          ) : (
            <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-12 text-center text-slate-500 space-y-3">
              <Sparkles className="w-10 h-10 text-slate-300 mx-auto" />
              <h3 className="text-base font-bold text-slate-800">Select or Generate Content</h3>
              <p className="text-xs text-slate-500 max-w-sm mx-auto">
                Choose a content asset from the library on the left, or generate a new public awareness brief with AI.
              </p>
              <button
                onClick={() => setGeneratorOpen(true)}
                className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-semibold text-white bg-brand-600 hover:bg-brand-700 rounded-xl shadow-sm"
              >
                <Sparkles className="w-3.5 h-3.5" />
                Open AI Generator
              </button>
            </div>
          )}

        </div>
      </div>

      {/* Modals */}
      <ContentGeneratorModal
        isOpen={generatorOpen}
        onClose={() => setGeneratorOpen(false)}
        onGenerated={handleGenerated}
      />

      <ContentTranslationModal
        isOpen={translationOpen}
        onClose={() => setTranslationOpen(false)}
        asset={selectedAsset}
        onTranslated={handleTranslated}
      />

      <ContentAttachModal
        isOpen={attachOpen}
        onClose={() => setAttachOpen(false)}
        asset={selectedAsset}
        onAttached={() => {
          setActionSuccess('Content successfully associated.');
          setTimeout(() => setActionSuccess(null), 3000);
        }}
      />
    </div>
  );
}

