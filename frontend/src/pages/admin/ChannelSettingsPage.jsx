import React, { useState, useEffect } from 'react';
import {
  Mail,
  Smartphone,
  Save,
  Send,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Server,
  Key,
  Shield,
  Eye,
  EyeOff,
  Radio,
  RefreshCw,
  HelpCircle,
} from 'lucide-react';
import {
  listChannelConfigs,
  updateChannelConfig,
  testChannel,
} from '../../services/channelService';

export default function ChannelSettingsPage() {
  const [configs, setConfigs] = useState({});
  const [activeTab, setActiveTab] = useState('Email');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [error, setError] = useState(null);
  const [successMsg, setSuccessMsg] = useState(null);
  const [testResult, setTestResult] = useState(null);

  // Form states per channel
  const [formData, setFormData] = useState({
    Email: {
      is_enabled: true,
      provider_type: 'mock',
      sender_address: 'notifications@masscomm.gov.in',
      sender_name: 'MassCommAI Citizen Communications',
      credentials: {
        smtp_host: 'smtp.gov.in',
        smtp_port: '587',
        smtp_username: '',
        smtp_password: '',
        use_tls: true,
        sendgrid_api_key: '',
      },
    },
    SMS: {
      is_enabled: true,
      provider_type: 'mock',
      sender_address: 'GOVMSG',
      sender_name: 'Govt Citizen Alert',
      credentials: {
        twilio_account_sid: '',
        twilio_auth_token: '',
        twilio_from_number: '',
        fast2sms_api_key: '',
      },
    },
  });

  const [testDestinations, setTestDestinations] = useState({
    Email: 'admin@masscomm.gov.in',
    SMS: '+919876543210',
  });

  const [showSecrets, setShowSecrets] = useState({});

  const toggleShowSecret = (field) => {
    setShowSecrets((prev) => ({ ...prev, [field]: !prev[field] }));
  };

  const fetchConfigs = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await listChannelConfigs();
      const cfgMap = {};
      data.forEach((item) => {
        cfgMap[item.channel] = item;
      });
      setConfigs(cfgMap);

      // Hydrate forms
      setFormData((prev) => ({
        Email: {
          is_enabled: cfgMap.Email?.is_enabled ?? true,
          provider_type: cfgMap.Email?.provider_type ?? 'mock',
          sender_address: cfgMap.Email?.sender_address ?? 'notifications@masscomm.gov.in',
          sender_name: cfgMap.Email?.sender_name ?? 'MassCommAI Citizen Communications',
          credentials: {
            ...prev.Email.credentials,
            ...(cfgMap.Email?.masked_credentials || {}),
          },
        },
        SMS: {
          is_enabled: cfgMap.SMS?.is_enabled ?? true,
          provider_type: cfgMap.SMS?.provider_type ?? 'mock',
          sender_address: cfgMap.SMS?.sender_address ?? 'GOVMSG',
          sender_name: cfgMap.SMS?.sender_name ?? 'Govt Citizen Alert',
          credentials: {
            ...prev.SMS.credentials,
            ...(cfgMap.SMS?.masked_credentials || {}),
          },
        },
      }));
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load channel configurations.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchConfigs();
  }, []);

  const handleFieldChange = (channel, field, value) => {
    setFormData((prev) => ({
      ...prev,
      [channel]: {
        ...prev[channel],
        [field]: value,
      },
    }));
  };

  const handleCredChange = (channel, credKey, value) => {
    setFormData((prev) => ({
      ...prev,
      [channel]: {
        ...prev[channel],
        credentials: {
          ...prev[channel].credentials,
          [credKey]: value,
        },
      },
    }));
  };

  const handleSave = async (e) => {
    e.preventDefault();
    try {
      setSaving(true);
      setError(null);
      setSuccessMsg(null);
      const current = formData[activeTab];
      await updateChannelConfig(activeTab, {
        is_enabled: current.is_enabled,
        provider_type: current.provider_type,
        sender_address: current.sender_address,
        sender_name: current.sender_name,
        credentials: current.credentials,
      });
      setSuccessMsg(`${activeTab} channel configuration updated successfully.`);
      await fetchConfigs();
    } catch (err) {
      setError(err.response?.data?.detail || `Failed to update ${activeTab} channel.`);
    } finally {
      setSaving(false);
    }
  };

  const handleTestDispatch = async () => {
    try {
      setTesting(true);
      setTestResult(null);
      setError(null);
      const destination = testDestinations[activeTab];
      const res = await testChannel(activeTab, {
        destination,
        message: `MassCommAI automated connectivity test via ${activeTab} channel.`,
        subject: `[Test] MassCommAI ${activeTab} Gateway Health Verification`,
      });
      setTestResult(res);
    } catch (err) {
      setTestResult({
        success: false,
        status: 'Failed',
        provider_name: activeTab.toLowerCase(),
        error_code: 'TEST_REQUEST_FAILED',
        error_message: err.response?.data?.detail || err.message,
      });
    } finally {
      setTesting(false);
    }
  };

  const curData = formData[activeTab] || {};

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      {/* Header Banner */}
      <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Channel Integration Governance</h1>
            <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-indigo-50 text-indigo-700 border border-indigo-200">
              <Radio className="w-3 h-3 animate-pulse" />
              Gateway Engine
            </span>
          </div>
          <p className="text-sm text-slate-500 mt-1">
            Configure delivery adapters, API credentials, and verify external gateway connectivity for citizen communication.
          </p>
        </div>
        <button
          onClick={fetchConfigs}
          disabled={loading}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-slate-600 bg-slate-50 hover:bg-slate-100 border border-slate-200 rounded-lg transition"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          Refresh Status
        </button>
      </div>

      {/* Global Alerts */}
      {error && (
        <div className="bg-rose-50 border border-rose-200 rounded-xl p-4 flex items-center gap-3 text-rose-700 text-sm">
          <AlertCircle className="w-5 h-5 shrink-0 text-rose-500" />
          <span>{error}</span>
        </div>
      )}
      {successMsg && (
        <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-4 flex items-center gap-3 text-emerald-800 text-sm">
          <CheckCircle2 className="w-5 h-5 shrink-0 text-emerald-600" />
          <span>{successMsg}</span>
        </div>
      )}

      {/* Channel Tabs */}
      <div className="flex border-b border-slate-200 gap-4">
        <button
          onClick={() => {
            setActiveTab('Email');
            setTestResult(null);
          }}
          className={`pb-3 px-2 font-medium text-sm flex items-center gap-2 border-b-2 transition ${
            activeTab === 'Email'
              ? 'border-indigo-600 text-indigo-600 font-semibold'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <Mail className="w-4 h-4" />
          Email Channel
          <span
            className={`text-xs px-2 py-0.5 rounded-full font-semibold ${
              formData.Email?.is_enabled
                ? 'bg-emerald-100 text-emerald-700'
                : 'bg-slate-200 text-slate-600'
            }`}
          >
            {formData.Email?.is_enabled ? 'Active' : 'Disabled'}
          </span>
        </button>

        <button
          onClick={() => {
            setActiveTab('SMS');
            setTestResult(null);
          }}
          className={`pb-3 px-2 font-medium text-sm flex items-center gap-2 border-b-2 transition ${
            activeTab === 'SMS'
              ? 'border-indigo-600 text-indigo-600 font-semibold'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <Smartphone className="w-4 h-4" />
          SMS Channel
          <span
            className={`text-xs px-2 py-0.5 rounded-full font-semibold ${
              formData.SMS?.is_enabled
                ? 'bg-emerald-100 text-emerald-700'
                : 'bg-slate-200 text-slate-600'
            }`}
          >
            {formData.SMS?.is_enabled ? 'Active' : 'Disabled'}
          </span>
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left 2 Columns: Configuration Form */}
        <div className="lg:col-span-2 space-y-6">
          <form onSubmit={handleSave} className="bg-white border border-slate-200 rounded-2xl p-6 shadow-xs space-y-6">
            {/* Enable/Disable Toggle */}
            <div className="flex items-center justify-between pb-5 border-b border-slate-100">
              <div>
                <label className="text-base font-semibold text-slate-900 block">
                  {activeTab} Channel Operational Status
                </label>
                <p className="text-xs text-slate-500 mt-0.5">
                  When disabled, campaign dispatches over this channel are withheld automatically.
                </p>
              </div>
              <button
                type="button"
                onClick={() => handleFieldChange(activeTab, 'is_enabled', !curData.is_enabled)}
                className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-hidden ${
                  curData.is_enabled ? 'bg-indigo-600' : 'bg-slate-200'
                }`}
              >
                <span
                  className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow-sm ring-0 transition duration-200 ease-in-out ${
                    curData.is_enabled ? 'translate-x-5' : 'translate-x-0'
                  }`}
                />
              </button>
            </div>

            {/* Provider Type Selection */}
            <div>
              <label className="block text-sm font-semibold text-slate-900 mb-1">
                Active Provider Adapter
              </label>
              <select
                value={curData.provider_type}
                onChange={(e) => handleFieldChange(activeTab, 'provider_type', e.target.value)}
                className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg bg-white focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
              >
                {activeTab === 'Email' ? (
                  <>
                    <option value="mock">Mock / Demo Sandbox (Simulated Delivery)</option>
                    <option value="smtp">Standard SMTP Server (TLS / StartTLS)</option>
                    <option value="sendgrid">SendGrid REST API v3</option>
                  </>
                ) : (
                  <>
                    <option value="mock">Mock / Demo Sandbox (Simulated Telecom Gateway)</option>
                    <option value="twilio">Twilio Cloud Communications</option>
                    <option value="fast2sms">Fast2SMS (Gov/Indian Telecom Gateway)</option>
                  </>
                )}
              </select>
            </div>

            {/* Sender Metadata */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">
                  {activeTab === 'Email' ? 'From Email Address' : 'Sender Header / Phone'}
                </label>
                <input
                  type="text"
                  value={curData.sender_address || ''}
                  onChange={(e) => handleFieldChange(activeTab, 'sender_address', e.target.value)}
                  placeholder={activeTab === 'Email' ? 'notifications@masscomm.gov.in' : 'GOVMSG'}
                  className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">
                  Sender Display Name
                </label>
                <input
                  type="text"
                  value={curData.sender_name || ''}
                  onChange={(e) => handleFieldChange(activeTab, 'sender_name', e.target.value)}
                  placeholder={activeTab === 'Email' ? 'MassCommAI Citizen Portal' : 'Govt Citizen Alert'}
                  className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                />
              </div>
            </div>

            {/* Provider-Specific Credentials */}
            {curData.provider_type === 'mock' ? (
              <div className="bg-indigo-50/60 border border-indigo-100 rounded-xl p-4 flex items-start gap-3">
                <Shield className="w-5 h-5 text-indigo-600 mt-0.5 shrink-0" />
                <div className="text-xs text-indigo-900 space-y-1">
                  <p className="font-semibold">Deterministic Mock Mode Active</p>
                  <p>
                    Outbound communications are deterministically simulated without dispatching external network calls or incurring telephony charges.
                    Email format and Indian phone number syntax are validated strictly.
                  </p>
                </div>
              </div>
            ) : curData.provider_type === 'smtp' ? (
              <div className="space-y-4 pt-4 border-t border-slate-100">
                <h3 className="text-sm font-semibold text-slate-900 flex items-center gap-1.5">
                  <Server className="w-4 h-4 text-indigo-600" />
                  SMTP Server Credentials
                </h3>

                <div className="grid grid-cols-3 gap-3">
                  <div className="col-span-2">
                    <label className="block text-xs font-medium text-slate-600 mb-1">Host</label>
                    <input
                      type="text"
                      value={curData.credentials?.smtp_host || ''}
                      onChange={(e) => handleCredChange('Email', 'smtp_host', e.target.value)}
                      placeholder="smtp.example.gov.in"
                      className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-slate-600 mb-1">Port</label>
                    <input
                      type="number"
                      value={curData.credentials?.smtp_port || '587'}
                      onChange={(e) => handleCredChange('Email', 'smtp_port', e.target.value)}
                      placeholder="587"
                      className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-medium text-slate-600 mb-1">Username</label>
                    <input
                      type="text"
                      value={curData.credentials?.smtp_username || ''}
                      onChange={(e) => handleCredChange('Email', 'smtp_username', e.target.value)}
                      placeholder="postmaster"
                      className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-slate-600 mb-1">Password</label>
                    <div className="relative">
                      <input
                        type={showSecrets.smtp_password ? 'text' : 'password'}
                        value={curData.credentials?.smtp_password || ''}
                        onChange={(e) => handleCredChange('Email', 'smtp_password', e.target.value)}
                        placeholder="••••••••"
                        className="w-full px-3 py-2 pr-9 text-sm border border-slate-300 rounded-lg"
                      />
                      <button
                        type="button"
                        onClick={() => toggleShowSecret('smtp_password')}
                        className="absolute right-2.5 top-2.5 text-slate-400 hover:text-slate-600"
                      >
                        {showSecrets.smtp_password ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                      </button>
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-2 pt-1">
                  <input
                    type="checkbox"
                    id="smtp_tls"
                    checked={curData.credentials?.use_tls !== false}
                    onChange={(e) => handleCredChange('Email', 'use_tls', e.target.checked)}
                    className="rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
                  />
                  <label htmlFor="smtp_tls" className="text-xs font-medium text-slate-700">
                    Enable STARTTLS encryption
                  </label>
                </div>
              </div>
            ) : curData.provider_type === 'sendgrid' ? (
              <div className="space-y-4 pt-4 border-t border-slate-100">
                <h3 className="text-sm font-semibold text-slate-900 flex items-center gap-1.5">
                  <Key className="w-4 h-4 text-indigo-600" />
                  SendGrid API Configuration
                </h3>
                <div>
                  <label className="block text-xs font-medium text-slate-600 mb-1">API Key</label>
                  <div className="relative">
                    <input
                      type={showSecrets.sendgrid_api_key ? 'text' : 'password'}
                      value={curData.credentials?.api_key || curData.credentials?.sendgrid_api_key || ''}
                      onChange={(e) => handleCredChange('Email', 'api_key', e.target.value)}
                      placeholder="SG.••••••••••••••••••••"
                      className="w-full px-3 py-2 pr-9 text-sm border border-slate-300 rounded-lg font-mono text-xs"
                    />
                    <button
                      type="button"
                      onClick={() => toggleShowSecret('sendgrid_api_key')}
                      className="absolute right-2.5 top-2.5 text-slate-400 hover:text-slate-600"
                    >
                      {showSecrets.sendgrid_api_key ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  </div>
                </div>
              </div>
            ) : curData.provider_type === 'twilio' ? (
              <div className="space-y-4 pt-4 border-t border-slate-100">
                <h3 className="text-sm font-semibold text-slate-900 flex items-center gap-1.5">
                  <Key className="w-4 h-4 text-indigo-600" />
                  Twilio Account Configuration
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-medium text-slate-600 mb-1">Account SID</label>
                    <input
                      type="text"
                      value={curData.credentials?.account_sid || ''}
                      onChange={(e) => handleCredChange('SMS', 'account_sid', e.target.value)}
                      placeholder="AC••••••••••••••••••••"
                      className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg font-mono text-xs"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-slate-600 mb-1">Auth Token</label>
                    <div className="relative">
                      <input
                        type={showSecrets.twilio_auth_token ? 'text' : 'password'}
                        value={curData.credentials?.auth_token || ''}
                        onChange={(e) => handleCredChange('SMS', 'auth_token', e.target.value)}
                        placeholder="••••••••••••••••••••"
                        className="w-full px-3 py-2 pr-9 text-sm border border-slate-300 rounded-lg font-mono text-xs"
                      />
                      <button
                        type="button"
                        onClick={() => toggleShowSecret('twilio_auth_token')}
                        className="absolute right-2.5 top-2.5 text-slate-400 hover:text-slate-600"
                      >
                        {showSecrets.twilio_auth_token ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                      </button>
                    </div>
                  </div>
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-600 mb-1">Twilio From Number</label>
                  <input
                    type="text"
                    value={curData.credentials?.from_number || ''}
                    onChange={(e) => handleCredChange('SMS', 'from_number', e.target.value)}
                    placeholder="+12025550143"
                    className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg"
                  />
                </div>
              </div>
            ) : curData.provider_type === 'fast2sms' ? (
              <div className="space-y-4 pt-4 border-t border-slate-100">
                <h3 className="text-sm font-semibold text-slate-900 flex items-center gap-1.5">
                  <Key className="w-4 h-4 text-indigo-600" />
                  Fast2SMS API Configuration
                </h3>
                <div>
                  <label className="block text-xs font-medium text-slate-600 mb-1">Authorization API Key</label>
                  <div className="relative">
                    <input
                      type={showSecrets.fast2sms_api_key ? 'text' : 'password'}
                      value={curData.credentials?.api_key || ''}
                      onChange={(e) => handleCredChange('SMS', 'api_key', e.target.value)}
                      placeholder="••••••••••••••••••••"
                      className="w-full px-3 py-2 pr-9 text-sm border border-slate-300 rounded-lg font-mono text-xs"
                    />
                    <button
                      type="button"
                      onClick={() => toggleShowSecret('fast2sms_api_key')}
                      className="absolute right-2.5 top-2.5 text-slate-400 hover:text-slate-600"
                    >
                      {showSecrets.fast2sms_api_key ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  </div>
                </div>
              </div>
            ) : null}

            {/* Save Button */}
            <div className="pt-4 border-t border-slate-100 flex justify-end">
              <button
                type="submit"
                disabled={saving}
                className="inline-flex items-center gap-2 px-5 py-2.5 text-sm font-semibold rounded-xl bg-indigo-600 text-white hover:bg-indigo-700 shadow-sm transition disabled:opacity-50"
              >
                {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                Save {activeTab} Configuration
              </button>
            </div>
          </form>
        </div>

        {/* Right 1 Column: Connectivity Test & Diagnostic Panel */}
        <div className="space-y-6">
          <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-xs space-y-4">
            <h2 className="text-base font-semibold text-slate-900 flex items-center gap-2">
              <Send className="w-4 h-4 text-indigo-600" />
              Test {activeTab} Connectivity
            </h2>
            <p className="text-xs text-slate-500">
              Dispatches an isolated probe message to verify authentication and gateway routing without affecting campaigns.
            </p>

            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1">
                {activeTab === 'Email' ? 'Test Recipient Email' : 'Test Recipient Phone'}
              </label>
              <input
                type="text"
                value={testDestinations[activeTab] || ''}
                onChange={(e) =>
                  setTestDestinations((prev) => ({
                    ...prev,
                    [activeTab]: e.target.value,
                  }))
                }
                placeholder={activeTab === 'Email' ? 'admin@masscomm.gov.in' : '+919876543210'}
                className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
              />
            </div>

            <button
              type="button"
              onClick={handleTestDispatch}
              disabled={testing || !testDestinations[activeTab]}
              className="w-full inline-flex items-center justify-center gap-2 px-4 py-2 text-sm font-semibold rounded-xl bg-slate-900 text-white hover:bg-slate-800 transition disabled:opacity-50"
            >
              {testing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
              Send Test {activeTab}
            </button>

            {/* Test Results Output */}
            {testResult && (
              <div
                className={`p-4 rounded-xl border text-xs space-y-2 animate-in fade-in ${
                  testResult.success
                    ? 'bg-emerald-50 border-emerald-200 text-emerald-900'
                    : 'bg-rose-50 border-rose-200 text-rose-900'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="font-semibold flex items-center gap-1.5">
                    {testResult.success ? (
                      <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                    ) : (
                      <AlertCircle className="w-4 h-4 text-rose-600" />
                    )}
                    {testResult.status} ({testResult.provider_name})
                  </span>
                  <span className="text-[10px] uppercase font-mono px-1.5 py-0.5 rounded bg-white/70 border">
                    {testResult.success ? 'Success' : 'Error'}
                  </span>
                </div>

                {testResult.provider_message_id && (
                  <p className="font-mono text-[11px] text-slate-600 truncate">
                    Ref: {testResult.provider_message_id}
                  </p>
                )}

                {testResult.error_message && (
                  <p className="text-rose-700 font-medium">{testResult.error_message}</p>
                )}

                {testResult.metadata && Object.keys(testResult.metadata).length > 0 && (
                  <div className="mt-2 pt-2 border-t border-slate-200/60 font-mono text-[10px] text-slate-500">
                    <pre className="overflow-x-auto whitespace-pre-wrap">
                      {JSON.stringify(testResult.metadata, null, 2)}
                    </pre>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

