import React from 'react';
import {
  Smartphone,
  Volume2,
  Mail,
  MessageSquare,
  AlertTriangle,
  AlertCircle,
  CheckCircle2,
  Info,
  ShieldAlert,
  Radio,
  Layers,
  Sparkles,
  Zap,
} from 'lucide-react';

const SEVERITY_CONFIG = {
  CRITICAL: {
    bg: 'bg-rose-50 border-rose-200 text-rose-900',
    iconColor: 'text-rose-600',
    badge: 'bg-rose-100 text-rose-800 border-rose-300',
  },
  HIGH: {
    bg: 'bg-orange-50 border-orange-200 text-orange-900',
    iconColor: 'text-orange-600',
    badge: 'bg-orange-100 text-orange-800 border-orange-300',
  },
  MEDIUM: {
    bg: 'bg-amber-50 border-amber-200 text-amber-900',
    iconColor: 'text-amber-600',
    badge: 'bg-amber-100 text-amber-800 border-amber-300',
  },
  LOW: {
    bg: 'bg-yellow-50 border-yellow-200 text-yellow-900',
    iconColor: 'text-yellow-600',
    badge: 'bg-yellow-100 text-yellow-800 border-yellow-300',
  },
  INFO: {
    bg: 'bg-sky-50 border-sky-200 text-sky-900',
    iconColor: 'text-sky-600',
    badge: 'bg-sky-100 text-sky-800 border-sky-300',
  },
};

const CHANNEL_ICONS = {
  SMS: Smartphone,
  Voice: Volume2,
  WhatsApp: MessageSquare,
  Email: Mail,
};

/**
 * ChannelConstraintsMeter
 * 
 * Renders live or persisted telecommunications constraints, segment meters,
 * encoding pills (GSM-7 vs UCS-2), voice speaking duration, and structured warnings.
 */
