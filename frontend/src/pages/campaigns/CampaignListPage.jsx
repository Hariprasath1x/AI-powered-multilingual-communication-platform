import React, { useState, useEffect, useCallback } from 'react';
import { Link, useLocation } from 'react-router-dom';
import {
  Megaphone,
  Plus,
  Search,
  Filter,
  RefreshCw,
  Eye,
  Edit2,
  Trash2,
  Calendar,
  Users,
  CheckCircle2,
  AlertCircle,
  ChevronLeft,
  ChevronRight,
  Layers,
  Sparkles,
  Clock
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { listCampaigns, getCampaignMeta } from '../../services/campaignService';
import CampaignDeleteModal from './CampaignDeleteModal';

export default function CampaignListPage() {
  const { user, isAdmin, isCampaignManager } = useAuth();
  const location = useLocation();
  const canCreate = isAdmin || isCampaignManager;

  // Data State
  const [campaigns, setCampaigns] = useState([]);
  const [totalCount, setTotalCount] = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [loading, setLoading] = useState(true);
  const [toastMessage, setToastMessage] = useState(location.state?.message || '');

  // Filter Options State
  const [metaOptions, setMetaOptions] = useState({
    types: [],
    priorities: [],
    statuses: [],
    channels: [],
  });
  const [selectedStatus, setSelectedStatus] = useState('');
  const [selectedType, setSelectedType] = useState('');
  const [selectedPriority, setSelectedPriority] = useState('');
  const [searchTerm, setSearchTerm] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');

  // Modals
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [deletingCampaign, setDeletingCampaign] = useState(null);

  // Debounce search
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(searchTerm);
      setCurrentPage(1);
    }, 300);
    return () => clearTimeout(timer);
  }, [searchTerm]);

  // Load metadata options once
  useEffect(() => {
    getCampaignMeta()
      .then((data) => setMetaOptions(data))
      .catch(() => {});
  }, []);

  const fetchCampaigns = useCallback(async () => {
    setLoading(true);
    try {
      const params = {
        page: currentPage,
        page_size: pageSize,
      };
      if (debouncedSearch) params.search = debouncedSearch;
      if (selectedStatus) params.status = selectedStatus;
      if (selectedType) params.type = selectedType;
      if (selectedPriority) params.priority = selectedPriority;

      const data = await listCampaigns(params);
      setCampaigns(data.items || []);
      setTotalCount(data.total || 0);
      setTotalPages(data.total_pages || 1);
    } catch (err) {
      showToast(err.response?.data?.detail || 'Failed to load campaigns.');
    } finally {
      setLoading(false);
    }
  }, [currentPage, pageSize, debouncedSearch, selectedStatus, selectedType, selectedPriority]);

  useEffect(() => {
    fetchCampaigns();
  }, [fetchCampaigns]);

  const showToast = (msg) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(''), 4500);
  };

  const canModifyCampaign = (camp) => {
    if (isAdmin) return true;
    if (isCampaignManager && camp.created_by === user?.id) return true;
    return false;
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
        return 'bg-rose-50 text-rose-700 border-rose-200';
      case 'Medium':
        return 'bg-amber-50 text-amber-700 border-amber-200';
      case 'Low':
      default:
        return 'bg-slate-100 text-slate-600 border-slate-200';
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      
      {/* Toast Alert */}
      {toastMessage && (
        <div className="fixed bottom-6 right-6 z-50 flex items-center gap-2.5 px-4 py-3 bg-slate-900 text-white text-sm font-medium rounded-xl shadow-2xl border border-slate-700 animate-fade-in">
          <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
          <span>{toastMessage}</span>
        </div>
      )}

      {/* Header Banner */}
      <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-emerald-100 text-emerald-600 flex items-center justify-center">
              <Megaphone className="w-4 h-4" />
            </div>
            <h1 className="text-xl sm:text-2xl font-extrabold text-slate-900 tracking-tight">
              Campaign Studio
            </h1>
          </div>
          <p className="text-sm text-slate-600 max-w-2xl">
            Design multi-channel public communication campaigns with audience segmentation, template linking, and consent compliance.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Link
            to="/templates"
            className="inline-flex items-center gap-1.5 px-4 py-2.5 bg-white border border-slate-200 hover:bg-slate-50 text-slate-700 text-sm font-semibold rounded-xl transition shadow-2xs"
          >
            Template Library
          </Link>
          {canCreate && (
            <Link
              to="/campaigns/new"
              className="inline-flex items-center gap-2 px-4 py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white text-sm font-semibold rounded-xl shadow-sm hover:shadow-emerald-500/25 transition active:scale-[0.98] whitespace-nowrap"
            >
              <Plus className="w-4 h-4" />
              New Campaign
            </Link>
          )}
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-2xs space-y-3">
        <div className="grid grid-cols-1 sm:grid-cols-12 gap-3">
          
          {/* Search Term */}
          <div className="sm:col-span-4 relative">
            <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-3 pointer-events-none" />
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Search by campaign title or objective..."
              className="w-full pl-9 pr-4 py-2 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 focus:bg-white transition"
            />
          </div>

          {/* Status Filter */}
          <div className="sm:col-span-3">
            <select
              value={selectedStatus}
              onChange={(e) => {
                setSelectedStatus(e.target.value);
                setCurrentPage(1);
              }}
              className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 focus:bg-white transition"
            >
              <option value="">All Statuses</option>
              {metaOptions.statuses.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </div>

          {/* Type Filter */}
          <div className="sm:col-span-2">
            <select
              value={selectedType}
              onChange={(e) => {
                setSelectedType(e.target.value);
                setCurrentPage(1);
              }}
              className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 focus:bg-white transition"
            >
              <option value="">All Types</option>
              {metaOptions.types.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </div>

          {/* Priority Filter */}
          <div className="sm:col-span-2">
            <select
              value={selectedPriority}
              onChange={(e) => {
                setSelectedPriority(e.target.value);
                setCurrentPage(1);
              }}
              className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 focus:bg-white transition"
            >
              <option value="">All Priorities</option>
              {metaOptions.priorities.map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>
          </div>

          {/* Refresh Button */}
          <div className="sm:col-span-1 flex justify-end">
            <button
              onClick={fetchCampaigns}
              title="Refresh campaigns"
              className="w-full sm:w-auto p-2 text-slate-500 hover:text-brand-600 hover:bg-slate-100 border border-slate-200 rounded-xl transition flex items-center justify-center"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            </button>
          </div>
        </div>

        {/* Clear Filters bar */}
        {(selectedStatus || selectedType || selectedPriority || debouncedSearch) && (
          <div className="flex items-center gap-2 pt-2 border-t border-slate-100 text-xs text-slate-500">
            <span>Filtered by:</span>
            {debouncedSearch && <span className="px-2 py-0.5 rounded bg-slate-100 text-slate-700">"{debouncedSearch}"</span>}
            {selectedStatus && <span className="px-2 py-0.5 rounded bg-slate-100 text-slate-700">{selectedStatus}</span>}
            {selectedType && <span className="px-2 py-0.5 rounded bg-slate-100 text-slate-700">{selectedType}</span>}
            {selectedPriority && <span className="px-2 py-0.5 rounded bg-slate-100 text-slate-700">{selectedPriority} Priority</span>}
            <button
              onClick={() => {
                setSelectedStatus('');
                setSelectedType('');
                setSelectedPriority('');
                setSearchTerm('');
              }}
              className="text-xs text-brand-600 hover:underline ml-auto font-medium"
            >
              Clear Filters
            </button>
          </div>
        )}
      </div>

      {/* Campaigns Directory List */}
      {loading ? (
        <div className="py-20 flex flex-col items-center justify-center space-y-3 bg-white rounded-2xl border border-slate-200">
          <RefreshCw className="w-8 h-8 text-brand-500 animate-spin" />
          <p className="text-sm font-medium text-slate-500">Loading campaign directory...</p>
        </div>
      ) : campaigns.length === 0 ? (
        <div className="py-16 text-center bg-white rounded-2xl border border-slate-200 p-8 space-y-4">
          <div className="w-12 h-12 rounded-2xl bg-slate-100 text-slate-400 mx-auto flex items-center justify-center">
            <Megaphone className="w-6 h-6" />
          </div>
          <div className="space-y-1">
            <h3 className="text-base font-bold text-slate-800">No Campaigns Found</h3>
            <p className="text-xs text-slate-500 max-w-sm mx-auto">
              {debouncedSearch || selectedStatus || selectedType || selectedPriority
                ? 'No campaigns matched your search filter criteria. Try resetting your filters.'
                : 'No campaigns have been created yet. Launch your first public communication campaign.'}
            </p>
          </div>
          {canCreate && (
            <Link
              to="/campaigns/new"
              className="inline-flex items-center gap-1.5 px-4 py-2 bg-emerald-600 text-white text-xs font-semibold rounded-xl hover:bg-emerald-700 transition"
            >
              <Plus className="w-3.5 h-3.5" />
              Create First Campaign
            </Link>
          )}
        </div>
      ) : (
        <div className="space-y-3">
          {campaigns.map((camp) => {
            const isOwner = canModifyCampaign(camp);
            const isDraftOrReview = camp.status === 'Draft' || camp.status === 'In Review';
            const isDraftOrArchived = camp.status === 'Draft' || camp.status === 'Archived';

            return (
              <div
                key={camp.id}
                className="bg-white rounded-2xl border border-slate-200 p-5 shadow-2xs hover:border-brand-300 hover:shadow-sm transition flex flex-col lg:flex-row lg:items-center justify-between gap-4"
              >
                {/* Left: Info & Badges */}
                <div className="space-y-2 flex-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className={`text-xs font-bold px-2.5 py-0.5 rounded-full border ${getStatusBadge(camp.status)}`}>
                      {camp.status}
                    </span>
                    <span className={`text-[11px] font-bold px-2 py-0.5 rounded-md border ${getPriorityBadge(camp.priority)}`}>
                      {camp.priority}
                    </span>
                    <span className="text-[11px] font-medium px-2 py-0.5 rounded bg-slate-100 text-slate-600">
                      {camp.campaign_type}
                    </span>
                  </div>

                  <Link
                    to={`/campaigns/${camp.id}`}
                    className="text-base font-bold text-slate-900 hover:text-brand-600 transition block"
                  >
                    {camp.name}
                  </Link>

                  {camp.objective && (
                    <p className="text-xs text-slate-500 line-clamp-1 max-w-2xl">{camp.objective}</p>
                  )}

                  {/* Metadata Chips Bar */}
                  <div className="flex items-center gap-4 text-xs text-slate-400 flex-wrap pt-1">
                    <span className="flex items-center gap-1 text-slate-600">
                      <Layers className="w-3.5 h-3.5 text-amber-500" />
                      <strong>{camp.segments?.length || 0}</strong> segments
                    </span>
                    <span className="flex items-center gap-1 text-slate-600">
                      <Users className="w-3.5 h-3.5 text-blue-500" />
                      Reach: <strong>{camp.total_target_audience ?? 0}</strong> ({camp.confirmed_consent_audience ?? 0} confirmed opt-in)
                    </span>
                    <span className="flex items-center gap-1 text-slate-500">
                      Channels: <strong>{camp.channels?.join(', ')}</strong>
                    </span>
                    {camp.template_title && (
                      <span className="text-slate-500">
                        Template: <strong className="text-slate-700">{camp.template_title}</strong>
                      </span>
                    )}
                  </div>
                </div>

                {/* Right: Actions */}
                <div className="flex items-center gap-2 self-start lg:self-center border-t lg:border-t-0 pt-3 lg:pt-0 w-full lg:w-auto justify-end">
                  <Link
                    to={`/campaigns/${camp.id}`}
                    className="inline-flex items-center gap-1 px-3 py-1.5 text-xs font-semibold rounded-xl bg-slate-100 text-slate-700 hover:bg-slate-200 transition"
                  >
                    <Eye className="w-3.5 h-3.5" /> View
                  </Link>

                  {isOwner && isDraftOrReview && (
                    <Link
                      to={`/campaigns/${camp.id}/edit`}
                      className="inline-flex items-center gap-1 px-3 py-1.5 text-xs font-semibold rounded-xl bg-white border border-slate-200 text-slate-700 hover:bg-slate-50 transition"
                    >
                      <Edit2 className="w-3.5 h-3.5 text-slate-500" /> Edit
                    </Link>
                  )}

                  {isOwner && isDraftOrArchived && (
                    <button
                      onClick={() => {
                        setDeletingCampaign(camp);
                        setDeleteModalOpen(true);
                      }}
                      className="p-1.5 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition"
                      title="Delete campaign"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Pagination Footer */}
      {!loading && totalPages > 1 && (
        <div className="bg-white p-4 rounded-xl border border-slate-200 flex items-center justify-between text-xs text-slate-600">
          <span>
            Showing page <strong>{currentPage}</strong> of <strong>{totalPages}</strong> ({totalCount} total campaigns)
          </span>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
              disabled={currentPage === 1}
              className="p-1.5 border border-slate-200 rounded-lg hover:bg-slate-50 disabled:opacity-40 transition"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <span className="px-2 font-semibold text-slate-800">{currentPage}</span>
            <button
              onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
              disabled={currentPage === totalPages}
              className="p-1.5 border border-slate-200 rounded-lg hover:bg-slate-50 disabled:opacity-40 transition"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      <CampaignDeleteModal
        isOpen={deleteModalOpen}
        onClose={() => setDeleteModalOpen(false)}
        onSuccess={(msg) => {
          showToast(msg);
          fetchCampaigns();
        }}
        campaign={deletingCampaign}
      />

    </div>
  );
}

