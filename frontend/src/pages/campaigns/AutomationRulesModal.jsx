import React, { useState, useEffect } from 'react';
import {
  X,
  Plus,
  Play,
  Trash2,
  CheckCircle2,
  AlertCircle,
  Clock,
  Send,
  Zap,
  ArrowRight,
  ShieldCheck,
  RefreshCw,
} from 'lucide-react';
import {
  listAutomationRules,
  createAutomationRule,
  deleteAutomationRule,
  updateAutomationRule,
  getAutomationHistory,
  evaluateAutomationRules,
} from '../../services/campaignService';

export default function AutomationRulesModal({ isOpen, onClose, campaign }) {
  const [activeTab, setActiveTab] = useState('rules'); // 'rules' or 'history'
  const [rules, setRules] = useState([]);
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(false);
  const [evaluating, setEvaluating] = useState(false);
  const [error, setError] = useState(null);
  const [successMsg, setSuccessMsg] = useState(null);

  // New rule form state
  const [showAddForm, setShowAddForm] = useState(false);
  const [formData, setFormData] = useState({
    name: '',
    trigger_condition: 'message_not_opened',
    wait_hours: 24,
    action_type: 'send_reminder',
    action_channel: 'SMS',
    custom_message: '',
  });

  useEffect(() => {
    if (isOpen && campaign?.id) {
      loadData();
    }
  }, [isOpen, campaign?.id, activeTab]);

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);
      if (activeTab === 'rules') {
        const data = await listAutomationRules(campaign.id);
        setRules(data);
      } else {
        const histData = await getAutomationHistory(campaign.id);
        setHistory(histData);
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load automation data.');
    } finally {
      setLoading(false);
    }
  };

  const handleCreateRule = async (e) => {
    e.preventDefault();
    if (!formData.name.trim()) return;

    try {
      setLoading(true);
      setError(null);
      await createAutomationRule(campaign.id, {
        name: formData.name.trim(),
        trigger_condition: formData.trigger_condition,
        wait_hours: parseInt(formData.wait_hours, 10) || 24,
        action_type: formData.action_type,
        action_channel: formData.action_channel,
        custom_message: formData.custom_message.trim() || null,
        is_enabled: true,
      });
      setSuccessMsg('Automation rule created successfully.');
      setShowAddForm(false);
      setFormData({
        name: '',
        trigger_condition: 'message_not_opened',
        wait_hours: 24,
        action_type: 'send_reminder',
        action_channel: 'SMS',
        custom_message: '',
      });
      loadData();
      setTimeout(() => setSuccessMsg(null), 3000);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to create automation rule.');
    } finally {
      setLoading(false);
    }
  };

  const handleToggleRule = async (rule) => {
    try {
      await updateAutomationRule(campaign.id, rule.id, {
        is_enabled: !rule.is_enabled,
      });
      setRules((prev) =>
        prev.map((r) => (r.id === rule.id ? { ...r, is_enabled: !r.is_enabled } : r))
      );
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to toggle rule.');
    }
  };

  const handleDeleteRule = async (ruleId) => {
    if (!window.confirm('Are you sure you want to delete this automation rule?')) return;
    try {
      await deleteAutomationRule(campaign.id, ruleId);
      setRules((prev) => prev.filter((r) => r.id !== ruleId));
      setSuccessMsg('Rule deleted.');
      setTimeout(() => setSuccessMsg(null), 2000);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to delete rule.');
    }
  };

  const handleEvaluateNow = async () => {
    try {
      setEvaluating(true);
      setError(null);
      const res = await evaluateAutomationRules(campaign.id);
      setSuccessMsg(`Automation evaluated: ${res.executed_actions || 0} action(s) executed.`);
      if (activeTab === 'history') {
        loadData();
      }
      setTimeout(() => setSuccessMsg(null), 4000);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to trigger rule evaluation.');
    } finally {
      setEvaluating(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl border border-slate-200 w-full max-w-3xl overflow-hidden flex flex-col max-h-[90vh] animate-in fade-in duration-200">

        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-gradient-to-r from-slate-900 to-indigo-950 text-white">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-indigo-500/20 border border-indigo-400/30 flex items-center justify-center shadow-inner">
              <Zap className="w-5 h-5 text-indigo-300" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base font-bold tracking-tight">Automated Workflows & Rules</h2>
                <span className="text-[10px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded-full bg-indigo-500/30 text-indigo-200 border border-indigo-400/30">
                  Task 15
                </span>
              </div>
              <p className="text-xs text-slate-300">
                Trigger follow-ups, fallback reminders, and automated citizen engagement
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-white/10 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Tab Navigation */}
        <div className="border-b border-slate-200 px-6 flex items-center justify-between bg-slate-50">
          <div className="flex gap-4">
            <button
              onClick={() => setActiveTab('rules')}
              className={`py-3 px-1 text-xs font-semibold border-b-2 transition ${
                activeTab === 'rules'
                  ? 'border-indigo-600 text-indigo-600'
                  : 'border-transparent text-slate-500 hover:text-slate-700'
              }`}
            >
              Active Rules ({rules.length})
            </button>
            <button
              onClick={() => setActiveTab('history')}
              className={`py-3 px-1 text-xs font-semibold border-b-2 transition ${
                activeTab === 'history'
                  ? 'border-indigo-600 text-indigo-600'
                  : 'border-transparent text-slate-500 hover:text-slate-700'
              }`}
            >
              Execution History
            </button>
          </div>

          <div className="flex items-center gap-2 py-2">
            <button
              onClick={handleEvaluateNow}
              disabled={evaluating}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg bg-indigo-50 text-indigo-700 hover:bg-indigo-100 border border-indigo-200 transition"
            >
              <Play className={`w-3 h-3 ${evaluating ? 'animate-spin' : ''}`} />
              {evaluating ? 'Evaluating...' : 'Evaluate Rules Now'}
            </button>
            {activeTab === 'rules' && !showAddForm && (
              <button
                onClick={() => setShowAddForm(true)}
                className="inline-flex items-center gap-1 px-3 py-1.5 text-xs font-bold rounded-lg bg-indigo-600 text-white hover:bg-indigo-700 transition"
              >
                <Plus className="w-3.5 h-3.5" />
                Add Rule
              </button>
            )}
          </div>
        </div>

        {/* Body */}
        <div className="p-6 overflow-y-auto space-y-4 flex-1">
          {error && (
            <div className="bg-rose-50 border border-rose-200 rounded-xl p-3 flex items-center gap-2 text-rose-700 text-xs">
              <AlertCircle className="w-4 h-4 shrink-0 text-rose-500" />
              <span>{error}</span>
            </div>
          )}

          {successMsg && (
            <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-3 flex items-center gap-2 text-emerald-800 text-xs">
              <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-600" />
              <span>{successMsg}</span>
            </div>
          )}

          {/* Add Rule Form */}
          {showAddForm && (
            <form onSubmit={handleCreateRule} className="bg-indigo-50/50 border border-indigo-200 rounded-xl p-4 space-y-3">
              <div className="flex items-center justify-between">
                <h4 className="text-xs font-bold text-indigo-950 uppercase tracking-wider">
                  Visual If → Then Rule Builder
                </h4>
                <button
                  type="button"
                  onClick={() => setShowAddForm(false)}
                  className="text-slate-400 hover:text-slate-600 text-xs"
                >
                  Cancel
                </button>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Rule Name</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. 24h Unread SMS Follow-up"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  className="w-full text-xs px-3 py-2 border border-slate-300 rounded-lg focus:ring-1 focus:ring-indigo-500 bg-white"
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 p-3 bg-white rounded-lg border border-indigo-100">
                {/* IF block */}
                <div className="space-y-2">
                  <span className="text-[11px] font-bold text-indigo-600 uppercase tracking-wider block">
                    IF (Condition)
                  </span>
                  <div>
                    <label className="text-[11px] text-slate-600 block">Trigger When:</label>
                    <select
                      value={formData.trigger_condition}
                      onChange={(e) => setFormData({ ...formData, trigger_condition: e.target.value })}
                      className="w-full text-xs px-2.5 py-1.5 border border-slate-300 rounded-md bg-white mt-0.5"
                    >
                      <option value="message_not_opened">Message Not Opened / Read</option>
                      <option value="message_delivery_failed">Delivery Failed (Exceeded Retries)</option>
                    </select>
                  </div>
                  <div>
                    <label className="text-[11px] text-slate-600 block">Waiting Period:</label>
                    <select
                      value={formData.wait_hours}
                      onChange={(e) => setFormData({ ...formData, wait_hours: e.target.value })}
                      className="w-full text-xs px-2.5 py-1.5 border border-slate-300 rounded-md bg-white mt-0.5"
                    >
                      <option value="1">1 hour</option>
                      <option value="6">6 hours</option>
                      <option value="12">12 hours</option>
                      <option value="24">24 hours (Recommended)</option>
                      <option value="48">48 hours</option>
                    </select>
                  </div>
                </div>

                {/* THEN block */}
                <div className="space-y-2">
                  <span className="text-[11px] font-bold text-emerald-600 uppercase tracking-wider block">
                    THEN (Action)
                  </span>
                  <div>
                    <label className="text-[11px] text-slate-600 block">Action Type:</label>
                    <select
                      value={formData.action_type}
                      onChange={(e) => setFormData({ ...formData, action_type: e.target.value })}
                      className="w-full text-xs px-2.5 py-1.5 border border-slate-300 rounded-md bg-white mt-0.5"
                    >
                      <option value="send_reminder">Send Reminder Message</option>
                      <option value="send_fallback">Send Alternate Channel Notice</option>
                    </select>
                  </div>
                  <div>
                    <label className="text-[11px] text-slate-600 block">Target Channel:</label>
                    <select
                      value={formData.action_channel}
                      onChange={(e) => setFormData({ ...formData, action_channel: e.target.value })}
                      className="w-full text-xs px-2.5 py-1.5 border border-slate-300 rounded-md bg-white mt-0.5"
                    >
                      <option value="SMS">SMS</option>
                      <option value="WhatsApp">WhatsApp</option>
                      <option value="Email">Email</option>
                      <option value="Push">Push Notification</option>
                    </select>
                  </div>
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Custom Reminder Text (Optional)
                </label>
                <input
                  type="text"
                  placeholder="Leave empty to use original campaign variant copy"
                  value={formData.custom_message}
                  onChange={(e) => setFormData({ ...formData, custom_message: e.target.value })}
                  className="w-full text-xs px-3 py-2 border border-slate-300 rounded-lg focus:ring-1 focus:ring-indigo-500 bg-white"
                />
              </div>

              <div className="flex justify-end gap-2 pt-1">
                <button
                  type="button"
                  onClick={() => setShowAddForm(false)}
                  className="px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-100 rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={loading}
                  className="px-4 py-1.5 text-xs font-bold bg-indigo-600 text-white hover:bg-indigo-700 rounded-lg shadow-xs"
                >
                  {loading ? 'Creating...' : 'Save Automation Rule'}
                </button>
              </div>
            </form>
          )}

          {/* Tab 1: Rules List */}
          {activeTab === 'rules' && (
            <div className="space-y-3">
              {rules.length === 0 ? (
                <div className="text-center py-10 bg-slate-50 rounded-xl border border-dashed border-slate-200">
                  <Clock className="w-8 h-8 text-slate-400 mx-auto mb-2" />
                  <p className="text-xs font-semibold text-slate-700">No automation rules configured</p>
                  <p className="text-[11px] text-slate-500 max-w-sm mx-auto mt-1">
                    Configure automated rules like sending an SMS reminder if an email is not opened within 24 hours.
                  </p>
                </div>
              ) : (
                rules.map((rule) => (
                  <div
                    key={rule.id}
                    className={`p-4 rounded-xl border transition flex items-center justify-between gap-4 ${
                      rule.is_enabled ? 'bg-white border-slate-200 shadow-2xs' : 'bg-slate-50 border-slate-200 opacity-60'
                    }`}
                  >
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-bold text-slate-900">{rule.name}</span>
                        <span
                          className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${
                            rule.is_enabled ? 'bg-emerald-50 text-emerald-700 border border-emerald-200' : 'bg-slate-200 text-slate-600'
                          }`}
                        >
                          {rule.is_enabled ? 'Active' : 'Disabled'}
                        </span>
                      </div>
                      <div className="flex items-center gap-2 text-xs text-slate-600">
                        <span className="font-semibold text-indigo-700">IF:</span>
                        <span>
                          {rule.trigger_condition === 'message_not_opened'
                            ? `Not opened after ${rule.wait_hours}h`
                            : `Failed delivery`}
                        </span>
                        <ArrowRight className="w-3.5 h-3.5 text-slate-400" />
                        <span className="font-semibold text-emerald-700">THEN:</span>
                        <span>
                          Send reminder via <strong className="text-slate-800">{rule.action_channel}</strong>
                        </span>
                      </div>
                    </div>

                    <div className="flex items-center gap-3">
                      <button
                        onClick={() => handleToggleRule(rule)}
                        className={`text-xs px-2.5 py-1 rounded-md font-semibold transition ${
                          rule.is_enabled
                            ? 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                            : 'bg-indigo-50 text-indigo-600 hover:bg-indigo-100'
                        }`}
                      >
                        {rule.is_enabled ? 'Disable' : 'Enable'}
                      </button>
                      <button
                        onClick={() => handleDeleteRule(rule.id)}
                        className="text-slate-400 hover:text-rose-600 p-1 rounded transition"
                        title="Delete rule"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>
          )}

          {/* Tab 2: Execution History */}
          {activeTab === 'history' && (
            <div className="space-y-2">
              {history.length === 0 ? (
                <div className="text-center py-10 bg-slate-50 rounded-xl border border-dashed border-slate-200">
                  <ShieldCheck className="w-8 h-8 text-slate-400 mx-auto mb-2" />
                  <p className="text-xs font-semibold text-slate-700">No automation executions recorded yet</p>
                  <p className="text-[11px] text-slate-500">
                    Executions are recorded here as rules trigger follow-ups or reminders.
                  </p>
                </div>
              ) : (
                <div className="border border-slate-200 rounded-xl overflow-hidden">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-slate-50 border-b border-slate-200 text-slate-600 font-semibold">
                      <tr>
                        <th className="py-2.5 px-3">Timestamp</th>
                        <th className="py-2.5 px-3">Recipient</th>
                        <th className="py-2.5 px-3">Action Taken</th>
                        <th className="py-2.5 px-3">Channel</th>
                        <th className="py-2.5 px-3">Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {history.map((log) => (
                        <tr key={log.id} className="hover:bg-slate-50/50">
                          <td className="py-2 px-3 text-slate-500 whitespace-nowrap">
                            {new Date(log.executed_at).toLocaleString()}
                          </td>
                          <td className="py-2 px-3 font-medium text-slate-800">{log.recipient_name}</td>
                          <td className="py-2 px-3 text-slate-600 font-mono text-[11px]">{log.action_taken}</td>
                          <td className="py-2 px-3">
                            <span className="px-2 py-0.5 rounded bg-slate-100 text-slate-700 font-semibold text-[11px]">
                              {log.target_channel}
                            </span>
                          </td>
                          <td className="py-2 px-3">
                            <span
                              className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                                log.status === 'success'
                                  ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                                  : 'bg-amber-50 text-amber-700 border border-amber-200'
                              }`}
                            >
                              {log.status}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-3 border-t border-slate-200 bg-slate-50 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-1.5 text-xs font-semibold bg-white border border-slate-300 rounded-lg text-slate-700 hover:bg-slate-50"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
