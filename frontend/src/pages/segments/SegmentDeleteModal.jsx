import React, { useState } from 'react';
import { AlertTriangle, X } from 'lucide-react';
import { deleteSegment } from '../../services/segmentService';

export default function SegmentDeleteModal({ isOpen, onClose, segment, onSuccess }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  if (!isOpen || !segment) return null;

  const handleDelete = async () => {
    setLoading(true);
    setError('');
    try {
      await deleteSegment(segment.id);
      onSuccess(`Segment "${segment.name}" was successfully deleted.`);
      onClose();
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to delete segment.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="relative bg-white rounded-2xl max-w-md w-full shadow-2xl border border-slate-200 overflow-hidden">
        <div className="p-6">
          <div className="w-12 h-12 rounded-2xl bg-rose-100 text-rose-600 flex items-center justify-center mb-4">
            <AlertTriangle className="w-6 h-6" />
          </div>

          <h3 className="text-lg font-bold text-slate-900">Delete Audience Segment</h3>
          <p className="text-xs text-slate-500 mt-1">
            Are you sure you want to permanently delete the segment <strong>{segment.name}</strong>?
          </p>

          <p className="text-xs text-rose-600 font-medium mt-3 bg-rose-50 p-2.5 rounded-lg border border-rose-200">
            This action cannot be undone. Any campaigns linked to this segment will no longer have access to this rule definition.
          </p>

          {error && (
            <p className="text-xs text-rose-600 mt-2 bg-rose-50 p-2 rounded border border-rose-200">{error}</p>
          )}

          <div className="mt-6 flex items-center justify-end gap-3">
            <button
              type="button"
              onClick={onClose}
              disabled={loading}
              className="px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-100 border border-slate-300 rounded-lg transition"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleDelete}
              disabled={loading}
              className="px-5 py-2 text-xs font-semibold text-white bg-rose-600 hover:bg-rose-700 disabled:opacity-60 rounded-lg shadow-sm transition"
            >
              {loading ? 'Deleting...' : 'Confirm Delete'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

