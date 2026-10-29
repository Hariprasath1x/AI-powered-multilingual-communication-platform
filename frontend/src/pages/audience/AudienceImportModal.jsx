import React, { useState, useRef } from 'react';
import {
  X,
  Upload,
  FileSpreadsheet,
  AlertCircle,
  CheckCircle2,
  AlertTriangle,
  Download,
  RefreshCw,
  Info
} from 'lucide-react';
import { importAudienceFile } from '../../services/audienceService';

export default function AudienceImportModal({ isOpen, onClose, onSuccess }) {
  const [selectedFile, setSelectedFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [importSummary, setImportSummary] = useState(null);
  const [errorMessage, setErrorMessage] = useState('');
  const fileInputRef = useRef(null);

  if (!isOpen) return null;

  const handleFileChange = (e) => {
    const file = e.target.files[0];
    if (file) {
      const fn = file.name.toLowerCase();
      if (!fn.endsWith('.csv') && !fn.endsWith('.xlsx')) {
        if (fn.endsWith('.xls')) {
          setErrorMessage('Legacy Excel format (.xls) is not supported. Please convert your file to modern Excel (.xlsx) or CSV (.csv).');
        } else {
          setErrorMessage('Unsupported format. Please select a CSV (.csv) or modern Excel (.xlsx) spreadsheet.');
        }
        setSelectedFile(null);
        return;
      }
      setSelectedFile(file);
      setErrorMessage('');
      setImportSummary(null);
    }
  };

  const handleDownloadSampleCsv = () => {
    const sampleCsvContent = `name,email,phone,age,gender,city,state,preferred_language,preferred_channel,occupation,department,consent
Anita Desai,anita.desai@agency.gov.in,+91 98765 11111,35,Female,Mumbai,Maharashtra,mr,Email,Chief Medical Officer,Public Health,true
Ramesh Patel,ramesh.patel@agency.gov.in,+91 98765 22222,42,Male,Ahmedabad,Gujarat,gu,SMS,Logistics Officer,Emergency Relief,true
Pooja Verma,pooja.verma@agency.gov.in,+91 98765 33333,28,Female,New Delhi,Delhi,hi,WhatsApp,Public Relations,Communication,true
Karthik Raj,karthik.raj@agency.gov.in,+91 98765 44444,31,Male,Chennai,Tamil Nadu,ta,Email,Systems Admin,IT Infrastructure,true
`;
    const blob = new Blob([sampleCsvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', 'masscommai_audience_sample.csv');
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!selectedFile) {
      setErrorMessage('Please select a CSV or Excel file to upload.');
      return;
    }

    setLoading(true);
    setErrorMessage('');

    try {
      const summary = await importAudienceFile(selectedFile);
      setImportSummary(summary);
      if (summary.successful_imports > 0) {
        onSuccess(`Import complete: ${summary.successful_imports} new recipients added.`);
      }
    } catch (err) {
      const detail = err.response?.data?.detail;
      setErrorMessage(typeof detail === 'string' ? detail : err.message || 'Import failed.');
    } finally {
      setLoading(false);
    }
  };

  const handleReset = () => {
    setSelectedFile(null);
    setImportSummary(null);
    setErrorMessage('');
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="relative bg-white rounded-2xl max-w-3xl w-full shadow-2xl border border-slate-200 overflow-hidden my-8">
        
        {/* Header */}
        <div className="px-6 py-4 bg-slate-50 border-b border-slate-200 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-brand-100 text-brand-700 flex items-center justify-center">
              <FileSpreadsheet className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-lg font-bold text-slate-900">Bulk Audience Import</h3>
              <p className="text-xs text-slate-500">Upload CSV or Excel files with row-by-row validation & duplicate checking.</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-200 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Body */}
        <div className="p-6 space-y-6">
          {errorMessage && (
            <div className="p-3.5 bg-rose-50 border border-rose-200 rounded-xl flex items-start gap-2.5 text-xs text-rose-700">
              <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5 text-rose-500" />
              <span>{errorMessage}</span>
            </div>
          )}

          {!importSummary ? (
            /* Upload State */
            <form onSubmit={handleSubmit} className="space-y-6">
              {/* File Dropzone */}
              <div
                onClick={() => fileInputRef.current?.click()}
                className="border-2 border-dashed border-slate-300 hover:border-brand-500 rounded-2xl p-8 text-center cursor-pointer bg-slate-50 hover:bg-brand-50/20 transition flex flex-col items-center justify-center"
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".csv,.xlsx"
                  onChange={handleFileChange}
                  className="hidden"
                />
                <div className="w-12 h-12 rounded-2xl bg-brand-100 text-brand-600 flex items-center justify-center mb-3">
                  <Upload className="w-6 h-6" />
                </div>
                {selectedFile ? (
                  <div>
                    <p className="text-sm font-semibold text-slate-900">{selectedFile.name}</p>
                    <p className="text-xs text-slate-500 mt-0.5">
                      {(selectedFile.size / 1024).toFixed(1)} KB • Ready to upload
                    </p>
                  </div>
                ) : (
                  <div>
                    <p className="text-sm font-semibold text-slate-800">
                      Click or drag and drop your spreadsheet here
                    </p>
                    <p className="text-xs text-slate-500 mt-1">
                      Supports CSV (.csv) or modern Microsoft Excel (.xlsx) up to 10MB (legacy .xls not supported)
                    </p>
                  </div>
                )}
              </div>

              {/* Sample Template & Format Tips */}
              <div className="p-4 bg-slate-50 rounded-xl border border-slate-200 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 text-xs">
                <div className="flex items-start gap-2 text-slate-600">
                  <Info className="w-4 h-4 text-brand-600 flex-shrink-0 mt-0.5" />
                  <span>
                    Supported columns: <strong>name</strong>, <strong>email</strong>, <strong>phone</strong>, <strong>age</strong>, <strong>gender</strong>, <strong>city</strong>, <strong>state</strong>, <strong>preferred_language</strong>, <strong>preferred_channel</strong>.
                  </span>
                </div>
                <button
                  type="button"
                  onClick={handleDownloadSampleCsv}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-white border border-slate-300 rounded-lg text-slate-700 font-medium hover:bg-slate-100 transition flex-shrink-0"
                >
                  <Download className="w-3.5 h-3.5" />
                  Sample CSV
                </button>
              </div>

              {/* Action Buttons */}
              <div className="pt-2 flex items-center justify-end gap-3">
                <button
                  type="button"
                  onClick={onClose}
                  className="px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-100 border border-slate-300 rounded-lg transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={!selectedFile || loading}
                  className="inline-flex items-center gap-2 px-5 py-2 text-xs font-semibold text-white bg-brand-600 hover:bg-brand-700 disabled:opacity-50 rounded-lg shadow-sm transition"
                >
                  {loading && <RefreshCw className="w-3.5 h-3.5 animate-spin" />}
                  {loading ? 'Processing File...' : 'Start Import'}
                </button>
              </div>
            </form>
          ) : (
            /* Results Reconciliation View */
            <div className="space-y-6">
              {/* Metric Summary Cards */}
              <div className="grid grid-cols-2 sm:grid-cols-5 gap-2.5">
                <div className="p-3 rounded-xl border border-slate-200 bg-slate-50 text-center">
                  <span className="text-[10px] font-medium text-slate-500 uppercase tracking-wider">Total Rows</span>
                  <p className="text-xl font-bold text-slate-900 mt-1">{importSummary.total_rows}</p>
                </div>
                <div className="p-3 rounded-xl border border-emerald-200 bg-emerald-50 text-center">
                  <span className="text-[10px] font-semibold text-emerald-700 uppercase tracking-wider">Imported</span>
                  <p className="text-xl font-bold text-emerald-800 mt-1">{importSummary.successful_imports}</p>
                </div>
                <div className="p-3 rounded-xl border border-amber-200 bg-amber-50 text-center">
                  <span className="text-[10px] font-semibold text-amber-700 uppercase tracking-wider">Duplicates</span>
                  <p className="text-xl font-bold text-amber-800 mt-1">{importSummary.duplicate_count}</p>
                </div>
                <div className="p-3 rounded-xl border border-rose-200 bg-rose-50 text-center">
                  <span className="text-[10px] font-semibold text-rose-700 uppercase tracking-wider">Rejected</span>
                  <p className="text-xl font-bold text-rose-800 mt-1">{importSummary.rejected_count}</p>
                </div>
                <div className="p-3 rounded-xl border border-slate-200 bg-slate-50 text-center">
                  <span className="text-[10px] font-semibold text-slate-600 uppercase tracking-wider">Unconfirmed</span>
                  <p className="text-xl font-bold text-slate-800 mt-1">{importSummary.unspecified_consent_count || 0}</p>
                </div>
              </div>

              {/* Status Message */}
              {importSummary.successful_imports > 0 && importSummary.rejected_count === 0 && importSummary.duplicate_count === 0 ? (
                <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-xl flex items-center gap-2.5 text-xs text-emerald-800">
                  <CheckCircle2 className="w-5 h-5 text-emerald-600 flex-shrink-0" />
                  <span>All <strong>{importSummary.successful_imports}</strong> audience members were imported successfully!</span>
                </div>
              ) : importSummary.errors.length > 0 ? (
                <div>
                  <h4 className="text-xs font-bold text-slate-800 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                    <AlertTriangle className="w-4 h-4 text-amber-500" />
                    Row Rejection & Duplicate Audit Log ({importSummary.errors.length})
                  </h4>
                  <div className="max-h-60 overflow-y-auto border border-slate-200 rounded-xl">
                    <table className="min-w-full divide-y divide-slate-200 text-xs">
                      <thead className="bg-slate-50 sticky top-0">
                        <tr>
                          <th className="px-3 py-2 text-left font-semibold text-slate-600">Row</th>
                          <th className="px-3 py-2 text-left font-semibold text-slate-600">Name / Handle</th>
                          <th className="px-3 py-2 text-left font-semibold text-slate-600">Type</th>
                          <th className="px-3 py-2 text-left font-semibold text-slate-600">Reconciliation Reason</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100 bg-white">
                        {importSummary.errors.map((err, idx) => (
                          <tr key={idx} className="hover:bg-slate-50/80">
                            <td className="px-3 py-2 font-mono text-slate-500">#{err.row_number}</td>
                            <td className="px-3 py-2 font-medium text-slate-900">
                              {err.name || err.email || err.phone || 'Unnamed Row'}
                            </td>
                            <td className="px-3 py-2">
                              <span
                                className={`px-2 py-0.5 rounded text-[10px] font-semibold ${
                                  err.error_type === 'duplicate'
                                    ? 'bg-amber-100 text-amber-800 border border-amber-200'
                                    : 'bg-rose-100 text-rose-800 border border-rose-200'
                                }`}
                              >
                                {err.error_type === 'duplicate' ? 'Duplicate' : 'Validation Error'}
                              </span>
                            </td>
                            <td className="px-3 py-2 text-slate-600">{err.reason}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              ) : null}

              {/* Completion Action */}
              <div className="pt-2 flex items-center justify-between border-t border-slate-200">
                <button
                  type="button"
                  onClick={handleReset}
                  className="px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-100 border border-slate-300 rounded-lg transition"
                >
                  Import Another File
                </button>
                <button
                  type="button"
                  onClick={onClose}
                  className="px-5 py-2 text-xs font-semibold text-white bg-brand-600 hover:bg-brand-700 rounded-lg shadow-sm transition"
                >
                  Done
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

