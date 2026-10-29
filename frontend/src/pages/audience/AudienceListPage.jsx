import React, { useState, useEffect, useCallback } from 'react';
import {
  Users,
  UserPlus,
  Upload,
  Search,
  Filter,
  RefreshCw,
  Edit2,
  Trash2,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Mail,
  Phone,
  MapPin,
  Globe,
  SlidersHorizontal,
  ChevronLeft,
  ChevronRight,
  ShieldCheck,
  Building,
  Briefcase
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { listAudience, getAudienceStats } from '../../services/audienceService';
import AudienceFormModal from './AudienceFormModal';
import AudienceImportModal from './AudienceImportModal';
import AudienceDeleteModal from './AudienceDeleteModal';

export default function AudienceListPage() {
  const { user, isAdmin, isCampaignManager, isCommTeam } = useAuth();
  const canManageAudience = isAdmin || isCampaignManager;

  // Data & Stats State
  const [audienceList, setAudienceList] = useState([]);
  const [stats, setStats] = useState(null);
  const [totalCount, setTotalCount] = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [loading, setLoading] = useState(true);
  const [toastMessage, setToastMessage] = useState('');

  // Filters State
  const [searchTerm, setSearchTerm] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [selectedLanguage, setSelectedLanguage] = useState('');
  const [selectedChannel, setSelectedChannel] = useState('');
  const [selectedConsent, setSelectedConsent] = useState('');

  // Modals State
  const [formModalOpen, setFormModalOpen] = useState(false);
  const [editingMember, setEditingMember] = useState(null);
  const [importModalOpen, setImportModalOpen] = useState(false);
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [deletingMember, setDeletingMember] = useState(null);

  // Debounce search input
  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedSearch(searchTerm);
      setCurrentPage(1);
    }, 350);
    return () => clearTimeout(handler);
  }, [searchTerm]);

  const loadStats = useCallback(async () => {
    try {
      const statsData = await getAudienceStats();
      setStats(statsData);
    } catch (err) {
      console.error('Failed to load audience stats:', err);
    }
  }, []);

  const loadAudience = useCallback(async () => {
    setLoading(true);
    try {
      const params = {
        page: currentPage,
        page_size: pageSize,
      };
      if (debouncedSearch.trim()) params.search = debouncedSearch.trim();
      if (selectedLanguage) params.preferred_language = selectedLanguage;
      if (selectedChannel) params.preferred_channel = selectedChannel;
      if (selectedConsent) params.consent_status = selectedConsent;

      const data = await listAudience(params);
      setAudienceList(data.items);
      setTotalCount(data.total);
      setTotalPages(data.total_pages);
    } catch (err) {
      console.error('Failed to fetch audience list:', err);
    } finally {
      setLoading(false);
    }
  }, [currentPage, pageSize, debouncedSearch, selectedLanguage, selectedChannel, selectedConsent]);

  useEffect(() => {
    loadAudience();
    loadStats();
  }, [loadAudience, loadStats]);

  const showToast = (msg) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(''), 4500);
  };

  const handleOpenCreate = () => {
    setEditingMember(null);
    setFormModalOpen(true);
  };

  const handleOpenEdit = (member) => {
    setEditingMember(member);
    setFormModalOpen(true);
  };

  const handleOpenDelete = (member) => {
    setDeletingMember(member);
    setDeleteModalOpen(true);
  };

  const handleResetFilters = () => {
    setSearchTerm('');
    setSelectedLanguage('');
    setSelectedChannel('');
    setSelectedConsent('');
    setCurrentPage(1);
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      
      {/* Toast Notification */}
      {toastMessage && (
        <div className="fixed top-20 right-6 z-50 p-4 bg-slate-900 text-white rounded-xl shadow-xl flex items-center gap-2.5 text-xs animate-in fade-in slide-in-from-top-4">
          <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          <span>{toastMessage}</span>
        </div>
      )}

      {/* Header Bar */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="w-10 h-10 rounded-xl bg-brand-600 text-white flex items-center justify-center shadow-sm">
              <Users className="w-5 h-5" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Audience Database</h1>
              <p className="text-xs text-slate-500">
                Manage public citizen profiles, communication channels, and multilingual preferences.
              </p>
            </div>
          </div>
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-2.5 flex-wrap">
          {!canManageAudience && (
            <span className="px-3 py-1.5 bg-amber-50 text-amber-800 border border-amber-200 rounded-lg text-xs font-semibold flex items-center gap-1.5">
              <ShieldCheck className="w-3.5 h-3.5" />
              View-only Mode (Communication Team)
            </span>
          )}

          {canManageAudience && (
            <>
              <button
                onClick={() => setImportModalOpen(true)}
                className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-semibold text-slate-700 bg-white hover:bg-slate-50 border border-slate-300 rounded-lg shadow-sm transition"
              >
                <Upload className="w-4 h-4 text-slate-500" />
                Import CSV / Excel
              </button>

              <button
                onClick={handleOpenCreate}
                className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-semibold text-white bg-brand-600 hover:bg-brand-700 rounded-lg shadow-sm transition active:scale-[0.98]"
              >
                <UserPlus className="w-4 h-4" />
                Add Recipient
              </button>
            </>
          )}
        </div>
      </div>

      {/* Aggregate Metric Cards */}
      {stats && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="p-4 bg-white rounded-xl border border-slate-200 shadow-sm">
            <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Total Recipients</span>
            <p className="text-2xl font-bold text-slate-900 mt-1">{stats.total_members}</p>
            <p className="text-[11px] text-slate-500 mt-0.5">Database contact registry</p>
          </div>

          <div className="p-4 bg-white rounded-xl border border-slate-200 shadow-sm">
            <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Active Consent</span>
            <p className="text-2xl font-bold text-emerald-600 mt-1">
              {stats.total_members > 0 ? `${Math.round((stats.active_consent_count / stats.total_members) * 100)}%` : '0%'}
            </p>
            <p className="text-[10px] text-slate-500 mt-0.5">
              {stats.active_consent_count} opt-in • {stats.opt_out_count || 0} opt-out • {stats.unspecified_consent_count || 0} unconfirmed
            </p>
          </div>

          <div className="p-4 bg-white rounded-xl border border-slate-200 shadow-sm">
            <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Top Languages</span>
            <div className="flex flex-wrap gap-1 mt-1.5">
              {Object.entries(stats.language_distribution || {}).slice(0, 4).map(([code, count]) => (
                <span key={code} className="px-2 py-0.5 bg-blue-50 text-blue-800 text-[10px] font-semibold rounded border border-blue-200">
                  {code.toUpperCase()}: {count}
                </span>
              ))}
            </div>
          </div>

          <div className="p-4 bg-white rounded-xl border border-slate-200 shadow-sm">
            <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Channels</span>
            <div className="flex flex-wrap gap-1 mt-1.5">
              {Object.entries(stats.channel_distribution || {}).map(([ch, count]) => (
                <span key={ch} className="px-2 py-0.5 bg-slate-100 text-slate-800 text-[10px] font-semibold rounded border border-slate-200">
                  {ch}: {count}
                </span>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Filter and Search Bar */}
      <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm flex flex-col md:flex-row items-center justify-between gap-3">
        {/* Search */}
        <div className="relative w-full md:w-80">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Search name, email, phone, city..."
            className="w-full pl-9 pr-3 py-2 text-xs rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
        </div>

        {/* Filter Controls */}
        <div className="flex items-center gap-2 w-full md:w-auto flex-wrap">
          {/* Language Filter */}
          <select
            value={selectedLanguage}
            onChange={(e) => {
              setSelectedLanguage(e.target.value);
              setCurrentPage(1);
            }}
            className="px-2.5 py-2 text-xs rounded-lg border border-slate-300 bg-white text-slate-700 focus:outline-none focus:ring-2 focus:ring-brand-500"
          >
            <option value="">All Languages</option>
            <option value="en">English (en)</option>
            <option value="hi">Hindi (hi)</option>
            <option value="ta">Tamil (ta)</option>
            <option value="te">Telugu (te)</option>
            <option value="mr">Marathi (mr)</option>
            <option value="gu">Gujarati (gu)</option>
            <option value="kn">Kannada (kn)</option>
            <option value="bn">Bengali (bn)</option>
            <option value="ml">Malayalam (ml)</option>
            <option value="pa">Punjabi (pa)</option>
          </select>

          {/* Channel Filter */}
          <select
            value={selectedChannel}
            onChange={(e) => {
              setSelectedChannel(e.target.value);
              setCurrentPage(1);
            }}
            className="px-2.5 py-2 text-xs rounded-lg border border-slate-300 bg-white text-slate-700 focus:outline-none focus:ring-2 focus:ring-brand-500"
          >
            <option value="">All Channels</option>
            <option value="Email">Email</option>
            <option value="SMS">SMS</option>
            <option value="WhatsApp">WhatsApp</option>
          </select>

          {/* Consent Status Filter */}
          <select
            value={selectedConsent}
            onChange={(e) => {
              setSelectedConsent(e.target.value);
              setCurrentPage(1);
            }}
            className="px-2.5 py-2 text-xs rounded-lg border border-slate-300 bg-white text-slate-700 focus:outline-none focus:ring-2 focus:ring-brand-500"
          >
            <option value="">All Consent States</option>
            <option value="true">Consented (Opt-in)</option>
            <option value="unconfirmed">Unconfirmed / Pending</option>
            <option value="false">Explicitly Opted Out</option>
          </select>

          {(searchTerm || selectedLanguage || selectedChannel || selectedConsent) && (
            <button
              onClick={handleResetFilters}
              className="px-3 py-2 text-xs text-rose-600 hover:bg-rose-50 rounded-lg border border-rose-200 transition font-medium"
            >
              Clear
            </button>
          )}

          <button
            onClick={() => {
              loadAudience();
              loadStats();
            }}
            className="p-2 text-slate-500 hover:text-slate-800 hover:bg-slate-100 rounded-lg transition"
            title="Refresh database records"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin text-brand-600' : ''}`} />
          </button>
        </div>
      </div>

      {/* Main Audience Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        {loading && audienceList.length === 0 ? (
          <div className="p-12 text-center text-slate-500 space-y-2">
            <RefreshCw className="w-6 h-6 animate-spin mx-auto text-brand-600" />
            <p className="text-xs font-medium">Loading audience members...</p>
          </div>
        ) : audienceList.length === 0 ? (
          <div className="p-12 text-center text-slate-500 space-y-3">
            <Users className="w-10 h-10 mx-auto text-slate-300" />
            <div>
              <p className="text-sm font-semibold text-slate-800">No audience members found</p>
              <p className="text-xs text-slate-400 mt-1">
                {searchTerm || selectedLanguage || selectedChannel || selectedConsent
                  ? 'No recipients matched the selected search or filter criteria.'
                  : 'Start building your audience database by adding your first recipient or uploading a CSV.'}
              </p>
            </div>
            {canManageAudience && (
              <button
                onClick={handleOpenCreate}
                className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-semibold text-white bg-brand-600 hover:bg-brand-700 rounded-lg shadow-sm transition"
              >
                <UserPlus className="w-4 h-4" />
                Add First Recipient
              </button>
            )}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200 text-xs text-left">
              <thead className="bg-slate-50 text-slate-600 font-semibold uppercase tracking-wider text-[10px]">
                <tr>
                  <th className="px-4 py-3">Recipient</th>
                  <th className="px-4 py-3">Contact Handle</th>
                  <th className="px-4 py-3">Location & Dept</th>
                  <th className="px-4 py-3">Language</th>
                  <th className="px-4 py-3">Channel</th>
                  <th className="px-4 py-3">Consent</th>
                  {canManageAudience && <th className="px-4 py-3 text-right">Actions</th>}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 bg-white">
                {audienceList.map((member) => (
                  <tr key={member.id} className="hover:bg-slate-50/75 transition">
                    
                    {/* Recipient Identity */}
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2.5">
                        <div className="w-8 h-8 rounded-full bg-slate-100 text-slate-700 flex items-center justify-center font-bold text-xs flex-shrink-0">
                          {member.name.charAt(0).toUpperCase()}
                        </div>
                        <div>
                          <p className="font-semibold text-slate-900">{member.name}</p>
                          <p className="text-[10px] text-slate-400">
                            {member.occupation || 'Public Citizen'}
                            {member.age ? ` • Age ${member.age}` : ''}
                            {member.gender ? ` • ${member.gender}` : ''}
                          </p>
                        </div>
                      </div>
                    </td>

                    {/* Contact Info */}
                    <td className="px-4 py-3">
                      <div className="space-y-0.5">
                        {member.email && (
                          <div className="flex items-center gap-1.5 text-slate-700">
                            <Mail className="w-3 h-3 text-slate-400" />
                            <span>{member.email}</span>
                          </div>
                        )}
                        {member.phone && (
                          <div className="flex items-center gap-1.5 text-slate-600 font-mono text-[11px]">
                            <Phone className="w-3 h-3 text-slate-400" />
                            <span>{member.phone}</span>
                          </div>
                        )}
                      </div>
                    </td>

                    {/* Location & Organization */}
                    <td className="px-4 py-3">
                      <div className="space-y-0.5">
                        {(member.city || member.state) && (
                          <div className="flex items-center gap-1.5 text-slate-600">
                            <MapPin className="w-3 h-3 text-slate-400" />
                            <span>{[member.city, member.state].filter(Boolean).join(', ')}</span>
                          </div>
                        )}
                        {member.organization_department && (
                          <div className="flex items-center gap-1.5 text-slate-500 text-[10px]">
                            <Building className="w-3 h-3 text-slate-400" />
                            <span>{member.organization_department}</span>
                          </div>
                        )}
                      </div>
                    </td>

                    {/* Preferred Language */}
                    <td className="px-4 py-3">
                      <span className="px-2 py-0.5 bg-blue-50 text-blue-700 rounded border border-blue-200 font-semibold text-[10px] uppercase">
                        {member.preferred_language}
                      </span>
                    </td>

                    {/* Preferred Channel */}
                    <td className="px-4 py-3">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-semibold border ${
                        member.preferred_channel === 'WhatsApp'
                          ? 'bg-emerald-50 text-emerald-800 border-emerald-200'
                          : member.preferred_channel === 'SMS'
                          ? 'bg-amber-50 text-amber-800 border-amber-200'
                          : 'bg-indigo-50 text-indigo-800 border-indigo-200'
                      }`}>
                        {member.preferred_channel}
                      </span>
                    </td>

                    {/* Consent Pill */}
                    <td className="px-4 py-3">
                      {member.consent_status === true ? (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-100 text-emerald-800">
                          <CheckCircle2 className="w-3 h-3" />
                          Opted In
                        </span>
                      ) : member.consent_status === false ? (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-rose-100 text-rose-800">
                          <XCircle className="w-3 h-3" />
                          Opted Out
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-slate-100 text-slate-700">
                          <AlertCircle className="w-3 h-3" />
                          Unconfirmed
                        </span>
                      )}
                    </td>

                    {/* Actions */}
                    {canManageAudience && (
                      <td className="px-4 py-3 text-right">
                        <div className="inline-flex items-center gap-1">
                          <button
                            onClick={() => handleOpenEdit(member)}
                            className="p-1.5 text-slate-500 hover:text-brand-600 hover:bg-brand-50 rounded-lg transition"
                            title="Edit recipient details"
                          >
                            <Edit2 className="w-3.5 h-3.5" />
                          </button>
                          <button
                            onClick={() => handleOpenDelete(member)}
                            className="p-1.5 text-slate-500 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition"
                            title="Delete recipient"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </td>
                    )}

                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination Bar */}
        {totalCount > 0 && (
          <div className="px-4 py-3 bg-slate-50 border-t border-slate-200 flex flex-col sm:flex-row items-center justify-between gap-3 text-xs text-slate-600">
            <div>
              Showing <span className="font-semibold text-slate-900">{(currentPage - 1) * pageSize + 1}</span> to{' '}
              <span className="font-semibold text-slate-900">
                {Math.min(currentPage * pageSize, totalCount)}
              </span>{' '}
              of <span className="font-semibold text-slate-900">{totalCount}</span> recipients
            </div>

            <div className="flex items-center gap-3">
              {/* Page size dropdown */}
              <div className="flex items-center gap-1.5">
                <span className="text-[11px] text-slate-500">Per page:</span>
                <select
                  value={pageSize}
                  onChange={(e) => {
                    setPageSize(Number(e.target.value));
                    setCurrentPage(1);
                  }}
                  className="px-2 py-1 text-xs rounded border border-slate-300 bg-white text-slate-700"
                >
                  <option value={10}>10</option>
                  <option value={25}>25</option>
                  <option value={50}>50</option>
                </select>
              </div>

              {/* Prev / Next Controls */}
              <div className="flex items-center gap-1">
                <button
                  onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                  disabled={currentPage <= 1}
                  className="p-1.5 rounded border border-slate-300 text-slate-600 hover:bg-slate-100 disabled:opacity-40 transition"
                  title="Previous Page"
                >
                  <ChevronLeft className="w-4 h-4" />
                </button>
                <span className="px-2 text-xs font-medium text-slate-800">
                  {currentPage} / {totalPages || 1}
                </span>
                <button
                  onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                  disabled={currentPage >= totalPages}
                  className="p-1.5 rounded border border-slate-300 text-slate-600 hover:bg-slate-100 disabled:opacity-40 transition"
                  title="Next Page"
                >
                  <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Modals */}
      <AudienceFormModal
        isOpen={formModalOpen}
        onClose={() => setFormModalOpen(false)}
        member={editingMember}
        onSuccess={(msg) => {
          showToast(msg);
          loadAudience();
          loadStats();
        }}
      />

      <AudienceImportModal
        isOpen={importModalOpen}
        onClose={() => setImportModalOpen(false)}
        onSuccess={(msg) => {
          showToast(msg);
          loadAudience();
          loadStats();
        }}
      />

      <AudienceDeleteModal
        isOpen={deleteModalOpen}
        onClose={() => {
          setDeleteModalOpen(false);
          setDeletingMember(null);
        }}
        member={deletingMember}
        onSuccess={(msg) => {
          showToast(msg);
          loadAudience();
          loadStats();
        }}
      />

    </div>
  );
}

