import React, { useState, useEffect } from 'react';
import { useNavigate, useParams, Link } from 'react-router-dom';
import {
  Megaphone,
  Layers,
  Calendar,
  FileText,
  ArrowRight,
  ArrowLeft,
  CheckCircle2,
  AlertCircle,
  Clock,
  Send,
  Users,
  ShieldCheck,
  Smartphone,
  Mail,
  MessageCircle,
  PhoneCall,
  Sparkles,
  Info,
  Check
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import {
  getCampaignMeta,
  getCampaign,
  createCampaign,
  updateCampaign,
  previewCampaign,
  previewCampaignCustom
} from '../../services/campaignService';
import { listSegments } from '../../services/segmentService';
import { listTemplates } from '../../services/templateService';

const CHANNELS = [
  { id: 'Email', label: 'Email', icon: Mail, desc: 'Official formatted bulletins and advisories' },
  { id: 'SMS', label: 'SMS', icon: Smartphone, desc: 'High-urgency GSM text alerts' },
  { id: 'WhatsApp', label: 'WhatsApp', icon: MessageCircle, desc: 'Rich media interactive messaging' },
  { id: 'Voice', label: 'Voice', icon: PhoneCall, desc: 'Automated citizen phone broadcasts' },
];

const CAMPAIGN_TYPES = [
  'Awareness',
  'Emergency Alert',
  'Educational',
  'Organizational Announcement',
];

const PRIORITIES = [
  { id: 'Low', label: 'Low', color: 'border-slate-300 text-slate-700 bg-slate-50' },
  { id: 'Medium', label: 'Medium', color: 'border-amber-300 text-amber-700 bg-amber-50' },
  { id: 'High', label: 'High', color: 'border-rose-300 text-rose-700 bg-rose-50' },
];

export default function CampaignWizardPage() {
  const navigate = useNavigate();
  const { id: editCampaignId } = useParams();
  const isEditing = Boolean(editCampaignId);
  const { user, isAdmin, isCampaignManager } = useAuth();
  const canEdit = isAdmin || isCampaignManager;

  const [currentStep, setCurrentStep] = useState(1);
  const [loading, setLoading] = useState(isEditing);
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState('');

  // Loaded Options
  const [availableSegments, setAvailableSegments] = useState([]);
  const [availableTemplates, setAvailableTemplates] = useState([]);

  // Form State
  const [formData, setFormData] = useState({
    name: '',
    campaign_type: 'Awareness',
    objective: '',
    priority: 'Medium',
    channels: ['Email'],
    segment_ids: [],
    template_id: null,
    start_date: '',
    end_date: '',
  });

  // Preview state in Step 4
  const [selectedChannelTab, setSelectedChannelTab] = useState('Email');
  const [previewData, setPreviewData] = useState(null);
  const [previewLoading, setPreviewLoading] = useState(false);

  // Load available segments and templates
  useEffect(() => {
    listSegments({ page_size: 100 })
      .then((res) => setAvailableSegments(res.items || []))
      .catch(() => {});

    listTemplates({ page_size: 100 })
      .then((res) => setAvailableTemplates(res.items || []))
      .catch(() => {});
  }, []);

  // Load existing campaign if in edit mode
  useEffect(() => {
    if (isEditing) {
      setLoading(true);
      getCampaign(editCampaignId)
        .then((camp) => {
          // Check ownership
          if (!isAdmin && camp.created_by !== user?.id) {
            setFormError('You do not have permission to edit campaigns authored by other managers.');
          }
          if (camp.status === 'Approved' || camp.status === 'Scheduled' || camp.status === 'Archived') {
            setFormError(`Cannot edit campaign in '${camp.status}' status. Move it back to Draft first.`);
          }

          setFormData({
            name: camp.name || '',
            campaign_type: camp.campaign_type || 'Awareness',
            objective: camp.objective || '',
            priority: camp.priority || 'Medium',
            channels: camp.channels && camp.channels.length > 0 ? camp.channels : ['Email'],
            segment_ids: (camp.segments || []).map((s) => s.id),
            template_id: camp.template_id || null,
            start_date: camp.start_date ? camp.start_date.substring(0, 16) : '',
            end_date: camp.end_date ? camp.end_date.substring(0, 16) : '',
          });
        })
        .catch((err) => {
          setFormError(err.response?.data?.detail || 'Failed to load campaign.');
        })
        .finally(() => setLoading(false));
    }
  }, [editCampaignId, isEditing, isAdmin, user?.id]);

  // Sync active channel tab when channels change
  useEffect(() => {
    if (formData.channels.length > 0 && !formData.channels.includes(selectedChannelTab)) {
      setSelectedChannelTab(formData.channels[0]);
    }
  }, [formData.channels, selectedChannelTab]);

  // Client-side simulated preview renderer for wizard when template is picked
  useEffect(() => {
    if (currentStep === 4 && formData.template_id) {
      const selectedTmpl = availableTemplates.find((t) => t.id === Number(formData.template_id));
      if (selectedTmpl) {
        const sampleRecipient = {
          name: 'Aarav Sharma',
          city: 'New Delhi',
          state: 'Delhi',
          email: 'aarav.sharma@example.gov.in',
          phone: '+919876543210',
          preferred_language: 'en',
          occupation: 'Civil Engineer',
          organization_department: 'Public Health Department',
        };

        let rendered = selectedTmpl.body;
        Object.entries(sampleRecipient).forEach(([k, v]) => {
          rendered = rendered.split(`{${k}}`).join(v);
        });

        const wordCount = rendered.split(/\s+/).filter(Boolean).length;
        const charCount = rendered.length;
        const smsSegments = charCount <= 160 ? 1 : Math.ceil(charCount / 153);
        const voiceDuration = Math.max(5, Math.round((wordCount / 130) * 60));

        setPreviewData({
          title: selectedTmpl.title,
          rendered,
          sampleRecipient,
          metrics: {
            wordCount,
            charCount,
            smsSegments,
            voiceDuration,
          },
        });
      }
    }
  }, [currentStep, formData.template_id, availableTemplates]);

  // Validation per step
  const validateStep = (step) => {
    setFormError('');
    if (step === 1) {
      if (!formData.name.trim() || formData.name.trim().length < 2) {
        setFormError('Campaign name must be at least 2 characters long.');
        return false;
      }
      return true;
    }
    if (step === 2) {
      // Segments can be optional during initial draft, but warn or require
      return true;
    }
    if (step === 3) {
      if (!formData.channels || formData.channels.length === 0) {
        setFormError('At least one communication channel must be selected.');
        return false;
      }
      if (formData.start_date && formData.end_date) {
        if (new Date(formData.end_date) < new Date(formData.start_date)) {
          setFormError('Planned end date must be after or equal to planned start date.');
          return false;
        }
      }
      return true;
    }
    if (step === 4) {
      return true;
    }
    return true;
  };

  const handleNext = () => {
    if (validateStep(currentStep)) {
      setCurrentStep((s) => Math.min(4, s + 1));
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }
  };

  const handleBack = () => {
    setFormError('');
    setCurrentStep((s) => Math.max(1, s - 1));
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const toggleChannel = (channelId) => {
    setFormData((prev) => {
      const exists = prev.channels.includes(channelId);
      const nextChannels = exists
        ? prev.channels.filter((c) => c !== channelId)
        : [...prev.channels, channelId];
      return { ...prev, channels: nextChannels };
    });
    if (formError) setFormError('');
  };

  const toggleSegment = (segmentId) => {
    setFormData((prev) => {
      const exists = prev.segment_ids.includes(segmentId);
      const nextSegments = exists
        ? prev.segment_ids.filter((id) => id !== segmentId)
        : [...prev.segment_ids, segmentId];
      return { ...prev, segment_ids: nextSegments };
    });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!validateStep(1) || !validateStep(3)) {
      return;
    }

    setSubmitting(true);
    setFormError('');

    try {
      const payload = {
        name: formData.name.trim(),
        campaign_type: formData.campaign_type,
        objective: formData.objective.trim() || null,
        priority: formData.priority,
        channels: formData.channels,
        segment_ids: formData.segment_ids,
        template_id: formData.template_id ? Number(formData.template_id) : null,
        start_date: formData.start_date ? new Date(formData.start_date).toISOString() : null,
        end_date: formData.end_date ? new Date(formData.end_date).toISOString() : null,
      };

      let result;
      if (isEditing) {
        result = await updateCampaign(editCampaignId, payload);
      } else {
        result = await createCampaign(payload);
      }

      navigate(`/campaigns/${result.id}`, {
        state: { message: isEditing ? 'Campaign updated successfully.' : 'Campaign created successfully in Draft status.' },
      });
    } catch (err) {
      const detail = err.response?.data?.detail;
      if (Array.isArray(detail)) {
        setFormError(detail.map((d) => d.msg || `${d.loc?.join('.')}: ${d.type}`).join(', '));
      } else if (typeof detail === 'string') {
        setFormError(detail);
      } else {
        setFormError(err.message || 'Failed to save campaign.');
      }
    } finally {
      setSubmitting(false);
    }
  };

  const stepLabels = [
    { num: 1, title: 'Basics', desc: 'Campaign info & priority' },
    { num: 2, title: 'Audience Targeting', desc: 'Segments & reach' },
    { num: 3, title: 'Channels & Schedule', desc: 'Delivery channels' },
    { num: 4, title: 'Template & Preview', desc: 'Message content' },
  ];

  if (loading) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-20 text-center space-y-3">
        <Clock className="w-8 h-8 text-brand-600 animate-spin mx-auto" />
        <p className="text-sm font-medium text-slate-500">Loading campaign configuration...</p>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      
      {/* Header Breadcrumb */}
      <div className="flex items-center justify-between">
        <Link
          to="/campaigns"
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-500 hover:text-brand-600 transition"
        >
          <ArrowLeft className="w-4 h-4" /> Back to Campaigns Directory
        </Link>
        <span className="text-xs font-medium text-slate-400">
          Step {currentStep} of 4
        </span>
      </div>

      {/* Main Card Container */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
        
        {/* Step Progress Stepper Bar */}
        <div className="border-b border-slate-100 bg-slate-50/50 p-4 sm:p-6">
          <div className="flex items-center justify-between">
            {stepLabels.map((s, idx) => {
              const isPassed = currentStep > s.num;
              const isCurrent = currentStep === s.num;
              return (
                <div key={s.num} className="flex items-center flex-1 last:flex-initial">
                  <div className="flex items-center gap-2.5">
                    <div
                      className={`w-8 h-8 rounded-xl flex items-center justify-center font-bold text-xs transition ${
                        isPassed
                          ? 'bg-emerald-600 text-white'
                          : isCurrent
                          ? 'bg-brand-600 text-white shadow-md shadow-brand-500/25 ring-4 ring-brand-100'
                          : 'bg-slate-200 text-slate-600'
                      }`}
                    >
                      {isPassed ? <Check className="w-4 h-4 stroke-[3]" /> : s.num}
                    </div>
                    <div className="hidden sm:block text-left">
                      <p className={`text-xs font-bold leading-tight ${isCurrent ? 'text-slate-900' : 'text-slate-500'}`}>
                        {s.title}
                      </p>
                      <p className="text-[10px] text-slate-400 leading-tight">{s.desc}</p>
                    </div>
                  </div>
                  {idx < stepLabels.length - 1 && (
                    <div
                      className={`flex-1 h-0.5 mx-3 sm:mx-4 transition ${
                        currentStep > s.num ? 'bg-emerald-500' : 'bg-slate-200'
                      }`}
                    />
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* Form Container */}
        <form onSubmit={handleSubmit} className="p-6 sm:p-8 space-y-6">
          
          {/* Top Form Error Alert */}
          {formError && (
            <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-xs flex items-start gap-3">
              <AlertCircle className="w-5 h-5 text-rose-500 flex-shrink-0 mt-0.5" />
              <div className="space-y-0.5">
                <p className="font-bold">Validation Notice</p>
                <p>{formError}</p>
              </div>
            </div>
          )}

          {/* =========================================================================
              STEP 1: CAMPAIGN BASICS
             ========================================================================= */}
          {currentStep === 1 && (
            <div className="space-y-5 animate-fade-in">
              <div className="space-y-1">
                <h2 className="text-lg font-bold text-slate-900">Campaign Basics & Priority</h2>
                <p className="text-xs text-slate-500">
                  Establish the public identity, operational scope, and priority of this communication broadcast.
                </p>
              </div>

              {/* Campaign Name */}
              <div className="space-y-1.5">
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider">
                  Campaign Title *
                </label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  placeholder="e.g. National Pulse Polio Immunization Drive 2026"
                  className="w-full px-3.5 py-2.5 bg-white border border-slate-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-brand-500 transition"
                  required
                />
              </div>

              {/* Type and Priority Grid */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider">
                    Campaign Classification *
                  </label>
                  <select
                    value={formData.campaign_type}
                    onChange={(e) => setFormData({ ...formData, campaign_type: e.target.value })}
                    className="w-full px-3.5 py-2.5 bg-white border border-slate-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-brand-500 transition"
                  >
                    {CAMPAIGN_TYPES.map((t) => (
                      <option key={t} value={t}>
                        {t}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="space-y-1.5">
                  <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider">
                    Priority Urgency Level *
                  </label>
                  <div className="grid grid-cols-3 gap-2">
                    {PRIORITIES.map((p) => {
                      const isSelected = formData.priority === p.id;
                      return (
                        <button
                          key={p.id}
                          type="button"
                          onClick={() => setFormData({ ...formData, priority: p.id })}
                          className={`py-2 px-3 text-xs font-bold rounded-xl border text-center transition ${
                            isSelected
                              ? `${p.color} ring-2 ring-brand-500 shadow-2xs`
                              : 'bg-white border-slate-200 text-slate-600 hover:bg-slate-50'
                          }`}
                        >
                          {p.label}
                        </button>
                      );
                    })}
                  </div>
                </div>
              </div>

              {/* Campaign Objective */}
              <div className="space-y-1.5">
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider">
                  Operational Objective (Optional)
                </label>
                <textarea
                  rows={3}
                  value={formData.objective}
                  onChange={(e) => setFormData({ ...formData, objective: e.target.value })}
                  placeholder="Outline target outcomes, target demographics, or civic department coordination notes..."
                  className="w-full px-3.5 py-2.5 bg-white border border-slate-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-brand-500 transition"
                />
              </div>
            </div>
          )}

          {/* =========================================================================
              STEP 2: AUDIENCE TARGETING
             ========================================================================= */}
          {currentStep === 2 && (
            <div className="space-y-5 animate-fade-in">
              <div className="space-y-1">
                <h2 className="text-lg font-bold text-slate-900">Audience Segmentation & Reach</h2>
                <p className="text-xs text-slate-500">
                  Select one or more saved audience segments to define the target cohort. Overlapping recipients are deduplicated automatically.
                </p>
              </div>

              {/* Confirmed Consent Guidance Banner */}
              <div className="p-4 rounded-xl bg-blue-50/70 border border-blue-200 text-blue-900 text-xs flex items-start gap-3">
                <ShieldCheck className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" />
                <div className="space-y-1">
                  <p className="font-bold">Consent Compliance Policy</p>
                  <p className="text-blue-800 leading-relaxed">
                    Segment membership defines matching recipients across civic criteria. However, <strong>segment membership does not authorize message dispatch</strong>. Only citizens with verified, confirmed opt-in consent (<code>consent_status: true</code>) are eligible for multi-channel broadcasts.
                  </p>
                </div>
              </div>

              {/* Segments Selection List */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider">
                    Select Target Segments ({formData.segment_ids.length} selected)
                  </label>
                  <Link
                    to="/segments"
                    target="_blank"
                    className="text-xs text-brand-600 hover:underline font-medium inline-flex items-center gap-1"
                  >
                    Open Rule Builder <ArrowRight className="w-3 h-3" />
                  </Link>
                </div>

                {availableSegments.length === 0 ? (
                  <div className="p-6 text-center bg-slate-50 rounded-xl border border-dashed border-slate-300 space-y-2">
                    <Layers className="w-6 h-6 text-slate-400 mx-auto" />
                    <p className="text-xs text-slate-600">No audience segments found in library.</p>
                    <Link
                      to="/segments"
                      target="_blank"
                      className="inline-block text-xs font-semibold text-brand-600 hover:underline"
                    >
                      Create an Audience Segment in Task 5
                    </Link>
                  </div>
                ) : (
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 max-h-72 overflow-y-auto p-1">
                    {availableSegments.map((seg) => {
                      const isSelected = formData.segment_ids.includes(seg.id);
                      return (
                        <div
                          key={seg.id}
                          onClick={() => toggleSegment(seg.id)}
                          className={`p-3.5 rounded-xl border cursor-pointer transition text-left flex items-start gap-3 select-none ${
                            isSelected
                              ? 'bg-brand-50/70 border-brand-400 ring-2 ring-brand-500/20'
                              : 'bg-white border-slate-200 hover:border-slate-300'
                          }`}
                        >
                          <input
                            type="checkbox"
                            checked={isSelected}
                            onChange={() => {}} // handled by div click
                            className="mt-0.5 rounded text-brand-600 focus:ring-brand-500"
                          />
                          <div className="space-y-1 flex-1">
                            <div className="flex items-center justify-between">
                              <span className="text-xs font-bold text-slate-900">{seg.name}</span>
                              <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-slate-100 text-slate-600">
                                #{seg.id}
                              </span>
                            </div>
                            {seg.description && (
                              <p className="text-[11px] text-slate-500 line-clamp-1">{seg.description}</p>
                            )}
                            {seg.audience_count !== undefined && (
                              <p className="text-[10px] text-emerald-700 font-medium">
                                ~{seg.audience_count} matching recipients
                              </p>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* =========================================================================
              STEP 3: CHANNELS & SCHEDULING
             ========================================================================= */}
          {currentStep === 3 && (
            <div className="space-y-5 animate-fade-in">
              <div className="space-y-1">
                <h2 className="text-lg font-bold text-slate-900">Communication Channels & Schedule</h2>
                <p className="text-xs text-slate-500">
                  Select delivery channels and optionally configure planned campaign timing windows.
                </p>
              </div>

              {/* Channels Selector */}
              <div className="space-y-2">
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider">
                  Distribution Channels * (Select at least 1)
                </label>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {CHANNELS.map((ch) => {
                    const isSelected = formData.channels.includes(ch.id);
                    const Icon = ch.icon;
                    return (
                      <div
                        key={ch.id}
                        onClick={() => toggleChannel(ch.id)}
                        className={`p-4 rounded-xl border cursor-pointer transition flex items-start gap-3 select-none ${
                          isSelected
                            ? 'bg-brand-50 border-brand-500 ring-2 ring-brand-500/20'
                            : 'bg-white border-slate-200 hover:border-slate-300'
                        }`}
                      >
                        <div
                          className={`w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0 ${
                            isSelected ? 'bg-brand-600 text-white' : 'bg-slate-100 text-slate-500'
                          }`}
                        >
                          <Icon className="w-5 h-5" />
                        </div>
                        <div className="space-y-0.5">
                          <span className="text-xs font-bold text-slate-900">{ch.label}</span>
                          <p className="text-[11px] text-slate-500 leading-snug">{ch.desc}</p>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Date Schedule Grid */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2">
                <div className="space-y-1.5">
                  <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider">
                    Planned Start Date & Time
                  </label>
                  <input
                    type="datetime-local"
                    value={formData.start_date}
                    onChange={(e) => setFormData({ ...formData, start_date: e.target.value })}
                    className="w-full px-3.5 py-2.5 bg-white border border-slate-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-brand-500 transition"
                  />
                  <p className="text-[11px] text-slate-400">
                    Required before advancing campaign status to Scheduled.
                  </p>
                </div>

                <div className="space-y-1.5">
                  <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider">
                    Planned End Date & Time (Optional)
                  </label>
                  <input
                    type="datetime-local"
                    value={formData.end_date}
                    onChange={(e) => setFormData({ ...formData, end_date: e.target.value })}
                    className="w-full px-3.5 py-2.5 bg-white border border-slate-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-brand-500 transition"
                  />
                  <p className="text-[11px] text-slate-400">
                    Must be greater than or equal to start date.
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* =========================================================================
              STEP 4: TEMPLATE & CONTENT PREVIEW
             ========================================================================= */}
          {currentStep === 4 && (
            <div className="space-y-5 animate-fade-in">
              <div className="space-y-1">
                <h2 className="text-lg font-bold text-slate-900">Template Selection & Multi-Channel Preview</h2>
                <p className="text-xs text-slate-500">
                  Link an approved communication template and simulate message rendering across each selected channel.
                </p>
              </div>

              {/* Template Picker */}
              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider">
                    Linked Communication Template *
                  </label>
                  <Link
                    to="/templates"
                    target="_blank"
                    className="text-xs text-brand-600 hover:underline font-medium inline-flex items-center gap-1"
                  >
                    Manage Templates <ArrowRight className="w-3 h-3" />
                  </Link>
                </div>

                <select
                  value={formData.template_id || ''}
                  onChange={(e) => setFormData({ ...formData, template_id: e.target.value || null })}
                  className="w-full px-3.5 py-2.5 bg-white border border-slate-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-brand-500 transition"
                >
                  <option value="">-- Choose a Template from Library --</option>
                  {availableTemplates.map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.title} ({t.category} • {t.language.toUpperCase()})
                    </option>
                  ))}
                </select>
              </div>

              {/* Multi-Channel Preview Window */}
              {previewData ? (
                <div className="bg-slate-900 rounded-2xl p-5 text-white shadow-lg space-y-4">
                  {/* Preview Header & Channel Switcher */}
                  <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 border-b border-slate-800 pb-3">
                    <div className="flex items-center gap-2">
                      <Sparkles className="w-4 h-4 text-brand-400" />
                      <span className="text-xs font-bold uppercase tracking-wider text-slate-300">
                        Live Simulation Preview
                      </span>
                    </div>

                    <div className="flex items-center gap-1 bg-slate-800 p-1 rounded-xl">
                      {formData.channels.map((ch) => (
                        <button
                          key={ch}
                          type="button"
                          onClick={() => setSelectedChannelTab(ch)}
                          className={`px-3 py-1 rounded-lg text-xs font-bold transition ${
                            selectedChannelTab === ch
                              ? 'bg-brand-600 text-white shadow-xs'
                              : 'text-slate-400 hover:text-white'
                          }`}
                        >
                          {ch}
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Channel-Specific Render Screen */}
                  <div className="space-y-3">
                    {/* Channel Specific Metrics Bar */}
                    <div className="flex items-center gap-4 text-xs text-slate-400 bg-slate-800/60 px-3.5 py-2 rounded-xl">
                      {selectedChannelTab === 'Email' && (
                        <>
                          <span>Format: <strong className="text-white">HTML / Multipart</strong></span>
                          <span>•</span>
                          <span>Word Count: <strong className="text-white">{previewData.metrics.wordCount} words</strong></span>
                        </>
                      )}
                      {selectedChannelTab === 'SMS' && (
                        <>
                          <span>Characters: <strong className="text-white">{previewData.metrics.charCount}</strong></span>
                          <span>•</span>
                          <span>
                            GSM Segments: <strong className="text-emerald-400">{previewData.metrics.smsSegments} part(s)</strong>
                          </span>
                          <span>•</span>
                          <span className="text-[11px] text-slate-400">160 chars per segment</span>
                        </>
                      )}
                      {selectedChannelTab === 'WhatsApp' && (
                        <>
                          <span>Format: <strong className="text-white">Interactive HSM Bubble</strong></span>
                          <span>•</span>
                          <span>Header: <strong className="text-white">{formData.name}</strong></span>
                        </>
                      )}
                      {selectedChannelTab === 'Voice' && (
                        <>
                          <span>Pacing: <strong className="text-white">130 WPM</strong></span>
                          <span>•</span>
                          <span>
                            Estimated Duration: <strong className="text-emerald-400">~{previewData.metrics.voiceDuration}s</strong>
                          </span>
                        </>
                      )}
                    </div>

                    {/* Rendered Preview Bubble */}
                    <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 text-slate-200 text-sm leading-relaxed whitespace-pre-line font-mono">
                      {selectedChannelTab === 'Email' && (
                        <div className="border-b border-slate-800 pb-2 mb-2 text-xs text-slate-400 font-sans">
                          Subject: <strong className="text-white">[{formData.priority.toUpperCase()}] {formData.name} — {previewData.title}</strong>
                        </div>
                      )}
                      {previewData.rendered}
                    </div>

                    {/* Simulation recipient note */}
                    <p className="text-[11px] text-slate-400 italic">
                      Rendered using sample recipient profile: {previewData.sampleRecipient.name} ({previewData.sampleRecipient.city}, {previewData.sampleRecipient.state}).
                    </p>
                  </div>
                </div>
              ) : (
                <div className="p-6 text-center bg-slate-50 rounded-xl border border-dashed border-slate-300 text-xs text-slate-500">
                  Select a template above to generate channel-specific simulated message previews.
                </div>
              )}

              {/* Review Summary Box */}
              <div className="bg-slate-50 p-4 rounded-xl border border-slate-200 space-y-2 text-xs text-slate-600">
                <span className="font-bold text-slate-800 uppercase tracking-wider block">Campaign Configuration Summary:</span>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-1">
                  <div>
                    <span className="text-slate-400 block">Name:</span>
                    <strong className="text-slate-900">{formData.name || 'Untitled'}</strong>
                  </div>
                  <div>
                    <span className="text-slate-400 block">Type:</span>
                    <strong className="text-slate-900">{formData.campaign_type}</strong>
                  </div>
                  <div>
                    <span className="text-slate-400 block">Channels:</span>
                    <strong className="text-slate-900">{formData.channels.join(', ')}</strong>
                  </div>
                  <div>
                    <span className="text-slate-400 block">Segments:</span>
                    <strong className="text-slate-900">{formData.segment_ids.length} selected</strong>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Stepper Navigation Buttons */}
          <div className="pt-6 border-t border-slate-100 flex items-center justify-between">
            {currentStep > 1 ? (
              <button
                type="button"
                onClick={handleBack}
                disabled={submitting}
                className="inline-flex items-center gap-1.5 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-100 rounded-xl transition"
              >
                <ArrowLeft className="w-4 h-4" /> Back
              </button>
            ) : (
              <div />
            )}

            <div className="flex items-center gap-3">
              {currentStep < 4 ? (
                <button
                  type="button"
                  onClick={handleNext}
                  className="inline-flex items-center gap-1.5 px-6 py-2.5 text-sm font-semibold text-white bg-brand-600 hover:bg-brand-700 rounded-xl shadow-sm hover:shadow-brand-500/25 transition active:scale-[0.98]"
                >
                  Continue <ArrowRight className="w-4 h-4" />
                </button>
              ) : (
                <button
                  type="submit"
                  disabled={submitting || !canEdit}
                  className="inline-flex items-center gap-2 px-6 py-2.5 text-sm font-semibold text-white bg-emerald-600 hover:bg-emerald-700 rounded-xl shadow-sm hover:shadow-emerald-500/25 transition active:scale-[0.98] disabled:opacity-50"
                >
                  <Send className="w-4 h-4" />
                  {submitting ? 'Saving Campaign...' : isEditing ? 'Update Campaign' : 'Create Campaign in Draft'}
                </button>
              )}
            </div>
          </div>

        </form>

      </div>
    </div>
  );
}

