import React, { useState } from 'react';
import { Trash2, AlertTriangle, X } from 'lucide-react';
import { deleteTemplate } from '../../services/templateService';

export default function TemplateDeleteModal({ isOpen, onClose, onSuccess, template }) {
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState('');

  if (!isOpen || !template) return null;

  const handleDelete = async () => {
    setDeleting(true);
    setError('');
    try {
      await deleteTemplate(template.id);
      onSuccess(`Template '${template.title}' was deleted successfully.`);
      onClose();
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to delete template.');
    } finally {
      setDeleting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-sm">
      <div className="relative w-full max-w-md bg-white rounded-2xl shadow-xl border border-slate-200 overflow-hidden">
        
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100 bg-rose-50/50">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-rose-100 text-rose-600 flex items-center justify-center">
              <Trash2 className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-slate-900">Delete Template</h2>
              <p className="text-xs text-rose-600 font-medium">Permanent Action</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 text-slate-400 hover:text-slate-600 rounded-lg hover:bg-slate-100 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-4">
          {error && (
            <div className="p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-xs">
              {error}
            </div>
          )}

          <p className="text-sm text-slate-600 leading-relaxed">
            Are you sure you want to permanently delete the communication template:
          </p>

          <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200 space-y-1">
            <p className="text-sm font-bold text-slate-900">{template.title}</p>
            <div className="flex items-center gap-2 text-xs text-slate-500">
              <span>Category: <strong className="text-slate-700">{template.category}</strong></span>
              <span>•</span>
              <span>Language: <strong className="text-slate-700 uppercase">{template.language}</strong></span>
            </div>
          </div>

          <div className="flex items-start gap-2.5 p-3 rounded-xl bg-amber-50 border border-amber-200 text-amber-800 text-xs">
            <AlertTriangle className="w-4 h-4 text-amber-600 flex-shrink-0 mt-0.5" />
            <span>
              Any draft campaigns referencing this template will retain their configuration, but their linked template reference will be reset to unassigned.
            </span>
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-4 bg-slate-50 border-t border-slate-100 flex items-center justify-end gap-3">
          <button
            type="button"
            onClick={onClose}
            disabled={deleting}
            className="px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-200/60 rounded-xl transition"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleDelete}
            disabled={deleting}
            className="px-5 py-2 text-sm font-semibold text-white bg-rose-600 hover:bg-rose-700 rounded-xl shadow-sm hover:shadow-rose-500/25 transition disabled:opacity-50"
          >
            {deleting ? 'Deleting...' : 'Confirm Delete'}
          </button>
        </div>

      </div>
    </div>
  );
}

