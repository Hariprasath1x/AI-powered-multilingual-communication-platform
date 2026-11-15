import React, { useState, useEffect } from 'react';
import {
  Users,
  Sparkles,
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
  Plus,
  Trash2,
  Check,
  X,
  Eye,
  Smartphone,
  Mail,
  Sliders,
  Send,
  HelpCircle,
  FileEdit,
  ShieldAlert,
} from 'lucide-react';
import {
  getPersonalizedVariants,
  personalizeContent,
  updatePersonalizedVariant,
  deletePersonalizedVariant,
  previewRecipientSimulation,
} from '../../services/contentService';
import { listSegments } from '../../services/segmentService';
import { listAudience } from '../../services/audienceService';

const REVIEW_BADGES = {
  Approved: 'bg-emerald-100 text-emerald-900 border-emerald-300',
  Draft: 'bg-amber-100 text-amber-900 border-amber-300',
  In_Review: 'bg-blue-100 text-blue-900 border-blue-300',
  Rejected: 'bg-rose-100 text-rose-900 border-rose-300',
};

const COMMON_PLACEHOLDERS = ['{name}', '{city}', '{phone}', '{area}'];

export default function PersonalizationVariantsPanel({
  assetId,
  campaignId,
  channel = 'SMS',
  sourceLanguage = 'en',
  canReview = true,
}) {
  const [variants, setVariants] = useState([]);
  const [segments, setSegments] = useState([]);
  const [selectedSegmentIds, setSelectedSegmentIds] = useState([]);
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState(null);
  const [successMsg, setSuccessMsg] = useState(null);

  // Editing state for variants
  const [editingVariantId, setEditingVariantId] = useState(null);
  const [editTitle, setEditTitle] = useState('');
  const [editBody, setEditBody] = useState('');
  const [editCta, setEditCta] = useState('');
  const [savingEdit, setSavingEdit] = useState(false);

  // Recipient Preview Simulation Modal state
  const [showPreviewModal, setShowPreviewModal] = useState(false);
  const [audienceMembers, setAudienceMembers] = useState([]);
  const [selectedRecipientId, setSelectedRecipientId] = useState('');
  const [simulationResult, setSimulationResult] = useState(null);
  const [simulating, setSimulating] = useState(false);

  // Rejection notes modal
  const [rejectingVariantId, setRejectingVariantId] = useState(null);
  const [rejectionNotes, setRejectionNotes] = useState('');

  useEffect(() => {
    if (assetId) {
      loadData();
    }
  }, [assetId]);

  async function loadData() {
    setLoading(true);
    setError(null);
    try {
      const [vars, segs] = await Promise.all([
        getPersonalizedVariants(assetId),
        listSegments({ size: 50 }),
      ]);
      setVariants(vars || []);
      const segList = segs?.items || segs || [];
      setSegments(segList);
      if (segList.length > 0 && selectedSegmentIds.length === 0) {
        setSelectedSegmentIds(segList.slice(0, 3).map((s) => s.id));
      }
    } catch (err) {
      setError(err?.response?.data?.detail || 'Failed to load demographic variants.');
    } finally {
      setLoading(false);
    }
  }

  async function handleGenerateVariants() {
    if (selectedSegmentIds.length === 0) {
      setError('Please select at least one audience segment.');
      return;
    }
    setGenerating(true);
    setError(null);
    setSuccessMsg(null);
    try {
      const payload = {
        segment_ids: selectedSegmentIds,
        channel,
        language: sourceLanguage,
      };
      const res = await personalizeContent(assetId, payload);
      setSuccessMsg(`Generated ${res.success_count} demographic variant(s) successfully.`);
      await loadData();
    } catch (err) {
      setError(err?.response?.data?.detail || 'Failed to generate demographic variants.');
    } finally {
      setGenerating(false);
    }
  }

  function startEditing(variant) {
    setEditingVariantId(variant.id);
    setEditTitle(variant.variant_title);
    setEditBody(variant.variant_body);
    setEditCta(variant.variant_cta || '');
  }

  function cancelEditing() {
    setEditingVariantId(null);
    setEditTitle('');
    setEditBody('');
    setEditCta('');
  }

  async function handleSaveEdit(variantId) {
    setSavingEdit(true);
    setError(null);
    try {
      await updatePersonalizedVariant(variantId, {
        variant_title: editTitle,
        variant_body: editBody,
        variant_cta: editCta || undefined,
      });
      setSuccessMsg('Variant updated successfully. Notice: Material edits reset approval status to Draft.');
      cancelEditing();
      await loadData();
    } catch (err) {
      setError(err?.response?.data?.detail || 'Failed to update variant.');
    } finally {
      setSavingEdit(false);
    }
  }

  async function handleStatusChange(variantId, newStatus, notes) {
    setError(null);
    try {
      await updatePersonalizedVariant(variantId, {
        review_status: newStatus,
        review_notes: notes || undefined,
      });
      setSuccessMsg(`Variant review status updated to '${newStatus}'.`);
      setRejectingVariantId(null);
      setRejectionNotes('');
      await loadData();
    } catch (err) {
      setError(err?.response?.data?.detail || `Failed to update status to ${newStatus}.`);
    }
  }

  async function handleDeleteVariant(variantId) {
    if (!window.confirm('Are you sure you want to delete this personalized variant?')) return;
    setError(null);
    try {
      await deletePersonalizedVariant(variantId);
      setSuccessMsg('Variant deleted successfully.');
      await loadData();
    } catch (err) {
      setError(err?.response?.data?.detail || 'Failed to delete variant.');
    }
  }

  function insertPlaceholder(token) {
    setEditBody((prev) => prev + ` ${token} `);
  }

  async function openPreviewSimulation() {
    setShowPreviewModal(true);
    setSimulationResult(null);
    try {
      const res = await listAudience({ size: 30 });
      const members = res?.items || res || [];
      setAudienceMembers(members);
      if (members.length > 0) {
        setSelectedRecipientId(members[0].id);
        runSimulation(members[0].id);
      }
    } catch (err) {
      setError('Failed to fetch recipients for simulation.');
    }
  }

  async function runSimulation(recipientId) {
    if (!recipientId) return;
    setSimulating(true);
    try {
      const res = await previewRecipientSimulation(assetId, {
        recipient_id: Number(recipientId),
        channel,
        preferred_language: sourceLanguage,
      });
      setSimulationResult(res);
    } catch (err) {
      setError(err?.response?.data?.detail || 'Simulation preview failed.');
    } finally {
      setSimulating(false);
    }
  }

  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-200">
        <div>
          <div className="flex items-center gap-2">
            <Users className="w-5 h-5 text-indigo-600" />
            <h2 className="text-lg font-semibold text-slate-900">
              Audience-Specific Personalization Variants
            </h2>
            <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200">
              Task 9.A
            </span>
          </div>
          <p className="text-sm text-slate-500 mt-0.5">
            Generate tailored demographic variants for senior citizens, youth, rural farmers, and commuters.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={openPreviewSimulation}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 text-xs font-semibold text-indigo-700 bg-indigo-50 border border-indigo-200 rounded-lg hover:bg-indigo-100 transition-colors"
          >
            <Smartphone className="w-4 h-4" />
            Simulate Recipient Delivery
          </button>
          <button
            type="button"
            onClick={loadData}
            disabled={loading}
            className="p-2 text-slate-600 hover:text-slate-900 border border-slate-200 rounded-lg hover:bg-slate-50 transition-colors"
            title="Refresh variants"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {error && (
        <div className="p-3.5 bg-rose-50 border border-rose-200 rounded-lg flex items-start gap-2.5 text-sm text-rose-800">
          <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
          <span>{error}</span>
        </div>
      )}

      {successMsg && (
        <div className="p-3.5 bg-emerald-50 border border-emerald-200 rounded-lg flex items-start gap-2.5 text-sm text-emerald-800">
          <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
          <span>{successMsg}</span>
        </div>
      )}

      {/* Segment Selector & Generator Controls */}
      <div className="p-4 rounded-xl border border-slate-200 bg-slate-50/70 space-y-3">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold uppercase tracking-wider text-slate-600">
            Select Audience Segments for Demographic Tailoring
          </span>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setSelectedSegmentIds(segments.map((s) => s.id))}
              className="text-xs text-indigo-600 hover:text-indigo-800 font-medium"
            >
              Select All
            </button>
            <span className="text-slate-300">|</span>
            <button
              type="button"
              onClick={() => setSelectedSegmentIds([])}
              className="text-xs text-slate-500 hover:text-slate-700 font-medium"
            >
              Clear
            </button>
          </div>
        </div>

        {segments.length === 0 ? (
          <p className="text-xs text-slate-500 italic">
            No audience segments configured. Create segments to enable demographic tailoring.
          </p>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2.5">
            {segments.map((seg) => {
              const isSelected = selectedSegmentIds.includes(seg.id);
              return (
                <label
                  key={seg.id}
                  className={`flex items-start gap-2.5 p-3 rounded-lg border text-xs cursor-pointer transition-colors ${
                    isSelected
                      ? 'bg-indigo-50/60 border-indigo-300 text-indigo-950 font-medium shadow-sm'
                      : 'bg-white border-slate-200 text-slate-700 hover:bg-slate-50'
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={isSelected}
                    onChange={(e) => {
                      if (e.target.checked) {
                        setSelectedSegmentIds([...selectedSegmentIds, seg.id]);
                      } else {
                        setSelectedSegmentIds(selectedSegmentIds.filter((id) => id !== seg.id));
                      }
                    }}
                    className="mt-0.5 rounded text-indigo-600 focus:ring-indigo-500 border-slate-300"
                  />
                  <div className="flex-1">
                    <span className="block font-semibold">{seg.name}</span>
                    <span className="text-[11px] text-slate-500 line-clamp-1">
                      {seg.description || 'Targeted segment'}
                    </span>
                  </div>
                </label>
              );
            })}
          </div>
        )}

        <div className="flex justify-end pt-2">
          <button
            type="button"
            disabled={generating || selectedSegmentIds.length === 0}
            onClick={handleGenerateVariants}
            className="inline-flex items-center gap-2 px-4 py-2 text-xs font-semibold text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 transition-colors shadow-sm disabled:opacity-50"
          >
            <Sparkles className={`w-3.5 h-3.5 ${generating ? 'animate-spin' : ''}`} />
            {generating ? 'Generating Variants...' : `Generate ${selectedSegmentIds.length} Demographic Variant(s)`}
          </button>
        </div>
      </div>

      {/* Generated Variants Grid */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-slate-900">
            Active Demographic Variants ({variants.length})
          </h3>
          <span className="text-xs text-slate-500">
            Variants automatically staged during campaign distribution
          </span>
        </div>

        {variants.length === 0 ? (
          <div className="p-8 text-center border-2 border-dashed border-slate-200 rounded-xl bg-slate-50/50 space-y-2">
            <Users className="w-8 h-8 text-slate-400 mx-auto" />
            <p className="text-sm font-medium text-slate-700">No demographic variants generated yet.</p>
            <p className="text-xs text-slate-500 max-w-sm mx-auto">
              Select audience segments above to generate persona-tailored variants that preserve helplines and placeholders.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-4">
            {variants.map((v) => {
              const isEditing = editingVariantId === v.id;
              const badgeClass = REVIEW_BADGES[v.review_status] || REVIEW_BADGES.Draft;

              return (
                <div
                  key={v.id}
                  className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm space-y-4 hover:border-slate-300 transition-colors"
                >
                  {/* Variant Card Header */}
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-3 border-b border-slate-100">
                    <div className="flex items-center gap-2.5">
                      <span className="px-2.5 py-1 rounded-md text-xs font-semibold bg-slate-100 text-slate-800">
                        {v.segment_name || 'Segment Variant'}
                      </span>
                      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold border ${badgeClass}`}>
                        {v.review_status}
                      </span>
                      <span className="text-xs text-slate-400 uppercase font-mono">
                        {v.channel} • {v.language}
                      </span>
                    </div>

                    <div className="flex items-center gap-1.5">
                      {!isEditing && (
                        <>
                          {canReview && v.review_status !== 'Approved' && (
                            <button
                              type="button"
                              onClick={() => handleStatusChange(v.id, 'Approved')}
                              className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-md hover:bg-emerald-100"
                              title="Approve variant for broadcast"
                            >
                              <Check className="w-3.5 h-3.5" />
                              Approve
                            </button>
                          )}
                          {canReview && v.review_status !== 'Rejected' && (
                            <button
                              type="button"
                              onClick={() => setRejectingVariantId(v.id)}
                              className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium text-rose-700 bg-rose-50 border border-rose-200 rounded-md hover:bg-rose-100"
                              title="Reject variant with notes"
                            >
                              <X className="w-3.5 h-3.5" />
                              Reject
                            </button>
                          )}
                          <button
                            type="button"
                            onClick={() => startEditing(v)}
                            className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium text-slate-700 bg-white border border-slate-200 rounded-md hover:bg-slate-50"
                          >
                            <FileEdit className="w-3.5 h-3.5" />
                            Edit
                          </button>
                          <button
                            type="button"
                            onClick={() => handleDeleteVariant(v.id)}
                            className="p-1 text-slate-400 hover:text-rose-600 rounded"
                            title="Delete variant"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </>
                      )}
                    </div>
                  </div>

                  {/* Card Content or Editing Form */}
                  {isEditing ? (
                    <div className="space-y-3 pt-1">
                      <div>
                        <label className="block text-xs font-medium text-slate-700 mb-1">
                          Variant Title
                        </label>
                        <input
                          type="text"
                          value={editTitle}
                          onChange={(e) => setEditTitle(e.target.value)}
                          className="w-full text-xs px-3 py-2 rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                        />
                      </div>

                      <div>
                        <div className="flex items-center justify-between mb-1">
                          <label className="text-xs font-medium text-slate-700">
                            Variant Body
                          </label>
                          {/* Placeholder helper chips */}
                          <div className="flex items-center gap-1">
                            <span className="text-[10px] text-slate-400">Insert tag:</span>
                            {COMMON_PLACEHOLDERS.map((token) => (
                              <button
                                key={token}
                                type="button"
                                onClick={() => insertPlaceholder(token)}
                                className="px-1.5 py-0.5 text-[10px] font-mono bg-slate-100 hover:bg-indigo-100 text-slate-700 hover:text-indigo-800 rounded border border-slate-200"
                              >
                                {token}
                              </button>
                            ))}
                          </div>
                        </div>
                        <textarea
                          rows={4}
                          value={editBody}
                          onChange={(e) => setEditBody(e.target.value)}
                          className="w-full text-xs px-3 py-2 rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-indigo-500 font-sans"
                        />
                      </div>

                      <div>
                        <label className="block text-xs font-medium text-slate-700 mb-1">
                          Call to Action (Optional)
                        </label>
                        <input
                          type="text"
                          value={editCta}
                          onChange={(e) => setEditCta(e.target.value)}
                          className="w-full text-xs px-3 py-2 rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                        />
                      </div>

                      <div className="flex justify-end gap-2 pt-2">
                        <button
                          type="button"
                          onClick={cancelEditing}
                          className="px-3 py-1.5 text-xs font-medium text-slate-600 bg-white border border-slate-300 rounded-lg hover:bg-slate-50"
                        >
                          Cancel
                        </button>
                        <button
                          type="button"
                          disabled={savingEdit}
                          onClick={() => handleSaveEdit(v.id)}
                          className="px-3.5 py-1.5 text-xs font-semibold text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 disabled:opacity-50"
                        >
                          {savingEdit ? 'Saving...' : 'Save Changes'}
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div className="space-y-2">
                      <h4 className="text-xs font-bold text-slate-900">{v.variant_title}</h4>
                      <p className="text-xs text-slate-700 whitespace-pre-wrap leading-relaxed bg-slate-50/50 p-3 rounded-lg border border-slate-100 font-sans">
                        {v.variant_body}
                      </p>
                      {v.variant_cta && (
                        <div className="text-xs text-slate-600">
                          <span className="font-semibold text-slate-800">CTA: </span>
                          <span className="font-medium text-indigo-700">{v.variant_cta}</span>
                        </div>
                      )}
                      {v.personalization_notes && (
                        <p className="text-[11px] text-slate-500 italic pt-1">
                          Tailoring Logic: {v.personalization_notes}
                        </p>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Recipient Preview Simulation Modal */}
      {showPreviewModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-sm animate-fade-in">
          <div className="bg-white rounded-2xl shadow-2xl max-w-2xl w-full max-h-[85vh] flex flex-col border border-slate-200">
            {/* Modal Header */}
            <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Smartphone className="w-5 h-5 text-indigo-600" />
                <h3 className="text-base font-semibold text-slate-900">
                  Recipient Delivery Simulation
                </h3>
                <span className="text-xs px-2 py-0.5 rounded-full bg-amber-100 text-amber-800 border border-amber-200 font-semibold">
                  Preview Mode
                </span>
              </div>
              <button
                onClick={() => setShowPreviewModal(false)}
                className="p-1 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Modal Content */}
            <div className="p-6 overflow-y-auto space-y-5">
              {/* Recipient Selector */}
              <div className="space-y-1.5">
                <label className="block text-xs font-semibold text-slate-700">
                  Select Target Recipient for Preview
                </label>
                <select
                  value={selectedRecipientId}
                  onChange={(e) => {
                    setSelectedRecipientId(e.target.value);
                    runSimulation(e.target.value);
                  }}
                  className="w-full text-xs px-3 py-2 rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-indigo-500 bg-white"
                >
                  {audienceMembers.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.name} ({m.city || 'No City'} • {m.age ? `${m.age} yrs` : 'Unknown Age'} • {m.phone || m.email})
                    </option>
                  ))}
                </select>
              </div>

              {simulating ? (
                <div className="p-12 text-center text-xs text-slate-500">
                  <RefreshCw className="w-6 h-6 text-indigo-500 animate-spin mx-auto mb-2" />
                  Simulating recipient message rendering...
                </div>
              ) : simulationResult ? (
                <div className="space-y-4">
                  {/* Smartphone message mockup */}
                  <div className="p-4 rounded-xl bg-slate-900 text-white max-w-md mx-auto shadow-lg space-y-3 font-sans">
                    <div className="flex items-center justify-between text-[11px] text-slate-400 border-b border-slate-800 pb-2">
                      <span>To: {simulationResult.recipient_name} ({simulationResult.recipient_address})</span>
                      <span className="font-mono text-emerald-400">{simulationResult.channel}</span>
                    </div>

                    <div className="space-y-1.5">
                      <div className="text-xs font-bold text-slate-100">
                        {simulationResult.preview_title}
                      </div>
                      <div className="text-xs text-slate-200 whitespace-pre-wrap leading-relaxed">
                        {simulationResult.preview_body}
                      </div>
                      {simulationResult.preview_cta && (
                        <div className="pt-2">
                          <span className="inline-block px-3 py-1 bg-indigo-600 text-white text-[11px] font-semibold rounded-md">
                            {simulationResult.preview_cta}
                          </span>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Substituted Placeholders Table */}
                  <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg space-y-2 text-xs">
                    <span className="font-semibold text-slate-700">Substituted Dynamic Attributes</span>
                    <div className="grid grid-cols-2 gap-2 text-slate-600">
                      {Object.entries(simulationResult.substituted_placeholders || {}).map(([ph, val]) => (
                        <div key={ph} className="flex items-center gap-1">
                          <code className="text-[11px] bg-slate-200 px-1 rounded text-slate-800">{ph}</code>
                          <span className="text-slate-400">→</span>
                          <span className="font-semibold text-slate-900">{val}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              ) : null}
            </div>

            {/* Modal Footer */}
            <div className="px-6 py-4 border-t border-slate-200 flex justify-end bg-slate-50 rounded-b-2xl">
              <button
                type="button"
                onClick={() => setShowPreviewModal(false)}
                className="px-4 py-2 text-xs font-medium text-slate-700 bg-white border border-slate-300 rounded-lg hover:bg-slate-100"
              >
                Close Preview
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Rejection Notes Modal */}
      {rejectingVariantId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-sm animate-fade-in">
          <div className="bg-white rounded-2xl shadow-xl max-w-md w-full p-6 space-y-4 border border-slate-200">
            <div className="flex items-center gap-2 text-rose-700 font-semibold text-sm">
              <ShieldAlert className="w-5 h-5 text-rose-600" />
              <span>Reject Variant with Review Notes</span>
            </div>
            <p className="text-xs text-slate-500">
              Provide mandatory feedback explaining why this demographic variant copy was rejected.
            </p>
            <textarea
              rows={3}
              value={rejectionNotes}
              onChange={(e) => setRejectionNotes(e.target.value)}
              placeholder="e.g. Tone too colloquial for government advisory. Please revise headline."
              className="w-full text-xs px-3 py-2 rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-rose-500"
            />
            <div className="flex justify-end gap-2 pt-1">
              <button
                type="button"
                onClick={() => {
                  setRejectingVariantId(null);
                  setRejectionNotes('');
                }}
                className="px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-100 rounded-lg"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={!rejectionNotes.trim()}
                onClick={() => handleStatusChange(rejectingVariantId, 'Rejected', rejectionNotes)}
                className="px-3.5 py-1.5 text-xs font-semibold text-white bg-rose-600 hover:bg-rose-700 rounded-lg disabled:opacity-50"
              >
                Confirm Rejection
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

