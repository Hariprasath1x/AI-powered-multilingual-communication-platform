import React, { useState, useEffect } from 'react';
import {
  X,
  Sparkles,
  CheckCircle2,
  AlertCircle,
  Loader2,
  RefreshCw,
  ChevronRight,
  ChevronLeft,
  Layers,
  Globe,
  Sliders,
  ShieldCheck,
  FileText,
  Check,
  AlertTriangle,
  RotateCcw,
  ExternalLink,
} from 'lucide-react';
import {
  runContentPipeline,
  getPipelineRun,
  resumePipelineRun,
} from '../../services/campaignService';
import { useNavigate } from 'react-router-dom';

const INDIAN_LANGUAGES = [
  { code: 'hi', name: 'Hindi', script: 'हिन्दी' },
  { code: 'ta', name: 'Tamil', script: 'தமிழ்' },
  { code: 'te', name: 'Telugu', script: 'తెలుగు' },
  { code: 'bn', name: 'Bengali', script: 'বাংলা' },
  { code: 'mr', name: 'Marathi', script: 'मराठी' },
  { code: 'kn', name: 'Kannada', script: 'ಕನ್ನಡ' },
  { code: 'gu', name: 'Gujarati', script: 'ગુજરાતી' },
  { code: 'ml', name: 'Malayalam', script: 'മലയാളം' },
  { code: 'pa', name: 'Punjabi', script: 'ਪੰਜਾਬੀ' },
  { code: 'ur', name: 'Urdu', script: 'اردو' },
];

const CHANNELS = ['SMS', 'Email', 'WhatsApp', 'Voice'];

const CATEGORIES = [
  'Disaster Preparedness',
  'Emergency Alert',
  'Healthcare',
  'Civic Services',
  'Education',
  'Environment',
  'Agriculture',
  'General Announcement',
];

const TONE_OPTIONS = [
  { id: 'Informative', label: 'Informative', desc: 'Clear, factual, objective guidance for civic notices' },
  { id: 'Friendly', label: 'Friendly', desc: 'Warm, approachable, conversational community updates' },
  { id: 'Urgent', label: 'Urgent', desc: 'Direct, rapid-action directives for critical alerts' },
  { id: 'Formal', label: 'Formal', desc: 'Authoritative, official governmental announcements' },
  { id: 'Empathetic', label: 'Empathetic', desc: 'Compassionate, reassuring support for vulnerable groups' },
];

const TONE_INSTRUCTIONS = [
  { id: 'friendlier', label: 'Friendlier & Reassuring' },
  { id: 'more_formal', label: 'More Formal & Official' },
  { id: 'more_urgent', label: 'More Urgent (Emergency Notice)' },
  { id: 'shorter', label: 'Concise / Shorter Length' },
  { id: 'empathetic_support', label: 'Empathetic Community Tone' },
];

const STAGE_DEFINITIONS = [
  { id: 'generate', name: 'Stage 1: Content Generation', desc: 'Synthesizes root brief copy tailored to selected delivery channels.' },
  { id: 'translate', name: 'Stage 2: Multilingual Translation', desc: 'Translates verified root content across targeted Indian languages.' },
  { id: 'personalize', name: 'Stage 3: Audience Personalization', desc: 'Produces demographic variants tailored to selected segment personas.' },
  { id: 'tone_optimize', name: 'Stage 4: Tone Optimization', desc: 'Calibrates tone and sentiment while strictly safeguarding factual anchors.' },
  { id: 'review', name: 'Stage 5: Quality Audit & Submission', desc: 'Evaluates dynamic compliance rules and routes to the editorial review queue.' },
];

