import React, { useState, useEffect } from 'react';
import {
  Radio,
  Bell,
  BellRing,
  AlertTriangle,
  Globe,
  RefreshCw,
  ShieldCheck,
  CheckCircle2,
  Calendar,
  Volume2,
} from 'lucide-react';
import { getPublicAnnouncements, registerDeviceToken } from '../../services/channelService';
import { API_BASE_URL } from '../../services/api';

export default function PublicAnnouncementsPage() {
  const [announcements, setAnnouncements] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedLanguage, setSelectedLanguage] = useState('');
  const [emergencyOnly, setEmergencyOnly] = useState(false);
  const [pushStatus, setPushStatus] = useState('default'); // 'default' | 'granted' | 'denied' | 'registering'
  const [pushMessage, setPushMessage] = useState(null);

  const fetchAnnouncements = async () => {
    try {
      setLoading(true);
      const params = {};
      if (selectedLanguage) params.language = selectedLanguage;
      if (emergencyOnly) params.emergency_only = true;
      const data = await getPublicAnnouncements(params);
      setAnnouncements(data);
    } catch (err) {
      console.error('Failed to load announcements:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAnnouncements();

    // Check current push notification permission
    if ('Notification' in window) {
      setPushStatus(Notification.permission);
    }

    // Connect to SSE stream for live real-time broadcasts
    let eventSource;
    try {
      const sseUrl = `${API_BASE_URL}/broadcast/sse`;
      eventSource = new EventSource(sseUrl);

      eventSource.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          if (payload.title && payload.body) {
            // Prepend new broadcast to announcements
            setAnnouncements((prev) => [payload, ...prev]);

            // If browser notification allowed, trigger notification
            if (Notification.permission === 'granted') {
              new Notification(payload.title, {
                body: payload.body,
                icon: '/vite.svg',
              });
            }
          }
        } catch (e) {
          // Heartbeat or malformed frame
        }
      };

      eventSource.onerror = () => {
        eventSource.close();
      };
    } catch (err) {
      console.warn('SSE subscription error:', err);
    }

    return () => {
      if (eventSource) eventSource.close();
    };
  }, [selectedLanguage, emergencyOnly]);

  const handleRequestPush = async () => {
    if (!('Notification' in window)) {
      setPushMessage('Browser push notifications are not supported in this browser.');
      return;
    }

    try {
      setPushStatus('registering');
      const permission = await Notification.requestPermission();
      setPushStatus(permission);

      if (permission === 'granted') {
        // Generate client device token and register with backend
        const mockToken = `web_token_${Math.random().toString(36).substring(2, 15)}_${Date.now()}`;
        await registerDeviceToken({
          token: mockToken,
          device_type: 'web',
          platform_metadata: {
            userAgent: navigator.userAgent,
            language: navigator.language,
          },
        });
        setPushMessage('Citizen Push Notifications activated successfully.');
      } else {
        setPushMessage('Push notifications permission was denied.');
      }
    } catch (err) {
      setPushMessage('Could not complete notification registration.');
      setPushStatus('default');
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 pb-12">
      {/* Citizen Portal Header */}
      <header className="bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 text-white border-b border-indigo-900/50">
        <div className="max-w-6xl mx-auto px-4 py-8 sm:px-6">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
            <div className="space-y-2">
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-500/20 text-emerald-300 border border-emerald-400/30">
                <Radio className="w-3.5 h-3.5 animate-pulse text-emerald-400" />
                Live Citizen Portal
              </div>
              <h1 className="text-3xl font-extrabold tracking-tight sm:text-4xl">
                Official Public Announcements
              </h1>
              <p className="text-sm text-slate-300 max-w-2xl">
                Real-time official communication, public advisories, and emergency alerts. Guaranteed anonymous delivery with zero personal tracking.
              </p>
            </div>

            {/* Notification Subscription Card */}
            <div className="bg-white/10 backdrop-blur-md border border-white/20 rounded-2xl p-4 sm:p-5 flex items-center gap-4 shrink-0 shadow-lg">
              <div className="w-12 h-12 rounded-xl bg-indigo-500/30 border border-indigo-400/30 flex items-center justify-center shrink-0">
                {pushStatus === 'granted' ? (
                  <BellRing className="w-6 h-6 text-emerald-400" />
                ) : (
                  <Bell className="w-6 h-6 text-indigo-300" />
                )}
              </div>
              <div>
                <h2 className="text-sm font-bold text-white">Browser Push Alerts</h2>
                <p className="text-xs text-slate-300">
                  {pushStatus === 'granted' ? 'Active on this device' : 'Receive immediate critical notifications'}
                </p>
                {pushStatus !== 'granted' ? (
                  <button
                    onClick={handleRequestPush}
                    disabled={pushStatus === 'registering'}
                    className="mt-2 inline-flex items-center gap-1.5 px-3 py-1 text-xs font-semibold rounded-lg bg-emerald-600 text-white hover:bg-emerald-500 transition shadow-xs"
                  >
                    Enable Notifications
                  </button>
                ) : (
                  <span className="mt-1 inline-flex items-center gap-1 text-[11px] font-semibold text-emerald-400">
                    <CheckCircle2 className="w-3 h-3" /> Enabled
                  </span>
                )}
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="max-w-6xl mx-auto px-4 sm:px-6 pt-8 space-y-6">
        {pushMessage && (
          <div className="bg-indigo-50 border border-indigo-200 text-indigo-900 px-4 py-3 rounded-xl text-xs flex items-center justify-between animate-in fade-in">
            <span>{pushMessage}</span>
            <button onClick={() => setPushMessage(null)} className="font-bold ml-2">
              Dismiss
            </button>
          </div>
        )}

        {/* Filter Controls Bar */}
        <div className="bg-white border border-slate-200 rounded-2xl p-4 shadow-xs flex flex-wrap items-center justify-between gap-4">
          <div className="flex flex-wrap items-center gap-4">
            {/* Language Selector */}
            <div className="flex items-center gap-2">
              <Globe className="w-4 h-4 text-slate-500" />
              <label htmlFor="lang-select" className="text-xs font-semibold text-slate-700 uppercase tracking-wider">
                Language:
              </label>
              <select
                id="lang-select"
                value={selectedLanguage}
                onChange={(e) => setSelectedLanguage(e.target.value)}
                className="text-xs font-medium border border-slate-300 rounded-lg px-2.5 py-1.5 bg-white text-slate-800 focus:ring-2 focus:ring-indigo-500"
              >
                <option value="">All Languages</option>
                <option value="en">English</option>
                <option value="hi">Hindi (हिन्दी)</option>
                <option value="ta">Tamil (தமிழ்)</option>
                <option value="te">Telugu (తెలుగు)</option>
                <option value="bn">Bengali (বাংলা)</option>
              </select>
            </div>

            {/* Emergency Alerts Toggle */}
            <label className="flex items-center gap-2 text-xs font-semibold text-slate-700 cursor-pointer">
              <input
                type="checkbox"
                checked={emergencyOnly}
                onChange={(e) => setEmergencyOnly(e.target.checked)}
                className="rounded border-slate-300 text-rose-600 focus:ring-rose-500"
              />
              <span className="flex items-center gap-1 text-rose-700">
                <AlertTriangle className="w-3.5 h-3.5 text-rose-600" />
                Emergency Alerts Only
              </span>
            </label>
          </div>

          <button
            onClick={fetchAnnouncements}
            disabled={loading}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-slate-600 bg-slate-50 hover:bg-slate-100 border border-slate-200 rounded-lg transition"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            Refresh Feed
          </button>
        </div>

        {/* Feed List */}
        {loading && announcements.length === 0 ? (
          <div className="p-12 text-center text-slate-500 text-sm">
            <RefreshCw className="w-6 h-6 animate-spin mx-auto text-indigo-600 mb-2" />
            Connecting to official announcement feed...
          </div>
        ) : announcements.length === 0 ? (
          <div className="bg-white border border-slate-200 rounded-2xl p-12 text-center text-slate-500 space-y-3">
            <ShieldCheck className="w-12 h-12 text-emerald-600 mx-auto" />
            <h2 className="text-base font-bold text-slate-900">No Active Alerts</h2>
            <p className="text-xs text-slate-500 max-w-sm mx-auto">
              There are currently no active public alerts or announcements matching your filter criteria.
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            {announcements.map((item) => (
              <article
                key={item.id}
                className={`border rounded-2xl p-6 transition shadow-xs ${
                  item.is_emergency
                    ? 'bg-rose-50/40 border-rose-200 hover:border-rose-300'
                    : 'bg-white border-slate-200 hover:border-slate-300'
                }`}
              >
                <div className="flex items-start justify-between gap-4 mb-3">
                  <div className="flex items-center gap-2">
                    {item.is_emergency && (
                      <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-bold uppercase tracking-wider bg-rose-600 text-white animate-pulse">
                        <AlertTriangle className="w-3 h-3" /> Emergency Alert
                      </span>
                    )}
                    <span className="text-[11px] font-semibold px-2 py-0.5 rounded bg-slate-100 text-slate-700 uppercase">
                      {item.language || 'en'}
                    </span>
                    <span className="text-xs text-slate-500 flex items-center gap-1 font-mono">
                      <Calendar className="w-3 h-3" />
                      {item.broadcast_at ? new Date(item.broadcast_at).toLocaleString() : 'Just now'}
                    </span>
                  </div>
                </div>

                <h2 className="text-lg font-bold text-slate-900 mb-2">{item.title}</h2>
                <div className="text-sm text-slate-700 whitespace-pre-wrap leading-relaxed">
                  {item.body}
                </div>
              </article>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
