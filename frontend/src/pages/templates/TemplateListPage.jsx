import React, { useState, useEffect, useCallback } from 'react';
import {
  FileText,
  Plus,
  Search,
  Filter,
  RefreshCw,
  Edit2,
  Trash2,
  Globe,
  Tag,
  Layers,
  ChevronLeft,
  ChevronRight,
  Sparkles,
  Info,
  CheckCircle2,
  AlertCircle
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { listTemplates, getTemplateCategories } from '../../services/templateService';
import TemplateFormModal from './TemplateFormModal';
import TemplateDeleteModal from './TemplateDeleteModal';

export default function TemplateListPage() {
  const { user, isAdmin, isCampaignManager } = useAuth();
  const canCreate = isAdmin || isCampaignManager;

  // Data State
  const [templates, setTemplates] = useState([]);
  const [totalCount, setTotalCount] = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [loading, setLoading] = useState(true);
  const [toastMessage, setToastMessage] = useState('');

  // Filters State
  const [categories, setCategories] = useState([]);
  const [selectedCategory, setSelectedCategory] = useState('');
  const [selectedLanguage, setSelectedLanguage] = useState('');
  const [searchTerm, setSearchTerm] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');

  // Modal State
  const [formModalOpen, setFormModalOpen] = useState(false);
  const [editingTemplate, setEditingTemplate] = useState(null);
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [deletingTemplate, setDeletingTemplate] = useState(null);

  // Debounce search
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(searchTerm);
      setCurrentPage(1);
    }, 300);
    return () => clearTimeout(timer);
  }, [searchTerm]);

  // Load categories metadata once
  useEffect(() => {
    getTemplateCategories()
      .then((data) => {
        if (data.categories) setCategories(data.categories);
      })
      .catch(() => {});
  }, []);

  const fetchTemplates = useCallback(async () => {
    setLoading(true);
    try {
      const params = {
        page: currentPage,
        page_size: pageSize,
      };
      if (debouncedSearch) params.search = debouncedSearch;
      if (selectedCategory) params.category = selectedCategory;
      if (selectedLanguage) params.language = selectedLanguage;

      const data = await listTemplates(params);
      setTemplates(data.items || []);
      setTotalCount(data.total || 0);
      setTotalPages(data.total_pages || 1);
    } catch (err) {
      showToast(err.response?.data?.detail || 'Failed to load templates.');
    } finally {
      setLoading(false);
    }
  }, [currentPage, pageSize, debouncedSearch, selectedCategory, selectedLanguage]);

  useEffect(() => {
    fetchTemplates();
  }, [fetchTemplates]);

  const showToast = (msg) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(''), 4500);
  };

  const canModifyTemplate = (tmpl) => {
    if (isAdmin) return true;
    if (isCampaignManager && tmpl.created_by === user?.id) return true;
    return false;
  };

  const getCategoryBadgeClass = (category) => {
    switch (category) {
      case 'Healthcare':
        return 'bg-emerald-50 text-emerald-700 border-emerald-200';
      case 'Emergency Alert':
      case 'Disaster Management':
        return 'bg-rose-50 text-rose-700 border-rose-200';
      case 'Civic Education':
        return 'bg-blue-50 text-blue-700 border-blue-200';
      case 'Public Governance':
        return 'bg-purple-50 text-purple-700 border-purple-200';
      case 'Community Outreach':
      default:
        return 'bg-amber-50 text-amber-700 border-amber-200';
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      
      {/* Toast Notification */}
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
            <div className="w-8 h-8 rounded-lg bg-brand-100 text-brand-600 flex items-center justify-center">
              <FileText className="w-4 h-4" />
            </div>
            <h1 className="text-xl sm:text-2xl font-extrabold text-slate-900 tracking-tight">
              Communication Template Library
            </h1>
          </div>
          <p className="text-sm text-slate-600 max-w-2xl">
            Create, manage, and standardize public awareness messages with dynamic citizen variables for multi-channel broadcasting.
          </p>
        </div>

        {canCreate && (
          <button
            onClick={() => {
              setEditingTemplate(null);
              setFormModalOpen(true);
            }}
            className="inline-flex items-center gap-2 px-4 py-2.5 bg-brand-600 hover:bg-brand-700 text-white text-sm font-semibold rounded-xl shadow-sm hover:shadow-brand-500/25 transition active:scale-[0.98] whitespace-nowrap"
          >
            <Plus className="w-4 h-4" />
            New Template
          </button>
        )}
      </div>

      {/* Search & Filter Bar */}
      <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-2xs space-y-3">
        <div className="grid grid-cols-1 sm:grid-cols-12 gap-3">
          
          {/* Search Input */}
          <div className="sm:col-span-6 relative">
            <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-3 pointer-events-none" />
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Search templates by headline title, content body, or tags..."
              className="w-full pl-9 pr-4 py-2 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 focus:bg-white transition"
            />
          </div>

          {/* Category Filter */}
          <div className="sm:col-span-3">
            <select
              value={selectedCategory}
              onChange={(e) => {
                setSelectedCategory(e.target.value);
                setCurrentPage(1);
              }}
              className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 focus:bg-white transition"
            >
              <option value="">All Categories</option>
              {categories.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </div>

          {/* Language Filter */}
          <div className="sm:col-span-2">
            <select
              value={selectedLanguage}
              onChange={(e) => {
                setSelectedLanguage(e.target.value);
                setCurrentPage(1);
              }}
              className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 focus:bg-white transition"
            >
              <option value="">All Languages</option>
              <option value="en">English (en)</option>
              <option value="hi">Hindi (hi)</option>
              <option value="ta">Tamil (ta)</option>
              <option value="te">Telugu (te)</option>
              <option value="bn">Bengali (bn)</option>
              <option value="mr">Marathi (mr)</option>
            </select>
          </div>

          {/* Refresh Button */}
          <div className="sm:col-span-1 flex justify-end">
            <button
              onClick={fetchTemplates}
              title="Refresh templates"
              className="w-full sm:w-auto p-2 text-slate-500 hover:text-brand-600 hover:bg-slate-100 border border-slate-200 rounded-xl transition flex items-center justify-center"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            </button>
          </div>
        </div>

        {/* Active Filters Summary */}
        {(selectedCategory || selectedLanguage || debouncedSearch) && (
          <div className="flex items-center gap-2 pt-2 border-t border-slate-100 text-xs text-slate-500">
            <span>Filtered by:</span>
            {debouncedSearch && (
              <span className="px-2 py-0.5 rounded bg-slate-100 text-slate-700 font-medium">
                "{debouncedSearch}"
              </span>
            )}
            {selectedCategory && (
              <span className="px-2 py-0.5 rounded bg-brand-50 text-brand-700 font-medium">
                {selectedCategory}
              </span>
            )}
            {selectedLanguage && (
              <span className="px-2 py-0.5 rounded bg-slate-100 text-slate-700 font-medium uppercase">
                {selectedLanguage}
              </span>
            )}
            <button
              onClick={() => {
                setSelectedCategory('');
                setSelectedLanguage('');
                setSearchTerm('');
              }}
              className="text-xs text-brand-600 hover:underline ml-auto font-medium"
            >
              Clear Filters
            </button>
          </div>
        )}
      </div>

      {/* Templates Grid List */}
      {loading ? (
        <div className="py-20 flex flex-col items-center justify-center space-y-3 bg-white rounded-2xl border border-slate-200">
          <RefreshCw className="w-8 h-8 text-brand-500 animate-spin" />
          <p className="text-sm font-medium text-slate-500">Loading communication templates...</p>
        </div>
      ) : templates.length === 0 ? (
        <div className="py-16 text-center bg-white rounded-2xl border border-slate-200 p-8 space-y-4">
          <div className="w-12 h-12 rounded-2xl bg-slate-100 text-slate-400 mx-auto flex items-center justify-center">
            <FileText className="w-6 h-6" />
          </div>
          <div className="space-y-1">
            <h3 className="text-base font-bold text-slate-800">No Templates Found</h3>
            <p className="text-xs text-slate-500 max-w-sm mx-auto">
              {debouncedSearch || selectedCategory || selectedLanguage
                ? 'No templates matched your search criteria. Try clearing active filters.'
                : 'No templates have been authored yet. Seed standard templates or create a new one.'}
            </p>
          </div>
          {canCreate && (
            <button
              onClick={() => {
                setEditingTemplate(null);
                setFormModalOpen(true);
              }}
              className="inline-flex items-center gap-1.5 px-4 py-2 bg-brand-600 text-white text-xs font-semibold rounded-xl hover:bg-brand-700 transition"
            >
              <Plus className="w-3.5 h-3.5" />
              Create First Template
            </button>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {templates.map((tmpl) => {
            const isOwner = canModifyTemplate(tmpl);
            return (
              <div
                key={tmpl.id}
                className="bg-white rounded-2xl border border-slate-200 p-5 shadow-2xs hover:border-brand-300 hover:shadow-sm transition flex flex-col justify-between space-y-4"
              >
                {/* Card Top: Badges & Actions */}
                <div className="space-y-2">
                  <div className="flex items-start justify-between gap-2">
                    <span
                      className={`text-xs font-bold px-2.5 py-0.5 rounded-full border ${getCategoryBadgeClass(
                        tmpl.category
                      )}`}
                    >
                      {tmpl.category}
                    </span>

                    <div className="flex items-center gap-1">
                      <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-slate-100 text-slate-600 uppercase font-semibold">
                        {tmpl.language}
                      </span>
                      {isOwner && (
                        <div className="flex items-center gap-0.5 ml-1">
                          <button
                            onClick={() => {
                              setEditingTemplate(tmpl);
                              setFormModalOpen(true);
                            }}
                            title="Edit template"
                            className="p-1.5 text-slate-400 hover:text-brand-600 hover:bg-brand-50 rounded-lg transition"
                          >
                            <Edit2 className="w-3.5 h-3.5" />
                          </button>
                          <button
                            onClick={() => {
                              setDeletingTemplate(tmpl);
                              setDeleteModalOpen(true);
                            }}
                            title="Delete template"
                            className="p-1.5 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Headline Title */}
                  <h3 className="text-base font-bold text-slate-900 line-clamp-1">{tmpl.title}</h3>
                </div>

                {/* Body Preview */}
                <div className="bg-slate-50/70 p-3 rounded-xl border border-slate-100 text-xs text-slate-700 leading-relaxed font-normal line-clamp-3">
                  {tmpl.body}
                </div>

                {/* Card Bottom: Placeholders & Creator */}
                <div className="space-y-2.5 pt-2 border-t border-slate-100 text-xs">
                  {/* Dynamic Variables */}
                  {tmpl.placeholders && tmpl.placeholders.length > 0 && (
                    <div className="flex items-center gap-1.5 flex-wrap">
                      <span className="text-[11px] text-slate-400 flex items-center gap-1">
                        <Sparkles className="w-3 h-3 text-brand-600" /> Variables:
                      </span>
                      {tmpl.placeholders.map((ph) => (
                        <span
                          key={ph}
                          className="px-1.5 py-0.5 rounded bg-emerald-50 text-emerald-700 border border-emerald-200 font-mono text-[10px]"
                        >
                          {ph}
                        </span>
                      ))}
                    </div>
                  )}

                  {/* Creator and Tags */}
                  <div className="flex items-center justify-between text-[11px] text-slate-400 pt-1">
                    <span>
                      By <strong className="text-slate-600 font-medium">{tmpl.creator_name || `User #${tmpl.created_by}`}</strong>
                    </span>
                    {tmpl.tags && (
                      <span className="flex items-center gap-1 text-slate-500 line-clamp-1 max-w-[180px]">
                        <Tag className="w-3 h-3 text-slate-400" />
                        {tmpl.tags}
                      </span>
                    )}
                  </div>
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
            Showing page <strong>{currentPage}</strong> of <strong>{totalPages}</strong> ({totalCount} total templates)
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

      {/* Modals */}
      <TemplateFormModal
        isOpen={formModalOpen}
        onClose={() => setFormModalOpen(false)}
        onSuccess={(msg) => {
          showToast(msg);
          fetchTemplates();
        }}
        template={editingTemplate}
      />

      <TemplateDeleteModal
        isOpen={deleteModalOpen}
        onClose={() => setDeleteModalOpen(false)}
        onSuccess={(msg) => {
          showToast(msg);
          fetchTemplates();
        }}
        template={deletingTemplate}
      />

    </div>
  );
}

