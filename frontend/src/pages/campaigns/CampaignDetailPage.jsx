import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate, useLocation, Link } from 'react-router-dom';
import {
  Megaphone,
  Layers,
  Calendar,
  FileText,
  Clock,
  CheckCircle2,
  AlertCircle,
  ArrowLeft,
  Edit2,
  Trash2,
  ArrowRight,
  ShieldCheck,
  Smartphone,
  Mail,
  MessageCircle,
  PhoneCall,
  Sparkles,
  Users,
  Archive,
  RefreshCw,
  SendHorizontal
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import {
  getCampaign,
  transitionCampaignStatus,
  previewCampaign
} from '../../services/campaignService';
import CampaignDeleteModal from './CampaignDeleteModal';

export default function CampaignDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const { user, isAdmin, isCampaignManager } = useAuth();

  const [campaign, setCampaign] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [toastMessage, setToastMessage] = useState(location.state?.message || '');

  // Transition in progress
  const [transitioning, setTransitioning] = useState(false);
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);

  // Previews
  const [activeChannelTab, setActiveChannelTab] = useState('Email');
  const [previewData, setPreviewData] = useState(null);

  const fetchCampaign = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getCampaign(id);
      setCampaign(data);

      if (data.channels && data.channels.length > 0) {
        setActiveChannelTab(data.channels[0]);
      }

      // Fetch live backend preview if template exists
      if (data.template_id) {
        previewCampaign(data.id)
          .then((p) => setPreviewData(p))
          .catch(() => {});
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load campaign details.');
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    fetchCampaign();
  }, [fetchCampaign]);

  const showToast = (msg) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(''), 4500);
  };

  const isOwner = isAdmin || (isCampaignManager && campaign?.created_by === user?.id);
  const isEditable = isOwner && (campaign?.status === 'Draft' || campaign?.status === 'In Review');
  const isDeletable = isOwner && (campaign?.status === 'Draft' || campaign?.status === 'Archived');

  const handleStatusTransition = async (newStatus) => {
    if (!isOwner) return;
    setTransitioning(true);
    try {
      const updated = await transitionCampaignStatus(campaign.id, newStatus);
      setCampaign(updated);
      showToast(`Campaign transitioned to '${newStatus}' successfully.`);
    } catch (err) {
      showToast(err.response?.data?.detail || `Failed to transition to '${newStatus}'.`);
    } finally {
      setTransitioning(false);
    }
  };

  const getStatusBadge = (status) => {
    switch (status) {
      case 'Draft':
        return 'bg-slate-100 text-slate-700 border-slate-300';
      case 'In Review':
        return 'bg-amber-100 text-amber-800 border-amber-300';
      case 'Approved':
        return 'bg-blue-100 text-blue-800 border-blue-300';
      case 'Scheduled':
        return 'bg-emerald-100 text-emerald-800 border-emerald-300';
      case 'Archived':
      default:
        return 'bg-rose-100 text-rose-800 border-rose-200';
    }
  };

  const getPriorityBadge = (priority) => {
    switch (priority) {
      case 'High':
        return 'bg-rose-100 text-rose-800 border-rose-200';
      case 'Medium':
        return 'bg-amber-100 text-amber-800 border-amber-200';
      case 'Low':
      default:
        return 'bg-slate-100 text-slate-700 border-slate-200';
    }
  };

  if (loading) {
    return (
      <div className="max-w-5xl mx-auto px-4 py-20 text-center space-y-3">
        <RefreshCw className="w-8 h-8 text-brand-600 animate-spin mx-auto" />
        <p className="text-sm font-medium text-slate-500">Loading campaign details...</p>
      </div>
    );
  }

  if (error || !campaign) {
    return (
      <div className="max-w-3xl mx-auto px-4 py-16 text-center space-y-4">
        <div className="p-6 bg-white rounded-2xl border border-slate-200 space-y-3">
          <AlertCircle className="w-10 h-10 text-rose-500 mx-auto" />
          <h2 className="text-lg font-bold text-slate-800">Campaign Not Found</h2>
          <p className="text-sm text-slate-500">{error || 'The requested campaign does not exist.'}</p>
          <Link
            to="/campaigns"
            className="inline-flex items-center gap-1.5 px-4 py-2 bg-brand-600 text-white text-xs font-semibold rounded-xl hover:bg-brand-700 transition"
          >
            <ArrowLeft className="w-4 h-4" /> Return to Directory
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      
      {/* Toast Alert */}
      {toastMessage && (
        <div className="fixed bottom-6 right-6 z-50 flex items-center gap-2.5 px-4 py-3 bg-slate-900 text-white text-sm font-medium rounded-xl shadow-2xl border border-slate-700 animate-fade-in">
          <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
          <span>{toastMessage}</span>
        </div>
      )}

      {/* Breadcrumb & Navigation */}
      <div className="flex items-center justify-between">
        <Link
          to="/campaigns"
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-500 hover:text-brand-600 transition"
        >
          <ArrowLeft className="w-4 h-4" /> Back to Campaigns Directory
        </Link>
        <span className="text-xs font-mono text-slate-400">Campaign ID #{campaign.id}</span>
      </div>

      {/* Main Campaign Header Card */}
      <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm space-y-6">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-2">
            <div className="flex items-center gap-2.5 flex-wrap">
              <span className={`text-xs font-bold px-2.5 py-0.5 rounded-full border ${getStatusBadge(campaign.status)}`}>
                {campaign.status}
              </span>
              <span className={`text-xs font-bold px-2.5 py-0.5 rounded-full border ${getPriorityBadge(campaign.priority)}`}>
                {campaign.priority} Priority
              </span>
              <span className="text-xs font-medium px-2 py-0.5 rounded-md bg-slate-100 text-slate-600">
                {campaign.campaign_type}
              </span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">
              {campaign.name}
            </h1>
            {campaign.objective && (
              <p className="text-sm text-slate-600 max-w-3xl leading-relaxed">
                {campaign.objective}
              </p>
            )}
          </div>

          {/* Action Buttons */}
          <div className="flex items-center gap-2 flex-wrap self-start md:self-auto">
            {isEditable && (
              <Link
                to={`/campaigns/${campaign.id}/edit`}
                className="inline-flex items-center gap-1.5 px-3.5 py-2 text-xs font-semibold rounded-xl bg-white border border-slate-200 text-slate-700 hover:bg-slate-50 transition shadow-2xs"
              >
                <Edit2 className="w-3.5 h-3.5 text-slate-500" />
                Edit Settings
              </Link>
            )}
            {isDeletable && (
              <button
                onClick={() => setDeleteModalOpen(true)}
                className="inline-flex items-center gap-1.5 px-3.5 py-2 text-xs font-semibold rounded-xl bg-white border border-slate-200 text-rose-600 hover:bg-rose-50 transition shadow-2xs"
              >
                <Trash2 className="w-3.5 h-3.5" />
                Delete
              </button>
            )}
          </div>
        </div>

        {/* Lifecycle Transitions Control Bar */}
        {isOwner && (
          <div className="pt-4 border-t border-slate-100 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 bg-slate-50 p-4 rounded-xl">
            <div className="space-y-0.5">
              <span className="text-xs font-bold text-slate-800 uppercase tracking-wider block">
                Lifecycle State Actions:
              </span>
              <p className="text-[11px] text-slate-500">
                Current status: <strong>{campaign.status}</strong>. Transitions are enforced by backend state machine.
              </p>
            </div>

            <div className="flex items-center gap-2 flex-wrap">
              {/* Draft -> In Review / Approved / Archived */}
              {campaign.status === 'Draft' && (
                <>
                  <button
                    onClick={() => handleStatusTransition('In Review')}
                    disabled={transitioning}
                    className="px-3 py-1.5 text-xs font-bold rounded-lg bg-amber-600 text-white hover:bg-amber-700 transition"
                  >
                    Submit for Review
                  </button>
                  <button
                    onClick={() => handleStatusTransition('Approved')}
                    disabled={transitioning}
                    className="px-3 py-1.5 text-xs font-bold rounded-lg bg-blue-600 text-white hover:bg-blue-700 transition"
                  >
                    Direct Approve
                  </button>
                  <button
                    onClick={() => handleStatusTransition('Archived')}
                    disabled={transitioning}
                    className="px-3 py-1.5 text-xs font-bold rounded-lg bg-slate-600 text-white hover:bg-slate-700 transition"
                  >
                    Archive
                  </button>
                </>
              )}

              {/* In Review -> Approved / Draft */}
              {campaign.status === 'In Review' && (
                <>
                  <button
                    onClick={() => handleStatusTransition('Approved')}
                    disabled={transitioning}
                    className="px-3 py-1.5 text-xs font-bold rounded-lg bg-emerald-600 text-white hover:bg-emerald-700 transition"
                  >
                    Approve Campaign
                  </button>
                  <button
                    onClick={() => handleStatusTransition('Draft')}
                    disabled={transitioning}
                    className="px-3 py-1.5 text-xs font-bold rounded-lg bg-slate-200 text-slate-700 hover:bg-slate-300 transition"
                  >
                    Return to Draft
                  </button>
                </>
              )}

              {/* Approved -> Scheduled / Draft */}
              {campaign.status === 'Approved' && (
                <>
                  <button
                    onClick={() => handleStatusTransition('Scheduled')}
                    disabled={transitioning}
                    className="px-3 py-1.5 text-xs font-bold rounded-lg bg-emerald-600 text-white hover:bg-emerald-700 transition"
                  >
                    Schedule Broadcast
                  </button>
                  <button
                    onClick={() => handleStatusTransition('Draft')}
                    disabled={transitioning}
                    className="px-3 py-1.5 text-xs font-bold rounded-lg bg-slate-200 text-slate-700 hover:bg-slate-300 transition"
                  >
                    Revert to Draft
                  </button>
                </>
              )}

              {/* Scheduled -> Draft */}
              {campaign.status === 'Scheduled' && (
                <button
                  onClick={() => handleStatusTransition('Draft')}
                  disabled={transitioning}
                  className="px-3 py-1.5 text-xs font-bold rounded-lg bg-slate-200 text-slate-700 hover:bg-slate-300 transition"
                >
                  Cancel / Revert to Draft
                </button>
              )}

              {/* Archived: Terminal */}
              {campaign.status === 'Archived' && (
                <span className="text-xs text-slate-400 italic">
                  Archived campaigns are terminal and cannot be transitioned.
                </span>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Two-Column Detail Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Left Column: Reach & Segments & Schedule */}
        <div className="lg:col-span-1 space-y-6">
          
          {/* Audience Reach Card */}
          <div className="bg-white rounded-2xl p-5 border border-slate-200 shadow-sm space-y-4">
            <div className="flex items-center gap-2 text-slate-900 font-bold text-sm">
              <Users className="w-4 h-4 text-brand-600" />
              Audience Reach Statistics
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="bg-slate-50 p-3 rounded-xl border border-slate-100 text-center space-y-0.5">
                <span className="text-2xl font-black text-slate-900">
                  {campaign.total_target_audience ?? 0}
                </span>
                <span className="text-[10px] text-slate-500 font-semibold uppercase tracking-wider block">
                  Total Target
                </span>
              </div>

              <div className="bg-emerald-50 p-3 rounded-xl border border-emerald-100 text-center space-y-0.5">
                <span className="text-2xl font-black text-emerald-700">
                  {campaign.confirmed_consent_audience ?? 0}
                </span>
                <span className="text-[10px] text-emerald-800 font-semibold uppercase tracking-wider block">
                  Confirmed Opt-In
                </span>
              </div>
            </div>

            {/* Tri-state consent notice */}
            <div className="p-3 bg-amber-50 rounded-xl border border-amber-200 text-amber-900 text-[11px] leading-relaxed">
              <strong>Tri-State Consent Law:</strong> Only recipients with verified confirmed opt-in consent (<code>consent_status: true</code>) receive broadcasts. Unconfirmed (null) or revoked (false) profiles are excluded.
            </div>
          </div>

          {/* Attached Segments */}
          <div className="bg-white rounded-2xl p-5 border border-slate-200 shadow-sm space-y-3">
            <div className="flex items-center justify-between text-slate-900 font-bold text-sm">
              <span className="flex items-center gap-2">
                <Layers className="w-4 h-4 text-amber-500" /> Attached Segments
              </span>
              <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-slate-100 text-slate-700">
                {campaign.segments?.length || 0}
              </span>
            </div>

            {(!campaign.segments || campaign.segments.length === 0) ? (
              <p className="text-xs text-slate-400 italic">No audience segments attached.</p>
            ) : (
              <div className="space-y-2">
                {campaign.segments.map((s) => (
                  <div key={s.id} className="p-2.5 rounded-xl bg-slate-50 border border-slate-100 text-xs space-y-0.5">
                    <p className="font-bold text-slate-800">{s.name}</p>
                    {s.description && <p className="text-[11px] text-slate-500">{s.description}</p>}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Channels & Timing */}
          <div className="bg-white rounded-2xl p-5 border border-slate-200 shadow-sm space-y-3">
            <div className="text-slate-900 font-bold text-sm flex items-center gap-2">
              <Calendar className="w-4 h-4 text-indigo-500" /> Configuration & Schedule
            </div>

            <div className="space-y-2 text-xs">
              <div>
                <span className="text-slate-400 block text-[11px]">Selected Channels:</span>
                <span className="font-bold text-slate-800">{campaign.channels?.join(', ')}</span>
              </div>
              <div>
                <span className="text-slate-400 block text-[11px]">Planned Start:</span>
                <span className="font-medium text-slate-800">
                  {campaign.start_date ? new Date(campaign.start_date).toLocaleString() : 'Unscheduled'}
                </span>
              </div>
              <div>
                <span className="text-slate-400 block text-[11px]">Planned End:</span>
                <span className="font-medium text-slate-800">
                  {campaign.end_date ? new Date(campaign.end_date).toLocaleString() : 'Open-ended'}
                </span>
              </div>
              <div>
                <span className="text-slate-400 block text-[11px]">Creator:</span>
                <span className="font-medium text-slate-800">
                  {campaign.creator_name || `User #${campaign.created_by}`}
                </span>
              </div>
            </div>
          </div>

        </div>

        {/* Right Column: Template & Simulated Preview */}
        <div className="lg:col-span-2 space-y-6">
          
          {/* Linked Template Card */}
          <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm space-y-3">
            <div className="flex items-center justify-between text-slate-900 font-bold text-sm">
              <span className="flex items-center gap-2">
                <FileText className="w-4 h-4 text-brand-600" /> Linked Template
              </span>
              {campaign.template_id && (
                <span className="text-xs font-mono text-slate-400">Template #{campaign.template_id}</span>
              )}
            </div>

            {!campaign.template_title ? (
              <div className="p-4 bg-amber-50 rounded-xl border border-amber-200 text-xs text-amber-800">
                No template is linked to this campaign. Transitioning to 'In Review' or 'Approved' requires a linked template.
              </div>
            ) : (
              <div className="space-y-2">
                <h3 className="text-base font-bold text-slate-900">{campaign.template_title}</h3>
                <div className="p-3.5 bg-slate-50 rounded-xl border border-slate-200 font-mono text-xs text-slate-700 whitespace-pre-line leading-relaxed">
                  {campaign.template_body}
                </div>
              </div>
            )}
          </div>

          {/* Simulated Multi-Channel Previews */}
          <div className="bg-slate-900 rounded-2xl p-6 text-white shadow-xl space-y-4">
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-brand-400" />
                <span className="text-xs font-bold uppercase tracking-wider text-slate-300">
                  Simulated Content Preview
                </span>
              </div>

              <div className="flex items-center gap-1 bg-slate-800 p-1 rounded-xl">
                {campaign.channels?.map((ch) => (
                  <button
                    key={ch}
                    type="button"
                    onClick={() => setActiveChannelTab(ch)}
                    className={`px-3 py-1 rounded-lg text-xs font-bold transition ${
                      activeChannelTab === ch
                        ? 'bg-brand-600 text-white shadow-xs'
                        : 'text-slate-400 hover:text-white'
                    }`}
                  >
                    {ch}
                  </button>
                ))}
              </div>
            </div>

            {/* Preview Payload Output */}
            {previewData && previewData.channel_previews && previewData.channel_previews[activeChannelTab] ? (
              <div className="space-y-3">
                {/* Channel Details */}
                <div className="flex items-center gap-3 text-xs text-slate-400 bg-slate-800/60 px-3.5 py-2 rounded-xl flex-wrap">
                  {activeChannelTab === 'Email' && (
                    <>
                      <span>Format: <strong className="text-white">HTML / Multipart</strong></span>
                      <span>•</span>
                      <span>Word Count: <strong className="text-white">{previewData.channel_previews.Email?.metrics?.word_count} words</strong></span>
                    </>
                  )}
                  {activeChannelTab === 'SMS' && (
                    <>
                      <span>Characters: <strong className="text-white">{previewData.channel_previews.SMS?.metrics?.character_count}</strong></span>
                      <span>•</span>
                      <span>
                        Segments: <strong className="text-emerald-400">{previewData.channel_previews.SMS?.metrics?.segment_count} part(s)</strong>
                      </span>
                    </>
                  )}
                  {activeChannelTab === 'WhatsApp' && (
                    <>
                      <span>Type: <strong className="text-white">Interactive Template</strong></span>
                      <span>•</span>
                      <span>Header: <strong className="text-white">{campaign.name}</strong></span>
                    </>
                  )}
                  {activeChannelTab === 'Voice' && (
                    <>
                      <span>Pacing: <strong className="text-white">130 WPM</strong></span>
                      <span>•</span>
                      <span>
                        Duration: <strong className="text-emerald-400">~{previewData.channel_previews.Voice?.metrics?.estimated_duration_seconds}s</strong>
                      </span>
                    </>
                  )}
                </div>

                <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 text-slate-200 text-sm leading-relaxed whitespace-pre-line font-mono">
                  {previewData.channel_previews[activeChannelTab]?.title_or_subject && (
                    <div className="border-b border-slate-800 pb-2 mb-2 text-xs text-slate-400 font-sans">
                      Subject: <strong className="text-white">{previewData.channel_previews[activeChannelTab]?.title_or_subject}</strong>
                    </div>
                  )}
                  {previewData.channel_previews[activeChannelTab]?.rendered_body || previewData.rendered_content}
                </div>

                <p className="text-[11px] text-slate-400 italic">
                  Simulated with sample citizen: {previewData.sample_recipient?.name} ({previewData.sample_recipient?.city}, {previewData.sample_recipient?.state}). No actual dispatch executed.
                </p>
              </div>
            ) : (
              <div className="p-6 text-center text-xs text-slate-400">
                No preview data available for {activeChannelTab}. Attach a template to generate simulated previews.
              </div>
            )}
          </div>

        </div>

      </div>

      {/* Delete Modal */}
      <CampaignDeleteModal
        isOpen={deleteModalOpen}
        onClose={() => setDeleteModalOpen(false)}
        onSuccess={(msg) => {
          navigate('/campaigns', { state: { message: msg } });
        }}
        campaign={campaign}
      />

    </div>
  );
}

