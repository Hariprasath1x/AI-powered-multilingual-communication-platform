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
  FileCheck2,
  Sliders,
  ShieldCheck,
  History,
  AlertTriangle,
  Users,
} from 'lucide-react';
import {
  listContentAssets,
  getContentAsset,
  updateContentAsset,
  getContentVariants,
  updateReviewStatus,
  deleteContentAsset,
  previewChannelMetrics,
  getTranslationReviewHistory,
} from '../../services/contentService';
import {
  evaluateContentQuality,
  getLatestQualityAssessment,
  getEditorialReadiness,
} from '../../services/contentQualityService';
import ContentGeneratorModal from './ContentGeneratorModal';
import ContentTranslationModal from './ContentTranslationModal';
import ContentAttachModal from './ContentAttachModal';
import ContentQualityAuditPanel from './ContentQualityAuditPanel';
import ContentAssessmentHistoryModal from './ContentAssessmentHistoryModal';
import ContentTranslationComparisonView from './ContentTranslationComparisonView';
import ChannelConstraintsMeter from './ChannelConstraintsMeter';
import ToneOptimizationPanel from './ToneOptimizationPanel';
import PersonalizationVariantsPanel from './PersonalizationVariantsPanel';
import { useAuth } from '../../context/AuthContext';

const LANGUAGE_LABELS = {
  en: 'English',
  hi: 'Hindi (हिन्दी)',
  kn: 'Kannada (ಕನ್ನಡ)',
  ta: 'Tamil (தமிழ்)',
  te: 'Telugu (తెలుగు)',
  mr: 'Marathi (मराठी)',
  bn: 'Bengali (বাংলা)',
  gu: 'Gujarati (ગુજરાતી)',
  ml: 'Malayalam (മലയാളം)',
  pa: 'Punjabi (ਪੰਜਾਬੀ)',
  ur: 'Urdu (اردو)',
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
  const isUrdu = (selectedAsset?.target_language || selectedAsset?.source_language) === 'ur';

  // Live channel metrics state for active editing & channel preview simulation
  const [liveMetrics, setLiveMetrics] = useState(null);
  const [isLoadingLiveMetrics, setIsLoadingLiveMetrics] = useState(false);
  const [simulatedChannelMetrics, setSimulatedChannelMetrics] = useState({});
  const [loadingSimulatedMetrics, setLoadingSimulatedMetrics] = useState(false);

  // Modals
  const [generatorOpen, setGeneratorOpen] = useState(false);
  const [translationOpen, setTranslationOpen] = useState(false);
  const [attachOpen, setAttachOpen] = useState(false);
  const [historyModalOpen, setHistoryModalOpen] = useState(false);
  const [translationReviewHistoryModalOpen, setTranslationReviewHistoryModalOpen] = useState(false);
  const [translationReviewHistoryList, setTranslationReviewHistoryList] = useState([]);
  const [translationReviewHistoryLoading, setTranslationReviewHistoryLoading] = useState(false);

  // Quality Assessment & Compliance state
  const [qualityAssessment, setQualityAssessment] = useState(null);
  const [editorialReadiness, setEditorialReadiness] = useState(null);
  const [evaluatingQuality, setEvaluatingQuality] = useState(false);
  const [activeStudioTab, setActiveStudioTab] = useState('quality'); // 'quality' | 'preview' | 'comparison'

  // Review Status action state
  const [reviewNotes, setReviewNotes] = useState('');
  const [reviewActionLoading, setReviewActionLoading] = useState(false);

  // Load quality evaluation and readiness for active asset
  const loadQualityData = async (assetId) => {
    try {
      const [assessRes, readinessRes] = await Promise.allSettled([
        getLatestQualityAssessment(assetId),
        getEditorialReadiness(assetId),
      ]);
      setQualityAssessment(assessRes.status === 'fulfilled' ? assessRes.value : null);
      setEditorialReadiness(readinessRes.status === 'fulfilled' ? readinessRes.value : null);
    } catch (err) {
      console.error('Failed to load quality data:', err);
    }
  };

  // Run on-demand quality & compliance audit
  const handleRunAudit = async (referenceFacts) => {
    if (!selectedAsset) return;
    setEvaluatingQuality(true);
    setError(null);
    try {
      const result = await evaluateContentQuality(selectedAsset.id, {
        reference_facts: referenceFacts || undefined,
      });
      setQualityAssessment(result);
      const readiness = await getEditorialReadiness(selectedAsset.id);
      setEditorialReadiness(readiness);
      setActionSuccess('Editorial quality and compliance assessment complete.');
      setTimeout(() => setActionSuccess(null), 3000);
    } catch (err) {
      console.error('Failed to evaluate content quality:', err);
      setError(err.response?.data?.detail || 'Quality evaluation failed.');
    } finally {
      setEvaluatingQuality(false);
    }
  };

  // Callback when a finding decision is updated
  const handleFindingUpdated = async () => {
    if (selectedAsset) {
      await loadQualityData(selectedAsset.id);
    }
  };

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

  // Debounced live calculation for active copy editing (300ms)
  useEffect(() => {
    if (!isEditing || !selectedAsset) return;

    const controller = new AbortController();
    setIsLoadingLiveMetrics(true);

    const timer = setTimeout(async () => {
      try {
        const metrics = await previewChannelMetrics(
          {
            channel: selectedAsset.channel,
            body: editForm.body || '',
            title: editForm.title || '',
            call_to_action: editForm.call_to_action || '',
            language: selectedAsset.target_language || selectedAsset.source_language || 'en',
          },
          controller.signal
        );
        setLiveMetrics(metrics);
      } catch (err) {
        if (err.name !== 'CanceledError' && err.name !== 'AbortError' && err.code !== 'ERR_CANCELED') {
          console.warn('Failed to calculate live preview metrics:', err);
        }
      } finally {
        setIsLoadingLiveMetrics(false);
      }
    }, 300);

    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [
    isEditing,
    editForm.body,
    editForm.title,
    editForm.call_to_action,
    selectedAsset?.id,
    selectedAsset?.channel,
    selectedAsset?.target_language,
    selectedAsset?.source_language,
  ]);

  // Load metrics when simulating preview for different channels in Multi-Channel Preview tab
  useEffect(() => {
    if (!selectedAsset) return;
    if (activeStudioTab !== 'preview') return;
    if (activePreviewChannel === selectedAsset.channel) return;
    if (simulatedChannelMetrics[activePreviewChannel]) return;

    const controller = new AbortController();
    setLoadingSimulatedMetrics(true);

    previewChannelMetrics(
      {
        channel: activePreviewChannel,
        body: selectedAsset.body || '',
        title: selectedAsset.title || '',
        call_to_action: selectedAsset.call_to_action || '',
        language: selectedAsset.target_language || selectedAsset.source_language || 'en',
      },
      controller.signal
    )
      .then((data) => {
        setSimulatedChannelMetrics((prev) => ({ ...prev, [activePreviewChannel]: data }));
      })
      .catch((err) => {
        if (err.name !== 'CanceledError' && err.name !== 'AbortError' && err.code !== 'ERR_CANCELED') {
          console.warn('Failed to calculate simulated channel metrics:', err);
        }
      })
      .finally(() => {
        setLoadingSimulatedMetrics(false);
      });

    return () => {
      controller.abort();
    };
  }, [
    activeStudioTab,
    activePreviewChannel,
    selectedAsset?.id,
    selectedAsset?.body,
    selectedAsset?.channel,
    selectedAsset?.target_language,
    selectedAsset?.source_language,
    simulatedChannelMetrics,
  ]);

  const handleSearchSubmit = (e) => {
    e.preventDefault();
    loadAssets(1);
  };

  // Select an asset to display in Studio workspace
  const selectAsset = async (asset) => {
    setSelectedAsset(asset);
    setIsEditing(false);
    setLiveMetrics(null);
    setSimulatedChannelMetrics({});
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

    // Load quality audit and editorial readiness
    await loadQualityData(asset.id);
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

  // Handle newly translated content (single or batch)
  const handleTranslated = (result) => {
    setActionSuccess('Translation generated successfully!');
    loadAssets(page);
    if (result && result.id) {
      refreshActiveAsset(result.id);
    } else if (result && result.successes && result.successes.length > 0) {
      refreshActiveAsset(result.successes[0].id);
    } else if (selectedAsset) {
      refreshActiveAsset(selectedAsset.id);
    }
    setTimeout(() => setActionSuccess(null), 3000);
  };

  // Open Translation Review History audit modal
  const handleOpenReviewHistory = async () => {
    if (!selectedAsset) return;
    setTranslationReviewHistoryLoading(true);
    setTranslationReviewHistoryModalOpen(true);
    try {
      const history = await getTranslationReviewHistory(selectedAsset.id);
      setTranslationReviewHistoryList(history || []);
    } catch (err) {
      console.error('Failed to load translation review audit history:', err);
    } finally {
      setTranslationReviewHistoryLoading(false);
    }
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
      case 'Needs Review':
        return 'bg-amber-100 text-amber-800 border-amber-200';
      case 'Generated':
        return 'bg-sky-100 text-sky-800 border-sky-200';
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
      <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 pb-2 border-b border-slate-200">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-blue-50 text-blue-600 border border-blue-100 flex items-center justify-center">
            <Sparkles className="w-5 h-5 text-blue-600" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
              AI Content & Translation Studio
            </h1>
            <p className="text-sm text-slate-500">
              Generate, translate, review, and channel-optimize public awareness communications across 6 Indian languages.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => setGeneratorOpen(true)}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg font-semibold text-white bg-blue-600 hover:bg-blue-700 transition shadow-2xs text-xs active:scale-[0.98]"
          >
            <Sparkles className="w-4 h-4" />
            Generate with AI
          </button>
        </div>
      </div>

      {/* Mandatory Human Review Guard Notice */}
      <div className="bg-slate-50 border border-slate-200 rounded-xl p-4 flex items-start gap-3.5">
        <ShieldAlert className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" />
        <div className="space-y-1 text-xs text-slate-800 leading-relaxed">
          <p className="font-bold text-xs text-slate-900">Responsible AI & Human-in-the-Loop Governance</p>
          <p className="text-[11px] text-slate-500">
            All AI-generated copy and machine translations are initialized in <strong>Draft</strong> status.
            Official public service announcements, emergency alerts, and health directives require verified human review
            before approval or campaign dispatch. Placeholders such as <code className="bg-white border border-slate-200 px-1 py-0.5 rounded font-mono text-[10px]">&#123;name&#125;</code> and <code className="bg-white border border-slate-200 px-1 py-0.5 rounded font-mono text-[10px]">&#123;city&#125;</code> are strictly preserved across language variants.
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
                    {selectedAsset.provider_metadata?.source_outdated && (
                      <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full border bg-amber-50 text-amber-800 border-amber-200">
                        Source Modified
                      </span>
                    )}
                    {selectedAsset.provider_metadata?.is_human_edited && (
                      <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full border bg-slate-100 text-slate-800 border-slate-200">
                        Human Edited
                      </span>
                    )}
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

              {/* Outdated Source Content Alert Banner (AUDIT-T8-04) */}
              {selectedAsset.provider_metadata?.source_outdated && (
                <div className="rounded-xl border border-amber-300 bg-amber-50 p-3.5 flex items-start gap-3">
                  <AlertTriangle className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
                  <div className="text-xs text-amber-900 space-y-1">
                    <p className="font-semibold text-amber-950">
                      Source Content Modified
                    </p>
                    <p>
                      The root source content for this campaign was modified by an editor after this translation was created.
                      Review status was reset to Needs Review. Please re-translate or review the translation to ensure message accuracy before broadcasting.
                    </p>
                  </div>
                </div>
              )}

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
                        dir={isUrdu ? 'rtl' : 'ltr'}
                        className={`w-full px-3 py-2 text-sm rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-brand-500 ${isUrdu ? 'text-right' : ''}`}
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-semibold text-slate-700 mb-1">Body Text</label>
                      <textarea
                        rows={6}
                        value={editForm.body}
                        onChange={(e) => setEditForm({ ...editForm, body: e.target.value })}
                        dir={isUrdu ? 'rtl' : 'ltr'}
                        className={`w-full px-3 py-2 text-sm rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-brand-500 font-mono text-xs leading-relaxed ${isUrdu ? 'text-right' : ''}`}
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-semibold text-slate-700 mb-1">Call to Action</label>
                      <input
                        type="text"
                        value={editForm.call_to_action}
                        onChange={(e) => setEditForm({ ...editForm, call_to_action: e.target.value })}
                        dir={isUrdu ? 'rtl' : 'ltr'}
                        className={`w-full px-3 py-2 text-sm rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-brand-500 ${isUrdu ? 'text-right' : ''}`}
                      />
                    </div>

                    {/* Live Channel Constraints Meter during active editing */}
                    <ChannelConstraintsMeter
                      metrics={liveMetrics || selectedAsset.channel_metrics}
                      isLive={true}
                      loading={isLoadingLiveMetrics}
                      language={selectedAsset.target_language || selectedAsset.source_language}
                    />
                  </div>
                ) : (
                  <div className="space-y-3">
                    <div
                      dir={isUrdu ? 'rtl' : 'ltr'}
                      className={`p-4 rounded-xl bg-slate-50 border border-slate-200 text-sm leading-relaxed text-slate-800 font-sans whitespace-pre-line ${isUrdu ? 'text-right' : ''}`}
                    >
                      {selectedAsset.body}
                    </div>

                    {/* Persisted Channel Constraints Snapshot on saved draft */}
                    {selectedAsset.channel_metrics && (
                      <ChannelConstraintsMeter
                        metrics={selectedAsset.channel_metrics}
                        isLive={false}
                        language={selectedAsset.target_language || selectedAsset.source_language}
                      />
                    )}
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

              {/* Studio Workspace Tabs */}
              <div className="space-y-4 pt-4 border-t border-slate-200">
                <div className="flex items-center justify-between border-b border-slate-200 pb-2">
                  <div className="flex items-center gap-1.5 flex-wrap">
                    <button
                      onClick={() => setActiveStudioTab('quality')}
                      className={`inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold rounded-lg transition ${
                        activeStudioTab === 'quality'
                          ? 'bg-brand-50 text-brand-700 border border-brand-200 shadow-sm'
                          : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50'
                      }`}
                    >
                      <FileCheck2 className="w-3.5 h-3.5 text-brand-600" />
                      Quality & Compliance
                      {editorialReadiness?.score !== undefined && editorialReadiness?.score !== null && (
                        <span className={`text-[10px] px-1.5 py-0.2 rounded-full font-bold ml-1 ${
                          editorialReadiness.readiness_status === 'Ready'
                            ? 'bg-emerald-100 text-emerald-800'
                            : editorialReadiness.readiness_status === 'Blocked'
                            ? 'bg-rose-100 text-rose-800'
                            : 'bg-amber-100 text-amber-800'
                        }`}>
                          {editorialReadiness.score}
                        </span>
                      )}
                    </button>

                    <button
                      onClick={() => setActiveStudioTab('preview')}
                      className={`inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold rounded-lg transition ${
                        activeStudioTab === 'preview'
                          ? 'bg-brand-50 text-brand-700 border border-brand-200 shadow-sm'
                          : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50'
                      }`}
                    >
                      <Eye className="w-3.5 h-3.5 text-slate-500" />
                      Multi-Channel Preview
                    </button>

                    {selectedAsset.operation_type === 'translation' && (
                      <button
                        onClick={() => setActiveStudioTab('comparison')}
                        className={`inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold rounded-lg transition ${
                          activeStudioTab === 'comparison'
                            ? 'bg-brand-50 text-brand-700 border border-brand-200 shadow-sm'
                            : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50'
                        }`}
                      >
                        <Sliders className="w-3.5 h-3.5 text-indigo-600" />
                        Translation Comparison
                      </button>
                    )}

                    <button
                      onClick={() => setActiveStudioTab('tone')}
                      className={`inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold rounded-lg transition ${
                        activeStudioTab === 'tone'
                          ? 'bg-brand-50 text-brand-700 border border-brand-200 shadow-sm'
                          : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50'
                      }`}
                    >
                      <Sparkles className="w-3.5 h-3.5 text-indigo-600" />
                      Tone & Sentiment
                    </button>

                    <button
                      onClick={() => setActiveStudioTab('personalization')}
                      className={`inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold rounded-lg transition ${
                        activeStudioTab === 'personalization'
                          ? 'bg-brand-50 text-brand-700 border border-brand-200 shadow-sm'
                          : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50'
                      }`}
                    >
                      <Users className="w-3.5 h-3.5 text-emerald-600" />
                      Audience Variants
                    </button>
                  </div>
                </div>

                {/* Tab 1: Quality & Compliance Panel */}
                {activeStudioTab === 'quality' && (
                  <ContentQualityAuditPanel
                    assessment={qualityAssessment}
                    asset={selectedAsset}
                    onRunAudit={handleRunAudit}
                    evaluating={evaluatingQuality}
                    onFindingUpdated={handleFindingUpdated}
                    onViewHistory={() => setHistoryModalOpen(true)}
                  />
                )}

                {/* Tab 2: Multi-Channel Simulation Preview */}
                {activeStudioTab === 'preview' && (() => {
                  const isUrdu = (selectedAsset.target_language || selectedAsset.source_language) === 'ur';
                  return (
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-slate-700 uppercase tracking-wider flex items-center gap-1.5">
                        <Eye className="w-3.5 h-3.5 text-brand-600" /> Multi-Channel Simulated Preview {isUrdu ? '(Urdu RTL Layout)' : ''}
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
                        <div
                          className={`bg-sky-600 text-white p-3 rounded-2xl rounded-tl-sm text-xs leading-relaxed ${isUrdu ? 'text-right' : ''}`}
                          dir={isUrdu ? 'rtl' : 'ltr'}
                        >
                          {selectedAsset.body}
                        </div>
                        <div className="text-[10px] text-slate-400 flex items-center justify-between pt-1">
                          <span>
                            {selectedAsset.character_count} chars &bull;{' '}
                            {(activePreviewChannel === selectedAsset.channel
                              ? selectedAsset.channel_metrics?.sms?.encoding
                              : simulatedChannelMetrics.SMS?.sms?.encoding) || 'GSM-7'}
                          </span>
                          <span>
                            {(activePreviewChannel === selectedAsset.channel
                              ? selectedAsset.channel_metrics?.sms?.segment_count
                              : simulatedChannelMetrics.SMS?.sms?.segment_count) || selectedAsset.sms_segment_count}{' '}
                            SMS segment(s)
                          </span>
                        </div>
                      </div>
                    )}

                    {activePreviewChannel === 'WhatsApp' && (
                      <div className="p-4 rounded-2xl bg-[#0b141a] text-white max-w-sm mx-auto shadow-inner space-y-3 font-sans">
                        <div className="text-[11px] text-emerald-400 flex items-center justify-between border-b border-slate-800 pb-2">
                          <span className="font-semibold flex items-center gap-1">
                            Civora Official <CheckCircle2 className="w-3 h-3 text-emerald-500 fill-emerald-500 text-slate-900" />
                          </span>
                          <span className="text-slate-500 text-[10px]">Verified Account</span>
                        </div>
                        <div
                          className={`bg-[#005c4b] text-white p-3 rounded-xl rounded-tl-sm text-xs leading-relaxed whitespace-pre-line ${isUrdu ? 'text-right' : ''}`}
                          dir={isUrdu ? 'rtl' : 'ltr'}
                        >
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
                          <span>
                            ~
                            {(activePreviewChannel === selectedAsset.channel
                              ? selectedAsset.channel_metrics?.estimated_duration_seconds
                              : simulatedChannelMetrics.Voice?.estimated_duration_seconds) ||
                              selectedAsset.voice_duration_seconds ||
                              5}{' '}
                            seconds
                          </span>
                        </div>
                        <div
                          className={`p-3 rounded-xl bg-slate-800/80 border border-slate-700 text-xs text-slate-200 italic leading-relaxed ${isUrdu ? 'text-right' : ''}`}
                          dir={isUrdu ? 'rtl' : 'ltr'}
                        >
                          "{selectedAsset.body}"
                        </div>
                        <div className="text-[11px] text-slate-400 flex items-center justify-between">
                          <span>
                            Audio Pacing:{' '}
                            {(selectedAsset.target_language || selectedAsset.source_language) === 'en'
                              ? 'Natural 150 WPM'
                              : `${LANGUAGE_LABELS[selectedAsset.target_language || selectedAsset.source_language] || 'Indic'} Pacing (~115-130 WPM)`}
                          </span>
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
                        <div
                          className={`py-2 text-xs leading-relaxed whitespace-pre-line text-slate-800 ${isUrdu ? 'text-right' : ''}`}
                          dir={isUrdu ? 'rtl' : 'ltr'}
                        >
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

                    {/* Telecommunications Constraints & Warning Details for Active Preview Channel */}
                    {(() => {
                      const currentMetrics =
                        activePreviewChannel === selectedAsset.channel
                          ? selectedAsset.channel_metrics
                          : simulatedChannelMetrics[activePreviewChannel];
                      return (
                        <ChannelConstraintsMeter
                          metrics={currentMetrics}
                          isLive={activePreviewChannel !== selectedAsset.channel}
                          loading={loadingSimulatedMetrics && activePreviewChannel !== selectedAsset.channel}
                          language={selectedAsset.target_language || selectedAsset.source_language}
                        />
                      );
                    })()}
                  </div>
                  );
                })()}

                {/* Tab 3: Translation Comparison */}
                {activeStudioTab === 'comparison' && (
                  <ContentTranslationComparisonView
                    asset={selectedAsset}
                    parentAsset={variants.find((v) => v.id === selectedAsset.parent_id) || variants.find((v) => v.parent_id === null && v.id !== selectedAsset.id)}
                  />
                )}

                {/* Tab 4: Sentiment & Tone Optimization */}
                {activeStudioTab === 'tone' && (
                  <ToneOptimizationPanel
                    assetId={selectedAsset.id}
                    currentText={isEditing ? editBody : selectedAsset.body}
                    channel={selectedAsset.channel}
                    onApplyImprovement={(improvedText) => {
                      setEditBody(improvedText);
                      setIsEditing(true);
                    }}
                  />
                )}

                {/* Tab 5: Audience-Specific Personalization Variants */}
                {activeStudioTab === 'personalization' && (
                  <PersonalizationVariantsPanel
                    assetId={selectedAsset.id}
                    campaignId={selectedAsset.campaign_id}
                    channel={selectedAsset.channel}
                    sourceLanguage={selectedAsset.source_language || 'en'}
                    canReview={user?.role === 'Admin' || user?.role === 'Campaign Manager'}
                  />
                )}
              </div>

              {/* Editorial Readiness & Approval Gate Banner */}
              {editorialReadiness && (
                <div className={`p-4 rounded-xl border text-xs flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 ${
                  editorialReadiness.is_approval_blocked
                    ? 'bg-rose-50 border-rose-200 text-rose-900'
                    : editorialReadiness.readiness_status === 'Ready'
                    ? 'bg-emerald-50 border-emerald-200 text-emerald-900'
                    : 'bg-amber-50 border-amber-200 text-amber-900'
                }`}>
                  <div className="flex items-start gap-2.5">
                    <ShieldCheck className={`w-5 h-5 flex-shrink-0 mt-0.5 ${
                      editorialReadiness.is_approval_blocked ? 'text-rose-600' : 'text-emerald-600'
                    }`} />
                    <div className="space-y-0.5">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-bold text-sm">
                          Editorial Readiness: {editorialReadiness.readiness_status}
                        </span>
                        {editorialReadiness.score !== null && (
                          <span className="font-mono font-semibold text-xs px-2 py-0.5 rounded bg-white/80 border border-slate-200">
                            Score: {editorialReadiness.score}/100
                          </span>
                        )}
                        {editorialReadiness.is_outdated && (
                          <span className="text-rose-700 font-semibold bg-rose-100 px-2 py-0.5 rounded text-[11px] border border-rose-200">
                            Content modified since last evaluation
                          </span>
                        )}
                      </div>
                      {editorialReadiness.blocking_reasons?.length > 0 && (
                        <p className="text-[11px] text-rose-700">
                          {editorialReadiness.blocking_reasons.join(' • ')}
                        </p>
                      )}
                    </div>
                  </div>
                  {editorialReadiness.is_approval_blocked && (
                    <span className="text-[10px] font-bold uppercase tracking-wider text-rose-700 bg-white px-2.5 py-1 rounded-md border border-rose-300 shadow-sm flex-shrink-0">
                      Approval Blocked
                    </span>
                  )}
                </div>
              )}

              {/* Review Lifecycle Actions Bar */}
              <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-3">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-bold text-slate-800 flex items-center gap-1.5">
                    <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                    Human Review & Editorial Sign-Off
                  </span>
                  <div className="flex items-center gap-2">
                    <span className="text-[11px] text-slate-500">
                      Current: <strong>{selectedAsset.review_status}</strong>
                    </span>
                    <button
                      type="button"
                      onClick={handleOpenReviewHistory}
                      className="inline-flex items-center gap-1 text-[11px] font-semibold text-indigo-600 hover:text-indigo-800 bg-indigo-50 hover:bg-indigo-100 px-2 py-0.5 rounded transition"
                      title="View chronological review transition audit trail"
                    >
                      <History className="w-3 h-3" />
                      Review History
                    </button>
                  </div>
                </div>

                <div className="flex items-center gap-2 flex-wrap">
                  <input
                    type="text"
                    placeholder="Review notes or editorial verification remarks..."
                    value={reviewNotes}
                    onChange={(e) => setReviewNotes(e.target.value)}
                    className="flex-1 min-w-[200px] px-3 py-1.5 text-xs rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-brand-500"
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
                  {selectedAsset.review_status === 'Generated' && (
                    <>
                      <button
                        onClick={() => handleReviewTransition('Needs Review')}
                        disabled={reviewActionLoading}
                        className="px-3 py-1.5 text-xs font-semibold text-white bg-amber-600 hover:bg-amber-700 rounded-lg shadow-sm transition"
                      >
                        Submit for Review
                      </button>
                      <button
                        onClick={() => handleReviewTransition('Approved')}
                        disabled={reviewActionLoading || editorialReadiness?.is_approval_blocked}
                        className={`px-3 py-1.5 text-xs font-semibold text-white rounded-lg shadow-sm transition ${
                          editorialReadiness?.is_approval_blocked
                            ? 'bg-slate-300 text-slate-500 cursor-not-allowed'
                            : 'bg-emerald-600 hover:bg-emerald-700'
                        }`}
                      >
                        Direct Approve
                      </button>
                    </>
                  )}
                  {selectedAsset.review_status === 'Needs Review' && (
                    <>
                      <button
                        onClick={() => handleReviewTransition('Approved')}
                        disabled={reviewActionLoading || editorialReadiness?.is_approval_blocked}
                        className={`px-3 py-1.5 text-xs font-semibold text-white rounded-lg shadow-sm transition ${
                          editorialReadiness?.is_approval_blocked
                            ? 'bg-slate-300 text-slate-500 cursor-not-allowed'
                            : 'bg-emerald-600 hover:bg-emerald-700'
                        }`}
                        title={
                          editorialReadiness?.is_approval_blocked
                            ? editorialReadiness.blocking_reasons?.join(', ') || 'Approval blocked by unresolved critical findings'
                            : 'Approve Content'
                        }
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
                  {selectedAsset.review_status === 'In Review' && (
                    <>
                      <button
                        onClick={() => handleReviewTransition('Approved')}
                        disabled={reviewActionLoading || editorialReadiness?.is_approval_blocked}
                        className={`px-3 py-1.5 text-xs font-semibold text-white rounded-lg shadow-sm transition ${
                          editorialReadiness?.is_approval_blocked
                            ? 'bg-slate-300 text-slate-500 cursor-not-allowed'
                            : 'bg-emerald-600 hover:bg-emerald-700'
                        }`}
                        title={
                          editorialReadiness?.is_approval_blocked
                            ? editorialReadiness.blocking_reasons?.join(', ') || 'Approval blocked by unresolved critical findings'
                            : 'Approve Content'
                        }
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
                  {selectedAsset.review_status === 'Rejected' && (
                    <button
                      onClick={() => handleReviewTransition('Needs Review')}
                      disabled={reviewActionLoading}
                      className="px-3 py-1.5 text-xs font-semibold text-amber-700 bg-amber-100 hover:bg-amber-200 rounded-lg transition"
                    >
                      Reopen for Review
                    </button>
                  )}
                  {selectedAsset.review_status === 'Approved' && (
                    <button
                      onClick={() => handleReviewTransition(selectedAsset.parent_id ? 'Needs Review' : 'Draft')}
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

      <ContentAssessmentHistoryModal
        isOpen={historyModalOpen}
        onClose={() => setHistoryModalOpen(false)}
        assetId={selectedAsset?.id}
      />

      {/* Translation Review Audit History Modal */}
      {translationReviewHistoryModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-sm overflow-y-auto">
          <div className="relative w-full max-w-lg bg-white rounded-xl shadow-xl border border-slate-200 overflow-hidden my-8">
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 bg-slate-50">
              <div className="flex items-center gap-2">
                <History className="w-5 h-5 text-indigo-600" />
                <div>
                  <h3 className="text-base font-bold text-slate-900">Translation Review Audit Trail</h3>
                  <p className="text-xs text-slate-500">Asset #{selectedAsset?.id} Editorial Lifecycle</p>
                </div>
              </div>
              <button
                onClick={() => setTranslationReviewHistoryModalOpen(false)}
                className="p-1 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="p-6 max-h-96 overflow-y-auto space-y-3">
              {translationReviewHistoryLoading ? (
                <div className="text-center py-6 text-xs text-slate-500">Loading audit history...</div>
              ) : translationReviewHistoryList.length === 0 ? (
                <div className="text-center py-6 text-xs text-slate-500 italic">
                  No editorial review transitions recorded yet for this asset.
                </div>
              ) : (
                <div className="relative border-l-2 border-indigo-100 ml-3 space-y-4 text-xs">
                  {translationReviewHistoryList.map((entry) => (
                    <div key={entry.id} className="ml-4 space-y-1 relative">
                      <div className="absolute -left-[23px] top-1 w-2.5 h-2.5 rounded-full bg-indigo-600 border-2 border-white ring-2 ring-indigo-100" />
                      <div className="flex items-center justify-between text-[11px]">
                        <span className="font-semibold text-slate-900">
                          {entry.from_status} → <span className="text-indigo-600 font-bold">{entry.to_status}</span>
                        </span>
                        <span className="text-slate-400">
                          {new Date(entry.created_at).toLocaleString()}
                        </span>
                      </div>
                      <div className="text-[11px] text-slate-600">
                        Reviewer: <span className="font-medium text-slate-800">{entry.reviewer_name || `User #${entry.reviewer_id}`}</span>
                      </div>
                      {entry.review_notes && (
                        <p className="text-[11px] text-slate-600 bg-slate-50 p-2 rounded border border-slate-100 italic">
                          "{entry.review_notes}"
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
            <div className="px-6 py-3 border-t border-slate-200 bg-slate-50 flex justify-end">
              <button
                onClick={() => setTranslationReviewHistoryModalOpen(false)}
                className="px-4 py-1.5 text-xs font-semibold text-slate-700 bg-white border border-slate-200 hover:bg-slate-100 rounded-lg transition"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