export default function ChannelConstraintsMeter({
  metrics,
  isLive = false,
  loading = false,
  language = null,
  className = '',
}) {
  if (!metrics) return null;

  const channel = metrics.channel || 'SMS';
  const ChannelIcon = CHANNEL_ICONS[channel] || Smartphone;
  const sms = metrics.sms;
  const warnings = metrics.warnings || [];

  return (
    <div className={`p-4 rounded-xl border border-slate-200 bg-white shadow-2xs space-y-3.5 ${className}`}>
      
      {/* Header Bar: Channel Indicator, Mode Badge, and Recalculating state */}
      <div className="flex items-center justify-between flex-wrap gap-2 pb-2.5 border-b border-slate-100 text-xs">
        <div className="flex items-center gap-2">
          <span className="p-1 rounded-lg bg-slate-100 text-slate-700">
            <ChannelIcon className="w-3.5 h-3.5" />
          </span>
          <span className="font-bold text-slate-900">{channel} Constraints</span>
          <span className="text-[10px] text-slate-400 font-mono">({metrics.rule_version || 'v1.0'})</span>
        </div>

        <div className="flex items-center gap-2">
          {loading && (
            <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-brand-600 animate-pulse">
              <span className="w-1.5 h-1.5 rounded-full bg-brand-500 animate-ping" />
              Recalculating...
            </span>
          )}

          {isLive ? (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-sky-50 text-sky-700 border border-sky-200 shadow-2xs">
              <span className="w-1.5 h-1.5 rounded-full bg-sky-500 animate-pulse" />
              Live Estimate
            </span>
          ) : (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-slate-100 text-slate-700 border border-slate-200">
              Persisted Snapshot
            </span>
          )}
        </div>
      </div>

      {/* CHANNEL: SMS Detailed Telephony Analysis */}
      {channel === 'SMS' && sms && (
        <div className="space-y-3">
          
          {/* Status Badges: Encoding & Segmentation */}
          <div className="flex items-center justify-between flex-wrap gap-2 text-xs">
            <div className="flex items-center gap-2 flex-wrap">
              {/* GSM-7 vs UCS-2 Encoding Badge */}
              <span
                className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-lg font-bold border text-xs shadow-2xs ${
                  sms.encoding === 'GSM-7'
                    ? 'bg-emerald-50 text-emerald-800 border-emerald-300'
                    : 'bg-indigo-50 text-indigo-800 border-indigo-300'
                }`}
                title={sms.encoding === 'GSM-7' ? 'Standard 7-bit Latin/Greek character set' : '16-bit Unicode encoding (required for Indic scripts / emojis)'}
              >
                <Radio className="w-3 h-3" />
                {sms.encoding}
                <span className="font-normal opacity-80 text-[10px]">
                  ({sms.encoding === 'GSM-7' ? '7-bit' : '16-bit UCS-2'})
                </span>
              </span>

              {/* Segment Count Pill */}
              <span
                className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-lg font-bold border text-xs ${
                  sms.segment_count > 3
                    ? 'bg-rose-50 text-rose-800 border-rose-300'
                    : sms.segment_count > 1
                    ? 'bg-amber-50 text-amber-800 border-amber-300'
                    : 'bg-slate-100 text-slate-800 border-slate-300'
                }`}
              >
                <Layers className="w-3 h-3" />
                {sms.segment_count === 0 ? '0 Segments' : `${sms.segment_count} Segment${sms.segment_count > 1 ? 's' : ''}`}
                {sms.is_multipart && (
                  <span className="text-[10px] font-medium opacity-90">(Multipart)</span>
                )}
              </span>
            </div>

            {/* Encoded Units & Segment Capacity */}
            <div className="text-right text-[11px] text-slate-600 font-mono">
              <span className="font-bold text-slate-900">{sms.encoded_units}</span> /{' '}
              <span>{sms.segment_count > 1 ? (sms.encoding === 'GSM-7' ? sms.segment_count * 153 : sms.segment_count * 67) : sms.segment_capacity}</span>{' '}
              {sms.encoding === 'GSM-7' ? 'septets' : 'units'}{' '}
              <span className="text-slate-400">({sms.character_count} chars)</span>
            </div>
          </div>

          {/* Segment Capacity Visual Bar */}
          <div className="space-y-1">
            <div className="flex items-center justify-between text-[10px] text-slate-500">
              <span>Current Segment Capacity</span>
              <span className="font-semibold text-slate-700">
                {sms.remaining_in_segment} {sms.encoding === 'GSM-7' ? 'septets' : 'units'} remaining in segment {sms.segment_count || 1}
              </span>
            </div>
            <div className="w-full bg-slate-100 h-2 rounded-full overflow-hidden flex">
              <div
                className={`h-full transition-all duration-300 ${
                  sms.segment_count > 3
                    ? 'bg-rose-500'
                    : sms.segment_count > 1
                    ? 'bg-amber-500'
                    : 'bg-emerald-500'
                }`}
                style={{
                  width: `${Math.min(
                    100,
                    Math.max(
                      3,
                      sms.segment_capacity > 0
                        ? (((sms.segment_capacity - sms.remaining_in_segment) / sms.segment_capacity) * 100)
                        : 0
                    )
                  )}%`,
                }}
              />
            </div>
          </div>

          {/* Detailed Encoding Indicators: Extension Chars & Surrogates */}
          <div className="flex items-center gap-2 flex-wrap pt-0.5 text-[11px]">
            {sms.has_extension_characters && (
              <span
                className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-amber-50 text-amber-800 border border-amber-200 text-[10px] font-medium"
                title="Characters like {, }, [, ], ^, ~, |, € consume 2 septets each due to GSM escape byte"
              >
                <Zap className="w-2.5 h-2.5 text-amber-600" />
                GSM Extension Characters (+1 septet cost each)
              </span>
            )}

            {sms.has_surrogate_pairs && (
              <span
                className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-indigo-50 text-indigo-800 border border-indigo-200 text-[10px] font-medium"
                title="Astral Unicode characters (such as emojis) require 2 UTF-16 code units (4 bytes)"
              >
                <Sparkles className="w-2.5 h-2.5 text-indigo-600" />
                Supplementary Characters / Emojis (2 units each)
              </span>
            )}

            {sms.non_gsm_characters && sms.non_gsm_characters.length > 0 && (
              <span
                className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-rose-50 text-rose-800 border border-rose-200 text-[10px] font-medium"
                title={`Non-GSM characters detected: ${sms.non_gsm_characters.join(' ')}`}
              >
                Non-GSM: {sms.non_gsm_characters.slice(0, 4).join(' ')}
                {sms.non_gsm_characters.length > 4 ? ` (+${sms.non_gsm_characters.length - 4})` : ''}
              </span>
            )}
          </div>
        </div>
      )}

      {/* CHANNEL: Voice IVR Duration & Pacing */}
      {channel === 'Voice' && (
        <div className="space-y-3">
          <div className="flex items-center justify-between flex-wrap gap-2 text-xs">
            <div className="flex items-center gap-2">
              <span
                className={`inline-flex items-center gap-1 px-3 py-1 rounded-lg font-bold border text-xs ${
                  (metrics.estimated_duration_seconds || 0) > 90
                    ? 'bg-rose-50 text-rose-800 border-rose-300'
                    : (metrics.estimated_duration_seconds || 0) > 60
                    ? 'bg-amber-50 text-amber-800 border-amber-300'
                    : 'bg-emerald-50 text-emerald-800 border-emerald-300'
                }`}
              >
                <Volume2 className="w-3.5 h-3.5" />
                ~{metrics.estimated_duration_seconds || 0} seconds
              </span>

              <span className="text-[11px] text-slate-500">
                (Target: &le;60s &bull; Max: 90s)
              </span>
            </div>

            <div className="text-right text-[11px] text-slate-600 font-medium">
              {metrics.word_count} words &bull; {metrics.character_count} chars
            </div>
          </div>

          {/* Voice Duration Visual Bar */}
          <div className="space-y-1">
            <div className="flex items-center justify-between text-[10px] text-slate-500">
              <span>Estimated Audio Duration</span>
              <span className="font-semibold text-slate-700">
                {metrics.estimated_duration_seconds || 0}s / 60s recommended
              </span>
            </div>
            <div className="w-full bg-slate-100 h-2 rounded-full overflow-hidden flex">
              <div
                className={`h-full transition-all duration-300 ${
                  (metrics.estimated_duration_seconds || 0) > 90
                    ? 'bg-rose-500'
                    : (metrics.estimated_duration_seconds || 0) > 60
                    ? 'bg-amber-500'
                    : 'bg-emerald-500'
                }`}
                style={{
                  width: `${Math.min(100, Math.max(3, (((metrics.estimated_duration_seconds || 0) / 90) * 100)))}%`,
                }}
              />
            </div>
          </div>
        </div>
      )}

      {/* CHANNEL: WhatsApp Free-form vs Template Limits */}
      {channel === 'WhatsApp' && (
        <div className="space-y-3">
          <div className="flex items-center justify-between flex-wrap gap-2 text-xs">
            <div className="flex items-center gap-2">
              <span
                className={`inline-flex items-center gap-1 px-3 py-1 rounded-lg font-bold border text-xs ${
                  metrics.character_count > 4096
                    ? 'bg-rose-50 text-rose-800 border-rose-300'
                    : metrics.character_count > 1024
                    ? 'bg-amber-50 text-amber-800 border-amber-300'
                    : 'bg-emerald-50 text-emerald-800 border-emerald-300'
                }`}
              >
                <MessageSquare className="w-3.5 h-3.5" />
                {metrics.character_count} / 1,024 chars
              </span>
              <span className="text-[11px] text-slate-500">
                (Free-form limit: 4,096 &bull; Template limit: 1,024)
              </span>
            </div>
            <div className="text-right text-[11px] text-slate-600 font-medium">
              {metrics.word_count} words
            </div>
          </div>

          <div className="space-y-1">
            <div className="flex items-center justify-between text-[10px] text-slate-500">
              <span>Optimal Readability Boundary</span>
              <span className="font-semibold text-slate-700">
                {metrics.character_count <= 1024
                  ? `${1024 - metrics.character_count} chars to recommended threshold`
                  : `${metrics.character_count - 1024} chars past recommended threshold`}
              </span>
            </div>
            <div className="w-full bg-slate-100 h-2 rounded-full overflow-hidden flex">
              <div
                className={`h-full transition-all duration-300 ${
                  metrics.character_count > 4096
                    ? 'bg-rose-500'
                    : metrics.character_count > 1024
                    ? 'bg-amber-500'
                    : 'bg-emerald-500'
                }`}
                style={{
                  width: `${Math.min(100, Math.max(3, ((metrics.character_count / 1024) * 100)))}%`,
                }}
              />
            </div>
          </div>
        </div>
      )}

      {/* CHANNEL: Email Subject & Body Metrics */}
      {channel === 'Email' && (
        <div className="space-y-3">
          <div className="flex items-center justify-between flex-wrap gap-2 text-xs">
            <div className="flex items-center gap-2">
              <span
                className={`inline-flex items-center gap-1 px-3 py-1 rounded-lg font-bold border text-xs ${
                  metrics.word_count > 800
                    ? 'bg-amber-50 text-amber-800 border-amber-300'
                    : 'bg-emerald-50 text-emerald-800 border-emerald-300'
                }`}
              >
                <Mail className="w-3.5 h-3.5" />
                {metrics.word_count} words
              </span>
              <span className="text-[11px] text-slate-500">
                (Recommended: 200 - 800 words)
              </span>
            </div>
            <div className="text-right text-[11px] text-slate-600 font-medium">
              {metrics.character_count} chars
            </div>
          </div>
        </div>
      )}

      {/* Structured Telecom Constraint Warnings */}
      {warnings.length > 0 && (
        <div className="space-y-2 pt-2 border-t border-slate-100">
          <div className="text-[11px] font-bold text-slate-700 flex items-center gap-1">
            <AlertCircle className="w-3.5 h-3.5 text-amber-600" />
            Telephony & Channel Advisories ({warnings.length})
          </div>

          <div className="space-y-1.5">
            {warnings.map((warn, idx) => {
              const cfg = SEVERITY_CONFIG[warn.severity] || SEVERITY_CONFIG.INFO;
              return (
                <div
                  key={`${warn.code}-${idx}`}
                  className={`p-2.5 rounded-lg border text-xs flex items-start gap-2 ${cfg.bg}`}
                >
                  <AlertCircle className={`w-4 h-4 flex-shrink-0 mt-0.5 ${cfg.iconColor}`} />
                  <div className="space-y-0.5">
                    <div className="flex items-center gap-1.5 flex-wrap">
                      <span className={`text-[9px] font-bold px-1.5 py-0.2 rounded font-mono border ${cfg.badge}`}>
                        {warn.severity}
                      </span>
                      <span className="font-mono text-[10px] font-semibold text-slate-700">
                        {warn.code}
                      </span>
                    </div>
                    <p className="text-[11px] leading-relaxed opacity-95">
                      {warn.message}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

