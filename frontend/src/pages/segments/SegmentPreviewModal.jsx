import React, { useState, useEffect } from 'react';
import {
  X,
  Users,
  Filter,
  CheckCircle2,
  XCircle,
  HelpCircle,
  ChevronLeft,
  ChevronRight,
  RefreshCw,
  Mail,
  Phone,
  Globe,
  MapPin,
  ShieldAlert
} from 'lucide-react';
import { previewSavedSegment } from '../../services/segmentService';

export default function SegmentPreviewModal({ isOpen, onClose, segment }) {
  const [loading, setLoading] = useState(false);
  const [previewData, setPreviewData] = useState(null);
  const [error, setError] = useState('');
  const [page, setPage] = useState(1);
  const pageSize = 8;

  const fetchPreview = async (targetPage = 1) => {
    if (!segment) return;
    setLoading(true);
    setError('');
    try {
      const offset = (targetPage - 1) * pageSize;
      const data = await previewSavedSegment(segment.id, pageSize, offset);
      setPreviewData(data);
      setPage(targetPage);
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to load segment preview.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen && segment) {
      setPage(1);
      fetchPreview(1);
    } else {
      setPreviewData(null);
      setError('');
    }
  }, [isOpen, segment]);

  if (!isOpen || !segment) return null;

  const totalMatching = previewData?.total_matching ?? 0;
  const sampleMembers = previewData?.sample_members ?? [];
  const totalPages = Math.max(1, Math.ceil(totalMatching / pageSize));

  const formatConsentBadge = (status) => {
    if (status === true) {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
          <CheckCircle2 className="w-3 h-3 text-emerald-600" />
          Confirmed
        </span>
      );
    }
    if (status === false) {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-rose-50 text-rose-700 border border-rose-200">
          <XCircle className="w-3 h-3 text-rose-600" />
          Revoked
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-amber-50 text-amber-700 border border-amber-200">
        <HelpCircle className="w-3 h-3 text-amber-600" />
        Unconfirmed
      </span>
    );
  };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="relative bg-white rounded-2xl max-w-4xl w-full shadow-2xl border border-slate-200 overflow-hidden flex flex-col max-h-[90vh]">
        
        {/* Modal Header */}
        <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between bg-slate-50">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-brand-100 text-brand-700 flex items-center justify-center">
              <Users className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
                {segment.name}
                <span className="text-xs font-normal px-2.5 py-0.5 rounded-full bg-brand-50 text-brand-700 border border-brand-200">
                  Live Preview
                </span>
              </h3>
              <p className="text-xs text-slate-500 line-clamp-1">
                {segment.description || 'No description provided.'}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-lg flex items-center justify-center text-slate-400 hover:text-slate-600 hover:bg-slate-200 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-6 overflow-y-auto flex-1 space-y-5">
          {/* Summary Banner */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="p-4 rounded-xl bg-slate-50 border border-slate-200">
              <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                Matching Audience
              </span>
              <p className="text-2xl font-extrabold text-slate-900 mt-1">
                {loading ? '...' : totalMatching.toLocaleString()}
              </p>
              <span className="text-[11px] text-slate-500">recipients qualify</span>
            </div>

            <div className="p-4 rounded-xl bg-slate-50 border border-slate-200">
              <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                Rule Connector
              </span>
              <p className="text-sm font-bold text-brand-700 mt-1 uppercase">
                {segment.filter_rules?.connector || 'AND'}
              </p>
              <span className="text-[11px] text-slate-500">
                {segment.filter_rules?.conditions?.length || 0} active conditions
              </span>
            </div>

            <div className="p-4 rounded-xl bg-slate-50 border border-slate-200">
              <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                Created By
              </span>
              <p className="text-xs font-semibold text-slate-800 mt-1 line-clamp-1">
                {segment.creator_name || `User #${segment.created_by}`}
              </p>
              <span className="text-[11px] text-slate-500">
                {segment.created_at ? new Date(segment.created_at).toLocaleDateString() : 'N/A'}
              </span>
            </div>
          </div>

          {/* Consent / Dispatch Clarification Notice */}
          <div className="flex items-start gap-2.5 p-3 rounded-xl bg-amber-50 border border-amber-200 text-xs text-amber-800">
            <ShieldAlert className="w-4 h-4 text-amber-600 mt-0.5 flex-shrink-0" />
            <div>
              <span className="font-semibold">Compliance Note:</span> Audience segmentation evaluates database demographic criteria. In accordance with platform privacy safeguards, campaign message dispatch independently verifies confirmed consent before sending messages.
            </div>
          </div>

          {/* Error Message */}
          {error && (
            <div className="p-3 bg-rose-50 border border-rose-200 text-xs text-rose-700 rounded-xl">
              {error}
            </div>
          )}

          {/* Preview Members Table */}
          <div className="border border-slate-200 rounded-xl overflow-hidden shadow-sm">
            <div className="px-4 py-2.5 bg-slate-100 border-b border-slate-200 flex items-center justify-between">
              <span className="text-xs font-bold text-slate-700 uppercase tracking-wider">
                Sample Matching Recipients (Page {page} of {totalPages})
              </span>
              <button
                type="button"
                onClick={() => fetchPreview(page)}
                disabled={loading}
                className="inline-flex items-center gap-1 text-xs text-slate-600 hover:text-brand-600 transition"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
                Refresh
              </button>
            </div>

            {loading ? (
              <div className="p-12 text-center text-slate-400 text-xs flex flex-col items-center gap-2">
                <RefreshCw className="w-6 h-6 animate-spin text-brand-600" />
                Querying database records...
              </div>
            ) : sampleMembers.length === 0 ? (
              <div className="p-10 text-center text-slate-500 text-xs">
                No audience members currently match this segment's filter criteria.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-50 border-b border-slate-200 text-slate-600 font-semibold">
                    <tr>
                      <th className="px-4 py-2.5">Name / Demographics</th>
                      <th className="px-4 py-2.5">Contact</th>
                      <th className="px-4 py-2.5">Language</th>
                      <th className="px-4 py-2.5">Channel</th>
                      <th className="px-4 py-2.5">Location</th>
                      <th className="px-4 py-2.5">Consent</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {sampleMembers.map((m) => (
                      <tr key={m.id} className="hover:bg-slate-50 transition">
                        <td className="px-4 py-2.5">
                          <div className="font-semibold text-slate-900">{m.name}</div>
                          <div className="text-[11px] text-slate-400">
                            {m.age ? `Age ${m.age}` : 'Age: N/A'}
                            {m.gender ? ` • ${m.gender}` : ''}
                            {m.occupation ? ` • ${m.occupation}` : ''}
                          </div>
                        </td>
                        <td className="px-4 py-2.5 text-slate-600">
                          {m.email && <div className="flex items-center gap-1"><Mail className="w-3 h-3 text-slate-400" /> {m.email}</div>}
                          {m.phone && <div className="flex items-center gap-1 text-[11px] text-slate-500"><Phone className="w-3 h-3 text-slate-400" /> {m.phone}</div>}
                        </td>
                        <td className="px-4 py-2.5 font-medium text-slate-800 uppercase">
                          {m.preferred_language || '—'}
                        </td>
                        <td className="px-4 py-2.5 capitalize text-slate-700">
                          {m.preferred_channel || '—'}
                        </td>
                        <td className="px-4 py-2.5 text-slate-600">
                          {m.city || m.state ? (
                            <span className="flex items-center gap-1">
                              <MapPin className="w-3 h-3 text-slate-400" />
                              {[m.city, m.state].filter(Boolean).join(', ')}
                            </span>
                          ) : (
                            '—'
                          )}
                        </td>
                        <td className="px-4 py-2.5">
                          {formatConsentBadge(m.consent_status)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>

        {/* Modal Footer with Pagination */}
        <div className="px-6 py-3.5 border-t border-slate-200 bg-slate-50 flex items-center justify-between">
          <div className="text-xs text-slate-500">
            Showing {sampleMembers.length} of {totalMatching} recipients
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => fetchPreview(page - 1)}
              disabled={page <= 1 || loading}
              className="p-1.5 rounded-lg border border-slate-300 text-slate-700 hover:bg-slate-200 disabled:opacity-40 transition"
              title="Previous page"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <span className="text-xs font-semibold text-slate-700 px-2">
              Page {page} / {totalPages}
            </span>
            <button
              type="button"
              onClick={() => fetchPreview(page + 1)}
              disabled={page >= totalPages || loading}
              className="p-1.5 rounded-lg border border-slate-300 text-slate-700 hover:bg-slate-200 disabled:opacity-40 transition"
              title="Next page"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
            <button
              type="button"
              onClick={onClose}
              className="ml-4 px-4 py-1.5 text-xs font-semibold text-slate-700 bg-white hover:bg-slate-100 border border-slate-300 rounded-lg transition"
            >
              Close
            </button>
          </div>
        </div>

      </div>
    </div>
  );
}

