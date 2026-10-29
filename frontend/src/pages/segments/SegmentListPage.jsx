import React, { useState, useEffect, useCallback } from 'react';
import {
  Layers,
  Plus,
  Search,
  RefreshCw,
  Eye,
  Edit2,
  Trash2,
  Users,
  CheckCircle2,
  AlertCircle,
  Filter,
  ShieldAlert,
  ChevronLeft,
  ChevronRight,
  Info
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { listSegments } from '../../services/segmentService';
import SegmentBuilderModal from './SegmentBuilderModal';
import SegmentPreviewModal from './SegmentPreviewModal';
import SegmentDeleteModal from './SegmentDeleteModal';

export default function SegmentListPage() {
  const { user, isAdmin, isCampaignManager, isCommunicationTeam } = useAuth();
  const canCreateSegments = isAdmin || isCampaignManager;

  // Data State
  const [segments, setSegments] = useState([]);
  const [totalCount, setTotalCount] = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [loading, setLoading] = useState(true);
  const [toastMessage, setToastMessage] = useState('');

  // Search & Filter State
  const [searchTerm, setSearchTerm] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');

  // Modals State
  const [builderModalOpen, setBuilderModalOpen] = useState(false);
  const [editingSegment, setEditingSegment] = useState(null);
  const [previewModalOpen, setPreviewModalOpen] = useState(false);
  const [previewingSegment, setPreviewingSegment] = useState(null);
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [deletingSegment, setDeletingSegment] = useState(null);

  // Debounce search
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(searchTerm);
      setCurrentPage(1);
    }, 300);
    return () => clearTimeout(timer);
  }, [searchTerm]);

  const fetchSegments = useCallback(async () => {
    setLoading(true);
    try {
      const params = {
        page: currentPage,
        page_size: pageSize,
      };
      if (debouncedSearch) params.search = debouncedSearch;

      const data = await listSegments(params);
      setSegments(data.items || []);
      setTotalCount(data.total || 0);
      setTotalPages(data.total_pages || 1);
    } catch (err) {
      showToast(err.response?.data?.detail || 'Failed to load audience segments.');
    } finally {
      setLoading(false);
    }
  }, [currentPage, pageSize, debouncedSearch]);

  useEffect(() => {
    fetchSegments();
  }, [fetchSegments]);

  const showToast = (msg) => {
    setToastMessage(msg);
    setTimeout(() => {
      setToastMessage('');
    }, 4500);
  };

  // Permission check for modifying a segment
  const canModifySegment = (seg) => {
    if (isAdmin) return true;
    if (isCampaignManager && seg.created_by === user?.id) return true;
    return false;
  };

  // Helper to format rule summary badges
  const renderRuleBadges = (filterRules) => {
    if (!filterRules) return <span className="text-slate-400 italic">No rules defined</span>;
    const connector = filterRules.connector || 'AND';
    const conditions = filterRules.conditions || [];
    const groups = filterRules.groups || [];

    if (conditions.length === 0 && groups.length === 0) {
      return <span className="text-slate-400 italic">Empty rule set</span>;
    }

    return (
      <div className="flex flex-wrap items-center gap-1.5 max-w-md">
        <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-indigo-100 text-indigo-700 uppercase">
          {connector}
        </span>
        {conditions.slice(0, 3).map((c, i) => (
          <span
            key={i}
            className="px-2 py-0.5 rounded text-[10px] font-medium bg-slate-100 text-slate-700 border border-slate-200"
            title={`${c.field} ${c.operator} ${c.value ?? ''}`}
          >
            {c.field.replace('_', ' ')} {formatOperatorShort(c.operator)} {formatValueShort(c.value)}
          </span>
        ))}
        {conditions.length > 3 && (
          <span className="text-[10px] text-slate-500 font-semibold">
            +{conditions.length - 3} more
          </span>
        )}
        {groups.length > 0 && (
          <span className="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-purple-50 text-purple-700 border border-purple-200">
            +{groups.length} sub-group{groups.length > 1 ? 's' : ''}
          </span>
        )}
      </div>
    );
  };

  const formatOperatorShort = (op) => {
    switch (op) {
      case 'equals': return '=';
      case 'not_equals': return '≠';
      case 'greater_than': return '>';
      case 'greater_than_or_equal': return '≥';
      case 'less_than': return '<';
      case 'less_than_or_equal': return '≤';
      case 'contains': return '~';
      case 'starts_with': return '^';
      case 'in': return 'in';
      case 'is_empty': return 'is null';
      case 'is_not_empty': return 'not null';
      default: return op;
    }
  };

  const formatValueShort = (val) => {
    if (val === null || val === undefined) return '';
    if (typeof val === 'boolean') return val ? 'true' : 'false';
    if (Array.isArray(val)) return `[${val.join(',')}]`;
    return String(val);
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      
      {/* Toast Notification */}
      {toastMessage && (
        <div className="fixed top-20 right-6 z-50 p-4 rounded-xl shadow-xl bg-slate-900 text-white text-xs flex items-center gap-3 animate-fade-in">
          <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
          <span>{toastMessage}</span>
          <button onClick={() => setToastMessage('')} className="ml-2 text-slate-400 hover:text-white">
            &times;
          </button>
        </div>
      )}

      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-brand-100 text-brand-700 flex items-center justify-center font-bold">
              <Layers className="w-4 h-4" />
            </div>
            <h1 className="text-xl sm:text-2xl font-extrabold text-slate-900 tracking-tight">
              Audience Segments
            </h1>
            <span className="text-[11px] font-semibold px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200">
              Task 5 Engine
            </span>
          </div>
          <p className="text-xs text-slate-600 max-w-2xl">
            Create and maintain dynamic rule-based cohorts to target civic communications by language, geography, channel, and consent status.
          </p>
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-3">
          {isCommunicationTeam && (
            <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-blue-50 border border-blue-200 text-blue-700 text-xs font-medium">
              <Info className="w-3.5 h-3.5" />
              <span>Read-Only & Preview Access</span>
            </div>
          )}

          {canCreateSegments && (
            <button
              onClick={() => {
                setEditingSegment(null);
                setBuilderModalOpen(true);
              }}
              className="inline-flex items-center gap-2 px-4 py-2 text-xs font-semibold text-white bg-brand-600 hover:bg-brand-700 rounded-xl shadow-sm transition"
            >
              <Plus className="w-4 h-4" />
              Create Segment
            </button>
          )}
        </div>
      </div>

      {/* Search and Filters Bar */}
      <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm flex flex-col sm:flex-row items-center justify-between gap-3">
        <div className="relative w-full sm:w-80">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
          <input
            type="text"
            placeholder="Search segments by name or description..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-9 pr-4 py-1.5 text-xs rounded-lg border border-slate-300 focus:ring-2 focus:ring-brand-500 focus:outline-none transition"
          />
        </div>

        <div className="flex items-center gap-2 w-full sm:w-auto justify-end">
          <button
            onClick={fetchSegments}
            disabled={loading}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-slate-700 bg-slate-50 hover:bg-slate-100 border border-slate-300 rounded-lg transition"
            title="Reload segments"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>
      </div>

      {/* Segments Table */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
        {loading ? (
          <div className="p-12 text-center text-slate-500 text-xs flex flex-col items-center gap-2">
            <RefreshCw className="w-6 h-6 text-brand-600 animate-spin" />
            Loading audience segments...
          </div>
        ) : segments.length === 0 ? (
          <div className="p-12 text-center space-y-3">
            <div className="w-12 h-12 rounded-2xl bg-slate-100 text-slate-400 flex items-center justify-center mx-auto">
              <Layers className="w-6 h-6" />
            </div>
            <h3 className="text-sm font-bold text-slate-800">No Audience Segments Found</h3>
            <p className="text-xs text-slate-500 max-w-sm mx-auto">
              {debouncedSearch
                ? `No segments matched "${debouncedSearch}". Try clearing your search.`
                : 'No segments have been defined yet. Build your first rule-based cohort.'}
            </p>
            {canCreateSegments && !debouncedSearch && (
              <button
                onClick={() => {
                  setEditingSegment(null);
                  setBuilderModalOpen(true);
                }}
                className="mt-2 inline-flex items-center gap-2 px-4 py-2 text-xs font-semibold text-white bg-brand-600 hover:bg-brand-700 rounded-xl transition"
              >
                <Plus className="w-4 h-4" />
                Build First Segment
              </button>
            )}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 border-b border-slate-200 text-slate-600 font-semibold uppercase tracking-wider">
                <tr>
                  <th className="px-5 py-3.5">Segment Name</th>
                  <th className="px-5 py-3.5">Rule Criteria</th>
                  <th className="px-5 py-3.5">Matching Audience</th>
                  <th className="px-5 py-3.5">Owner / Creator</th>
                  <th className="px-5 py-3.5 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {segments.map((seg) => {
                  const hasEditPermission = canModifySegment(seg);
                  return (
                    <tr key={seg.id} className="hover:bg-slate-50/80 transition">
                      
                      {/* Name & Description */}
                      <td className="px-5 py-4 max-w-xs">
                        <div className="font-bold text-slate-900 text-sm">{seg.name}</div>
                        {seg.description ? (
                          <div className="text-slate-500 text-[11px] mt-0.5 line-clamp-2">
                            {seg.description}
                          </div>
                        ) : (
                          <div className="text-slate-400 text-[11px] mt-0.5 italic">
                            No description
                          </div>
                        )}
                        <div className="text-[10px] text-slate-400 mt-1">
                          Created: {new Date(seg.created_at).toLocaleDateString()}
                        </div>
                      </td>

                      {/* Rule Criteria Badges */}
                      <td className="px-5 py-4">
                        {renderRuleBadges(seg.filter_rules)}
                      </td>

                      {/* Live Audience Count */}
                      <td className="px-5 py-4">
                        <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-slate-100 border border-slate-200 text-slate-800 font-semibold">
                          <Users className="w-3.5 h-3.5 text-brand-600" />
                          <span>{seg.matching_audience_count?.toLocaleString() ?? 0}</span>
                          <span className="text-[10px] text-slate-500 font-normal">recipients</span>
                        </div>
                      </td>

                      {/* Creator */}
                      <td className="px-5 py-4 text-slate-600">
                        <div className="font-medium text-slate-900">
                          {seg.creator_name || `User #${seg.created_by}`}
                        </div>
                        {seg.creator_email && (
                          <div className="text-[11px] text-slate-400">{seg.creator_email}</div>
                        )}
                      </td>

                      {/* Actions */}
                      <td className="px-5 py-4 text-right">
                        <div className="flex items-center justify-end gap-1.5">
                          {/* Live Preview Button */}
                          <button
                            onClick={() => {
                              setPreviewingSegment(seg);
                              setPreviewModalOpen(true);
                            }}
                            className="inline-flex items-center gap-1 px-2.5 py-1.5 text-xs font-semibold text-brand-700 bg-brand-50 hover:bg-brand-100 border border-brand-200 rounded-lg transition"
                            title="Preview matching audience members"
                          >
                            <Eye className="w-3.5 h-3.5" />
                            Preview
                          </button>

                          {/* Edit Button */}
                          {hasEditPermission && (
                            <button
                              onClick={() => {
                                setEditingSegment(seg);
                                setBuilderModalOpen(true);
                              }}
                              className="p-1.5 text-slate-500 hover:text-slate-800 hover:bg-slate-100 rounded-lg transition"
                              title="Edit segment rules"
                            >
                              <Edit2 className="w-3.5 h-3.5" />
                            </button>
                          )}

                          {/* Delete Button */}
                          {hasEditPermission && (
                            <button
                              onClick={() => {
                                setDeletingSegment(seg);
                                setDeleteModalOpen(true);
                              }}
                              className="p-1.5 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition"
                              title="Delete segment"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination Footer */}
        {totalCount > 0 && (
          <div className="px-6 py-3.5 border-t border-slate-200 bg-slate-50 flex items-center justify-between">
            <span className="text-xs text-slate-500">
              Showing {(currentPage - 1) * pageSize + 1} to{' '}
              {Math.min(currentPage * pageSize, totalCount)} of {totalCount} segments
            </span>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                disabled={currentPage <= 1 || loading}
                className="p-1.5 rounded-lg border border-slate-300 text-slate-700 hover:bg-slate-100 disabled:opacity-40 transition"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
              <span className="text-xs font-semibold text-slate-700 px-2">
                Page {currentPage} of {totalPages}
              </span>
              <button
                onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                disabled={currentPage >= totalPages || loading}
                className="p-1.5 rounded-lg border border-slate-300 text-slate-700 hover:bg-slate-100 disabled:opacity-40 transition"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Modals */}
      <SegmentBuilderModal
        isOpen={builderModalOpen}
        onClose={() => setBuilderModalOpen(false)}
        editingSegment={editingSegment}
        onSuccess={(msg) => {
          showToast(msg);
          fetchSegments();
        }}
      />

      <SegmentPreviewModal
        isOpen={previewModalOpen}
        onClose={() => {
          setPreviewModalOpen(false);
          setPreviewingSegment(null);
        }}
        segment={previewingSegment}
      />

      <SegmentDeleteModal
        isOpen={deleteModalOpen}
        onClose={() => {
          setDeleteModalOpen(false);
          setDeletingSegment(null);
        }}
        segment={deletingSegment}
        onSuccess={(msg) => {
          showToast(msg);
          fetchSegments();
        }}
      />

    </div>
  );
}