export default function ContentPipelineWizardModal({
  isOpen,
  onClose,
  campaign,
  onPipelineComplete,
}) {
  const navigate = useNavigate();

  // Wizard Navigation: 1: Brief, 2: Targeting, 3: Tone & Review, 4: Live Execution, 5: Review & Artifacts
  const [step, setStep] = useState(1);

  // Form Configuration State
  const [topic, setTopic] = useState('');
  const [objective, setObjective] = useState('');
  const [category, setCategory] = useState('Disaster Preparedness');
  const [selectedChannels, setSelectedChannels] = useState(['SMS', 'Email']);
  const [sourceLanguage, setSourceLanguage] = useState('en');
  const [targetLanguages, setTargetLanguages] = useState(['hi', 'ta']);
  const [selectedSegmentIds, setSelectedSegmentIds] = useState([]);
  const [targetTone, setTargetTone] = useState('Informative');
  const [toneInstruction, setToneInstruction] = useState('friendlier');
  const [factsInput, setFactsInput] = useState('');
  const [constraintsInput, setConstraintsInput] = useState('');
  const [submitForReview, setSubmitForReview] = useState(true);

  // Pipeline Execution State
  const [executing, setExecuting] = useState(false);
  const [activeRun, setActiveRun] = useState(null);
  const [executionError, setExecutionError] = useState(null);
  const [resumeStage, setResumeStage] = useState('translate');

  // Prepopulate from campaign if available
  useEffect(() => {
    if (campaign && isOpen) {
      if (campaign.name && !topic) setTopic(campaign.name);
      if (campaign.objective && !objective) setObjective(campaign.objective);
      if (campaign.channels && campaign.channels.length > 0) {
        setSelectedChannels(campaign.channels);
      }
      if (campaign.segments && campaign.segments.length > 0) {
        setSelectedSegmentIds(campaign.segments.map((s) => s.id));
      }
      if (campaign.campaign_type === 'Emergency Alert') {
        setCategory('Emergency Alert');
        setTargetTone('Urgent');
      }
    }
  }, [campaign, isOpen, topic, objective]);

  if (!isOpen) return null;

  const handleChannelToggle = (ch) => {
    if (selectedChannels.includes(ch)) {
      if (selectedChannels.length > 1) {
        setSelectedChannels(selectedChannels.filter((c) => c !== ch));
      }
    } else {
      setSelectedChannels([...selectedChannels, ch]);
    }
  };

  const handleLanguageToggle = (langCode) => {
    if (targetLanguages.includes(langCode)) {
      setTargetLanguages(targetLanguages.filter((l) => l !== langCode));
    } else {
      setTargetLanguages([...targetLanguages, langCode]);
    }
  };

  const handleSelectAllLanguages = () => {
    if (targetLanguages.length === INDIAN_LANGUAGES.length) {
      setTargetLanguages([]);
    } else {
      setTargetLanguages(INDIAN_LANGUAGES.map((l) => l.code));
    }
  };

  const handleSegmentToggle = (segId) => {
    if (selectedSegmentIds.includes(segId)) {
      setSelectedSegmentIds(selectedSegmentIds.filter((id) => id !== segId));
    } else {
      setSelectedSegmentIds([...selectedSegmentIds, segId]);
    }
  };

  // Launch the 5-stage automated pipeline
  const handleStartPipeline = async () => {
    setExecuting(true);
    setExecutionError(null);
    setStep(4);

    const parsedFacts = factsInput
      .split('\n')
      .map((s) => s.trim())
      .filter((s) => s.length > 0);

    const parsedConstraints = constraintsInput
      .split('\n')
      .map((s) => s.trim())
      .filter((s) => s.length > 0);

    const payload = {
      topic: topic.trim() || campaign?.name || 'Public Awareness Initiative',
      objective: objective.trim() || campaign?.objective || 'Deliver timely, compliant civic awareness messaging.',
      category: category,
      channels: selectedChannels,
      source_language: sourceLanguage,
      target_languages: targetLanguages,
      segment_ids: selectedSegmentIds,
      target_tone: targetTone,
      tone_instruction: toneInstruction,
      facts: parsedFacts.length > 0 ? parsedFacts : undefined,
      constraints: parsedConstraints.length > 0 ? parsedConstraints : undefined,
      submit_for_review: submitForReview,
      idempotency_key: `pipe-client-${campaign?.id}-${Date.now()}`,
    };

    try {
      const response = await runContentPipeline(campaign.id, payload);
      setActiveRun(response);
      setExecuting(false);
      if (response.status === 'completed') {
        setStep(5);
        if (onPipelineComplete) onPipelineComplete(response);
      }
    } catch (err) {
      setExecuting(false);
      const detail = err.response?.data?.detail || err.message || 'Pipeline execution failed.';
      setExecutionError(detail);
      // Attempt to inspect existing run status if available
      if (err.response?.data?.run_id) {
        try {
          const runStatus = await getPipelineRun(campaign.id, err.response.data.run_id);
          setActiveRun(runStatus);
        } catch {
          // ignore
        }
      }
    }
  };

  // Resume a failed run
  const handleResumeRun = async () => {
    if (!activeRun?.id) return;
    setExecuting(true);
    setExecutionError(null);

    try {
      const response = await resumePipelineRun(campaign.id, activeRun.id, {
        resume_from_stage: resumeStage,
      });
      setActiveRun(response);
      setExecuting(false);
      if (response.status === 'completed') {
        setStep(5);
        if (onPipelineComplete) onPipelineComplete(response);
      }
    } catch (err) {
      setExecuting(false);
      setExecutionError(err.response?.data?.detail || err.message || 'Failed to resume pipeline.');
    }
  };

  // Helper to determine stage status in UI
  const getStageStatus = (stageId, index) => {
    if (!activeRun) {
      return executing && index === 0 ? 'running' : 'pending';
    }
    const outputs = activeRun.stage_outputs || {};
    if (outputs[stageId]?.status === 'completed') return 'completed';
    if (activeRun.current_stage === stageId && activeRun.status === 'in_progress') return 'running';
    if (activeRun.current_stage === stageId && activeRun.status === 'failed') return 'failed';
    if (index < activeRun.completed_stages) return 'completed';
    return 'pending';
  };

  const campaignSegments = campaign?.segments || [];

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl border border-slate-200 w-full max-w-4xl overflow-hidden flex flex-col max-h-[92vh] animate-in fade-in duration-200">
        
        {/* Modal Top Header */}
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-gradient-to-r from-slate-900 to-indigo-950 text-white">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-blue-500/20 border border-blue-400/30 flex items-center justify-center shadow-inner">
              <Sparkles className="w-5 h-5 text-blue-300" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base font-bold tracking-tight">AI Content Pipeline Orchestrator</h2>
                <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded-full bg-blue-500/30 text-blue-200 border border-blue-400/30 font-semibold">
                  Milestone 2 • Task 12
                </span>
              </div>
              <p className="text-xs text-slate-300">
                Campaign #{campaign?.id}: <strong className="text-white">{campaign?.name}</strong>
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            disabled={executing}
            className="p-1.5 rounded-lg text-slate-300 hover:text-white hover:bg-white/10 transition disabled:opacity-40"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Multi-Step Indicator Header */}
        <div className="px-6 py-3 bg-slate-50 border-b border-slate-200 flex items-center justify-between text-xs">
          <div className="flex items-center gap-1 sm:gap-4 overflow-x-auto">
            {[
              { num: 1, label: 'Brief & Channels' },
              { num: 2, label: 'Targeting & Languages' },
              { num: 3, label: 'Tone & Review Policy' },
              { num: 4, label: 'Execution Tracker' },
              { num: 5, label: 'Output Artifacts' },
            ].map((s) => (
              <div
                key={s.num}
                className={`flex items-center gap-1.5 whitespace-nowrap transition-colors ${
                  step === s.num
                    ? 'font-bold text-blue-700'
                    : step > s.num
                    ? 'font-medium text-emerald-700'
                    : 'text-slate-400'
                }`}
              >
                <div
                  className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-semibold ${
                    step === s.num
                      ? 'bg-blue-600 text-white shadow-2xs'
                      : step > s.num
                      ? 'bg-emerald-600 text-white'
                      : 'bg-slate-200 text-slate-600'
                  }`}
                >
                  {step > s.num ? <Check className="w-3.5 h-3.5" /> : s.num}
                </div>
                <span className="hidden md:inline">{s.label}</span>
                {s.num < 5 && <ChevronRight className="w-3.5 h-3.5 text-slate-300 mx-1 hidden sm:inline" />}
              </div>
            ))}
          </div>
          <span className="text-[11px] font-semibold text-slate-500">
            Step {step} of 5
          </span>
        </div>

        {/* Step Body Content */}
        <div className="p-6 overflow-y-auto flex-1 space-y-6">

          {/* STEP 1: Brief, Topic, Objective & Channels */}
          {step === 1 && (
            <div className="space-y-5 animate-in fade-in">
              <div className="border-l-4 border-blue-600 pl-3">
                <h3 className="text-sm font-bold text-slate-900">Configure Campaign Brief & Channels</h3>
                <p className="text-xs text-slate-500">
                  Establish the factual basis and communication directive for LLM synthesis.
                </p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-1">
                  <label className="text-xs font-semibold text-slate-700">Topic / Core Focus *</label>
                  <input
                    type="text"
                    value={topic}
                    onChange={(e) => setTopic(e.target.value)}
                    placeholder="e.g. Flood Preparedness & Emergency Relief 2026"
                    className="w-full text-xs px-3 py-2 rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>

                <div className="space-y-1">
                  <label className="text-xs font-semibold text-slate-700">Public Domain Category</label>
                  <select
                    value={category}
                    onChange={(e) => setCategory(e.target.value)}
                    className="w-full text-xs px-3 py-2 rounded-xl border border-slate-300 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    {CATEGORIES.map((c) => (
                      <option key={c} value={c}>{c}</option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="space-y-1">
                <label className="text-xs font-semibold text-slate-700">Communication Objective *</label>
                <textarea
                  value={objective}
                  onChange={(e) => setObjective(e.target.value)}
                  rows={2}
                  placeholder="e.g. Inform citizens of impending heavy rainfall, distribute emergency helpline numbers, and direct to municipal relief centers."
                  className="w-full text-xs px-3 py-2 rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div className="space-y-2">
                <label className="text-xs font-semibold text-slate-700">Delivery Channels (Multi-select)</label>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  {CHANNELS.map((ch) => {
                    const isChecked = selectedChannels.includes(ch);
                    return (
                      <div
                        key={ch}
                        onClick={() => handleChannelToggle(ch)}
                        className={`p-3 rounded-xl border cursor-pointer flex items-center justify-between transition ${
                          isChecked
                            ? 'bg-blue-50 border-blue-400 text-blue-900 shadow-2xs'
                            : 'bg-white border-slate-200 text-slate-600 hover:bg-slate-50'
                        }`}
                      >
                        <span className="text-xs font-bold">{ch}</span>
                        <div
                          className={`w-4 h-4 rounded flex items-center justify-center border text-[10px] ${
                            isChecked
                              ? 'bg-blue-600 border-blue-600 text-white'
                              : 'border-slate-300 bg-white'
                          }`}
                        >
                          {isChecked && <Check className="w-3 h-3" />}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              <div className="space-y-1">
                <label className="text-xs font-semibold text-slate-700 flex items-center justify-between">
                  <span>Verified Factual Anchors (Helplines, Shelters, Dates)</span>
                  <span className="text-[11px] font-normal text-slate-400">One per line — strictly preserved</span>
                </label>
                <textarea
                  value={factsInput}
                  onChange={(e) => setFactsInput(e.target.value)}
                  rows={3}
                  placeholder="Helpline 1077 is active 24x7&#10;Municipal Shelters open at City Hall&#10;Relief camp operates until November 25"
                  className="w-full text-xs px-3 py-2 rounded-xl border border-slate-300 font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div className="space-y-1">
                <label className="text-xs font-semibold text-slate-700">Formatting Constraints (Optional)</label>
                <input
                  type="text"
                  value={constraintsInput}
                  onChange={(e) => setConstraintsInput(e.target.value)}
                  placeholder="e.g. Keep SMS under 160 characters; Include helpline in first sentence"
                  className="w-full text-xs px-3 py-2 rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>
          )}

          {/* STEP 2: Target Indian Languages & Campaign Audience Segments */}
          {step === 2 && (
            <div className="space-y-6 animate-in fade-in">
              <div className="border-l-4 border-indigo-600 pl-3">
                <h3 className="text-sm font-bold text-slate-900">Multilingual & Demographic Targeting</h3>
                <p className="text-xs text-slate-500">
                  Select target Indian languages for Stage 2 and campaign segments for Stage 3 personalization.
                </p>
              </div>

              {/* Target Languages */}
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <label className="text-xs font-bold text-slate-800 flex items-center gap-1.5">
                    <Globe className="w-3.5 h-3.5 text-indigo-600" />
                    Target Indian Languages ({targetLanguages.length} selected)
                  </label>
                  <button
                    type="button"
                    onClick={handleSelectAllLanguages}
                    className="text-xs text-indigo-600 hover:text-indigo-800 font-semibold"
                  >
                    {targetLanguages.length === INDIAN_LANGUAGES.length ? 'Deselect All' : 'Select All'}
                  </button>
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-5 gap-2.5">
                  {INDIAN_LANGUAGES.map((lang) => {
                    const isSelected = targetLanguages.includes(lang.code);
                    return (
                      <div
                        key={lang.code}
                        onClick={() => handleLanguageToggle(lang.code)}
                        className={`p-2.5 rounded-xl border cursor-pointer flex flex-col justify-between transition ${
                          isSelected
                            ? 'bg-indigo-50 border-indigo-400 text-indigo-900 shadow-2xs'
                            : 'bg-white border-slate-200 text-slate-700 hover:bg-slate-50'
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-bold">{lang.name}</span>
                          <span className="text-[10px] uppercase font-mono px-1 rounded bg-slate-100 text-slate-600 font-semibold">
                            {lang.code}
                          </span>
                        </div>
                        <span className="text-[11px] text-slate-500 font-medium mt-1">
                          {lang.script}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Campaign Audience Segments */}
              <div className="space-y-3 pt-4 border-t border-slate-200">
                <div className="flex items-center justify-between">
                  <label className="text-xs font-bold text-slate-800 flex items-center gap-1.5">
                    <Layers className="w-3.5 h-3.5 text-amber-600" />
                    Audience Segments for Personalization ({selectedSegmentIds.length} selected)
                  </label>
                  <span className="text-[11px] text-slate-500">
                    Stage 3 generates personalized variants per selected segment
                  </span>
                </div>

                {campaignSegments.length === 0 ? (
                  <div className="p-4 rounded-xl bg-amber-50 border border-amber-200 text-xs text-amber-800">
                    No segments are directly linked to this campaign. Stage 3 will personalize for available organization demographic cohorts.
                  </div>
                ) : (
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    {campaignSegments.map((seg) => {
                      const isSelected = selectedSegmentIds.includes(seg.id);
                      return (
                        <div
                          key={seg.id}
                          onClick={() => handleSegmentToggle(seg.id)}
                          className={`p-3 rounded-xl border cursor-pointer flex items-center justify-between transition ${
                            isSelected
                              ? 'bg-amber-50 border-amber-400 text-amber-900 shadow-2xs'
                              : 'bg-white border-slate-200 text-slate-700 hover:bg-slate-50'
                          }`}
                        >
                          <div>
                            <p className="text-xs font-bold">{seg.name}</p>
                            {seg.description && (
                              <p className="text-[11px] text-slate-500 line-clamp-1">{seg.description}</p>
                            )}
                          </div>
                          <div
                            className={`w-4 h-4 rounded flex items-center justify-center border text-[10px] ${
                              isSelected
                                ? 'bg-amber-600 border-amber-600 text-white'
                                : 'border-slate-300 bg-white'
                            }`}
                          >
                            {isSelected && <Check className="w-3 h-3" />}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* STEP 3: Tone Optimization & Human Review Policy */}
          {step === 3 && (
            <div className="space-y-6 animate-in fade-in">
              <div className="border-l-4 border-emerald-600 pl-3">
                <h3 className="text-sm font-bold text-slate-900">Tone Optimization & Governance Policy</h3>
                <p className="text-xs text-slate-500">
                  Calibrate sentiment tone for Stage 4 and set human editorial review enforcement for Stage 5.
                </p>
              </div>

              {/* Tone Selection */}
              <div className="space-y-3">
                <label className="text-xs font-bold text-slate-800 flex items-center gap-1.5">
                  <Sliders className="w-3.5 h-3.5 text-emerald-600" />
                  Target Tone Calibration
                </label>

                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  {TONE_OPTIONS.map((t) => {
                    const isSelected = targetTone === t.id;
                    return (
                      <div
                        key={t.id}
                        onClick={() => setTargetTone(t.id)}
                        className={`p-3 rounded-xl border cursor-pointer transition ${
                          isSelected
                            ? 'bg-emerald-50 border-emerald-500 text-emerald-950 shadow-2xs'
                            : 'bg-white border-slate-200 text-slate-700 hover:bg-slate-50'
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-bold">{t.label}</span>
                          {isSelected && <Check className="w-3.5 h-3.5 text-emerald-600" />}
                        </div>
                        <p className="text-[11px] text-slate-500 mt-1 leading-snug">{t.desc}</p>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Tone Adjustment Instruction */}
              <div className="space-y-2">
                <label className="text-xs font-semibold text-slate-700">Quick Adjustment Code / Pacing</label>
                <div className="flex flex-wrap gap-2">
                  {TONE_INSTRUCTIONS.map((ins) => (
                    <button
                      key={ins.id}
                      type="button"
                      onClick={() => setToneInstruction(ins.id)}
                      className={`text-xs px-3 py-1.5 rounded-lg border font-medium transition ${
                        toneInstruction === ins.id
                          ? 'bg-slate-900 border-slate-900 text-white'
                          : 'bg-white border-slate-300 text-slate-700 hover:bg-slate-50'
                      }`}
                    >
                      {ins.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Review Policy Toggle */}
              <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 flex items-start gap-3">
                <input
                  type="checkbox"
                  id="submitReview"
                  checked={submitForReview}
                  onChange={(e) => setSubmitForReview(e.target.checked)}
                  className="mt-0.5 rounded text-blue-600 focus:ring-blue-500"
                />
                <label htmlFor="submitReview" className="cursor-pointer space-y-0.5 text-xs">
                  <span className="font-bold text-slate-900 flex items-center gap-1.5">
                    <ShieldCheck className="w-4 h-4 text-blue-600" />
                    Enforce Human-in-the-Loop Review Queue Transition
                  </span>
                  <p className="text-[11px] text-slate-500 leading-relaxed">
                    When checked, all generated assets and demographic variants undergo automated compliance quality assessment
                    and are transitioned to <strong>In Review</strong> status, ready for official editorial sign-off.
                  </p>
                </label>
              </div>
            </div>
          )}

          {/* STEP 4: Live Execution Tracker & Progress */}
          {step === 4 && (
            <div className="space-y-6 animate-in fade-in">
              <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                <div>
                  <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                    {executing ? (
                      <Loader2 className="w-4 h-4 text-blue-600 animate-spin" />
                    ) : executionError ? (
                      <AlertTriangle className="w-4 h-4 text-rose-600" />
                    ) : (
                      <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                    )}
                    {executing
                      ? 'Executing 5-Stage Content Pipeline...'
                      : executionError
                      ? 'Pipeline Interrupted with Partial Progress'
                      : 'Pipeline Execution Completed'}
                  </h3>
                  <p className="text-xs text-slate-500">
                    {activeRun ? `Run ID #${activeRun.id} • Progress: ${activeRun.progress_percent}%` : 'Initializing orchestrator...'}
                  </p>
                </div>

                {activeRun && (
                  <span
                    className={`text-xs font-mono font-bold px-2.5 py-0.5 rounded-full border ${
                      activeRun.status === 'completed'
                        ? 'bg-emerald-50 text-emerald-800 border-emerald-300'
                        : activeRun.status === 'failed'
                        ? 'bg-rose-50 text-rose-800 border-rose-300'
                        : 'bg-blue-50 text-blue-800 border-blue-300'
                    }`}
                  >
                    {activeRun.status.toUpperCase()}
                  </span>
                )}
              </div>

              {/* Progress Bar */}
              <div className="space-y-1.5">
                <div className="flex justify-between text-xs font-semibold text-slate-700">
                  <span>Overall Pipeline Completion</span>
                  <span>{activeRun ? activeRun.progress_percent : (executing ? 20 : 0)}%</span>
                </div>
                <div className="w-full bg-slate-100 rounded-full h-2.5 overflow-hidden border border-slate-200">
                  <div
                    className={`h-2.5 rounded-full transition-all duration-500 ${
                      executionError ? 'bg-rose-500' : 'bg-gradient-to-r from-blue-600 to-indigo-600'
                    }`}
                    style={{
                      width: `${activeRun ? activeRun.progress_percent : (executing ? 20 : 0)}%`,
                    }}
                  />
                </div>
              </div>

              {/* 5-Stage Card List */}
              <div className="space-y-3">
                {STAGE_DEFINITIONS.map((stg, idx) => {
                  const status = getStageStatus(stg.id, idx);
                  const stageOutput = activeRun?.stage_outputs?.[stg.id];

                  return (
                    <div
                      key={stg.id}
                      className={`p-3.5 rounded-xl border transition flex items-center justify-between ${
                        status === 'completed'
                          ? 'bg-emerald-50/60 border-emerald-200 text-slate-800'
                          : status === 'running'
                          ? 'bg-blue-50/70 border-blue-300 text-slate-900 shadow-2xs'
                          : status === 'failed'
                          ? 'bg-rose-50/80 border-rose-300 text-slate-900'
                          : 'bg-slate-50 border-slate-200 text-slate-400 opacity-75'
                      }`}
                    >
                      <div className="flex items-center gap-3">
                        <div
                          className={`w-7 h-7 rounded-lg flex items-center justify-center text-xs font-bold ${
                            status === 'completed'
                              ? 'bg-emerald-600 text-white'
                              : status === 'running'
                              ? 'bg-blue-600 text-white'
                              : status === 'failed'
                              ? 'bg-rose-600 text-white'
                              : 'bg-slate-200 text-slate-500'
                          }`}
                        >
                          {status === 'completed' ? (
                            <Check className="w-4 h-4" />
                          ) : status === 'running' ? (
                            <Loader2 className="w-4 h-4 animate-spin" />
                          ) : status === 'failed' ? (
                            <AlertCircle className="w-4 h-4" />
                          ) : (
                            idx + 1
                          )}
                        </div>

                        <div>
                          <p className="text-xs font-bold">{stg.name}</p>
                          <p className="text-[11px] text-slate-500 line-clamp-1">{stg.desc}</p>
                          {stageOutput?.summary && (
                            <p className="text-[11px] font-medium text-emerald-800 mt-0.5">
                              ✓ {stageOutput.summary}
                            </p>
                          )}
                        </div>
                      </div>

                      <div className="text-right flex-shrink-0">
                        {status === 'completed' && (
                          <span className="text-[11px] font-semibold text-emerald-700 bg-emerald-100 px-2 py-0.5 rounded-md">
                            {stageOutput?.item_count ? `${stageOutput.item_count} items` : 'Done'}
                          </span>
                        )}
                        {status === 'running' && (
                          <span className="text-[11px] font-semibold text-blue-700 bg-blue-100 px-2 py-0.5 rounded-md animate-pulse">
                            Processing...
                          </span>
                        )}
                        {status === 'failed' && (
                          <span className="text-[11px] font-semibold text-rose-700 bg-rose-100 px-2 py-0.5 rounded-md">
                            Interrupted
                          </span>
                        )}
                        {status === 'pending' && (
                          <span className="text-[11px] text-slate-400">Queued</span>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Error & Resume Recovery Box */}
              {executionError && (
                <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 space-y-3">
                  <div className="flex items-start gap-2.5 text-rose-800 text-xs">
                    <AlertCircle className="w-4 h-4 text-rose-600 flex-shrink-0 mt-0.5" />
                    <div>
                      <p className="font-bold">Pipeline Stage Interruption</p>
                      <p className="text-[11px] text-rose-700 mt-0.5 font-mono">{executionError}</p>
                    </div>
                  </div>

                  <div className="pt-2 border-t border-rose-200 flex flex-wrap items-center justify-between gap-3 text-xs">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-rose-900">Resume execution from:</span>
                      <select
                        value={resumeStage}
                        onChange={(e) => setResumeStage(e.target.value)}
                        className="text-xs px-2.5 py-1 rounded-lg border border-rose-300 bg-white text-slate-800"
                      >
                        <option value="translate">Stage 2: Translation</option>
                        <option value="personalize">Stage 3: Personalization</option>
                        <option value="tone_optimize">Stage 4: Tone Optimization</option>
                        <option value="review">Stage 5: Review & Submission</option>
                      </select>
                    </div>

                    <button
                      type="button"
                      onClick={handleResumeRun}
                      disabled={executing}
                      className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-rose-700 text-white font-semibold text-xs hover:bg-rose-800 transition shadow-2xs disabled:opacity-50"
                    >
                      {executing ? (
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      ) : (
                        <RotateCcw className="w-3.5 h-3.5" />
                      )}
                      Resume Pipeline
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* STEP 5: Artifacts Review & Hand-off */}
          {step === 5 && (
            <div className="space-y-6 animate-in fade-in">
              <div className="border-l-4 border-emerald-600 pl-3">
                <h3 className="text-sm font-bold text-slate-900">Pipeline Execution Succeeded</h3>
                <p className="text-xs text-slate-500">
                  All 5 stages completed successfully. Content assets and demographic variants have been audited and persisted.
                </p>
              </div>

              {/* Statistics Grid */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-center">
                <div className="p-3 bg-slate-50 rounded-xl border border-slate-200">
                  <span className="text-[11px] text-slate-500 block">Root Assets</span>
                  <span className="text-xl font-bold text-slate-900">
                    {activeRun?.stage_outputs?.generate?.item_count || selectedChannels.length}
                  </span>
                </div>
                <div className="p-3 bg-slate-50 rounded-xl border border-slate-200">
                  <span className="text-[11px] text-slate-500 block">Translations</span>
                  <span className="text-xl font-bold text-indigo-700">
                    {activeRun?.stage_outputs?.translate?.item_count || (selectedChannels.length * targetLanguages.length)}
                  </span>
                </div>
                <div className="p-3 bg-slate-50 rounded-xl border border-slate-200">
                  <span className="text-[11px] text-slate-500 block">Personalized Variants</span>
                  <span className="text-xl font-bold text-amber-700">
                    {activeRun?.stage_outputs?.personalize?.item_count || selectedSegmentIds.length}
                  </span>
                </div>
                <div className="p-3 bg-slate-50 rounded-xl border border-slate-200">
                  <span className="text-[11px] text-slate-500 block">Audited & In Review</span>
                  <span className="text-xl font-bold text-emerald-700">
                    {activeRun?.stage_outputs?.review?.item_count || '100%'}
                  </span>
                </div>
              </div>

              {/* Stage Outputs Breakdown */}
              <div className="space-y-3">
                <span className="text-xs font-bold text-slate-700 uppercase tracking-wider block">
                  Stage Execution Summary
                </span>

                {activeRun?.stage_outputs &&
                  Object.entries(activeRun.stage_outputs).map(([key, val]) => (
                    <div key={key} className="p-3 rounded-xl bg-slate-50 border border-slate-200 text-xs space-y-1">
                      <div className="flex items-center justify-between">
                        <span className="font-bold text-slate-800 uppercase tracking-wider text-[11px]">
                          {key.replace('_', ' ')}
                        </span>
                        <span className="text-emerald-700 font-semibold bg-emerald-100 px-2 py-0.5 rounded text-[10px]">
                          Completed
                        </span>
                      </div>
                      <p className="text-[11px] text-slate-600">{val.summary}</p>
                    </div>
                  ))}
              </div>

              {/* Editorial Notice */}
              <div className="p-3.5 rounded-xl bg-blue-50 border border-blue-200 text-blue-900 text-xs flex items-start gap-2.5">
                <ShieldCheck className="w-4 h-4 text-blue-600 flex-shrink-0 mt-0.5" />
                <div>
                  <p className="font-bold">Ready for Editorial Sign-Off</p>
                  <p className="text-[11px] text-blue-800 leading-relaxed mt-0.5">
                    The generated copy and variants are stored in <strong>In Review</strong> status. You can now inspect, fine-tune, or sign off each asset in the Content & Translation Studio.
                  </p>
                </div>
              </div>
            </div>
          )}

        </div>

        {/* Modal Bottom Action Controls */}
        <div className="px-6 py-4 bg-slate-50 border-t border-slate-200 flex items-center justify-between">
          <div>
            {step > 1 && step < 4 && (
              <button
                type="button"
                onClick={() => setStep(step - 1)}
                className="inline-flex items-center gap-1.5 px-3.5 py-2 text-xs font-semibold rounded-xl bg-white border border-slate-300 text-slate-700 hover:bg-slate-100 transition shadow-2xs"
              >
                <ChevronLeft className="w-3.5 h-3.5" />
                Previous
              </button>
            )}
          </div>

          <div className="flex items-center gap-2">
            {step < 3 && (
              <button
                type="button"
                onClick={() => setStep(step + 1)}
                className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-semibold rounded-xl bg-blue-600 text-white hover:bg-blue-700 transition shadow-2xs"
              >
                Next Step
                <ChevronRight className="w-3.5 h-3.5" />
              </button>
            )}

            {step === 3 && (
              <button
                type="button"
                onClick={handleStartPipeline}
                disabled={executing}
                className="inline-flex items-center gap-2 px-5 py-2 text-xs font-bold rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 text-white hover:from-blue-700 hover:to-indigo-700 transition shadow-md disabled:opacity-50 active:scale-[0.98]"
              >
                <Sparkles className="w-4 h-4 text-blue-200" />
                Run 5-Stage AI Pipeline
              </button>
            )}

            {step === 5 && (
              <>
                <button
                  type="button"
                  onClick={() => {
                    onClose();
                    navigate('/content');
                  }}
                  className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-semibold rounded-xl bg-indigo-600 text-white hover:bg-indigo-700 transition shadow-2xs"
                >
                  <ExternalLink className="w-3.5 h-3.5" />
                  Open in Content Studio
                </button>
                <button
                  type="button"
                  onClick={onClose}
                  className="px-4 py-2 text-xs font-semibold rounded-xl bg-white border border-slate-300 text-slate-700 hover:bg-slate-100 transition shadow-2xs"
                >
                  Close
                </button>
              </>
            )}
          </div>
        </div>

      </div>
    </div>
  );
}

