import React from 'react';
import { Languages, ArrowRight, CheckCircle2, AlertTriangle, FileText, Radio, Info } from 'lucide-react';

const LANGUAGE_LABELS = {
  en: 'English',
  hi: 'Hindi (हिन्दी)',
  kn: 'Kannada (ಕನ್ನಡ)',
  ta: 'Tamil (தமிழ்)',
  te: 'Telugu (తెలుగు)',
  mr: 'Marathi (मराठी)',
  bn: 'Bengali (বাংলা)',
  gu: 'Gujarati (ગુજરાતી)',
  ml: 'Malayalam (മലയാളം)',
  pa: 'Punjabi (ਪੰਜਾਬੀ)',
  ur: 'Urdu (اردو)',
};

export default function ContentTranslationComparisonView({ asset, parentAsset }) {
  if (!asset || !asset.target_language || !parentAsset) return null;

  const sourceLang = (parentAsset.source_language || 'en').toLowerCase();
  const targetLang = (asset.target_language || '').toLowerCase();
  const isUrdu = targetLang === 'ur';

  const parentPlaceholders = parentAsset.detected_placeholders || [];
  const childPlaceholders = asset.detected_placeholders || [];

  return (
    <div className="p-5 rounded-xl bg-slate-50 border border-slate-200 shadow-2xs space-y-4">
      
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Languages className="w-4 h-4 text-blue-600" />
          <h4 className="text-xs font-bold text-slate-800 uppercase tracking-wider font-mono">
            Translation Fidelity & Discrepancy Comparison
          </h4>
        </div>
        <div className="flex items-center gap-1.5 text-xs font-semibold">
          <span className="px-2 py-0.5 rounded-md bg-white border border-slate-200 text-slate-800">
            {LANGUAGE_LABELS[sourceLang] || sourceLang} (Original)
          </span>
          <ArrowRight className="w-3.5 h-3.5 text-slate-400" />
          <span className="px-2 py-0.5 rounded-md bg-slate-900 text-white shadow-2xs">
            {LANGUAGE_LABELS[targetLang] || targetLang} (Variant){isUrdu ? ' [RTL]' : ''}
          </span>
        </div>
      </div>

      {/* Side-by-Side Comparison */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
        
        {/* Original */}
        <div className="p-3.5 rounded-lg bg-white border border-slate-200 space-y-2">
          <div className="flex items-center justify-between pb-1.5 border-b border-slate-200 text-[11px] font-semibold text-slate-500">
            <span>Original Copy</span>
            <span className="font-mono">#{parentAsset.id}</span>
          </div>
          <div className="font-bold text-slate-900">{parentAsset.title}</div>
          <p className="text-slate-600 leading-relaxed whitespace-pre-line text-[11px]">
            {parentAsset.body}
          </p>
          {parentAsset.call_to_action && (
            <div className="text-[10px] font-semibold text-slate-500 pt-1">
              CTA: {parentAsset.call_to_action}
            </div>
          )}
        </div>

        {/* Translation (with RTL support for Urdu) */}
        <div className={`p-3.5 rounded-lg bg-white border border-blue-200 space-y-2 ${isUrdu ? 'text-right' : ''}`} dir={isUrdu ? 'rtl' : 'ltr'}>
          <div className="flex items-center justify-between pb-1.5 border-b border-slate-200 text-[11px] font-semibold text-blue-600" dir="ltr">
            <span>Translated Variant {isUrdu ? '(RTL Layout)' : ''}</span>
            <span className="font-mono">#{asset.id}</span>
          </div>
          <div className="font-bold text-slate-900">{asset.title}</div>
          <p className="text-slate-600 leading-relaxed whitespace-pre-line text-[11px]">
            {asset.body}
          </p>
          {asset.call_to_action && (
            <div className="text-[10px] font-semibold text-blue-600 pt-1">
              CTA: {asset.call_to_action}
            </div>
          )}
        </div>
      </div>

      {/* Placeholder Comparison Checks */}
      <div className="p-3 bg-white/80 rounded-xl border border-indigo-100 flex items-center justify-between flex-wrap gap-2 text-xs">
        <span className="text-[11px] font-semibold text-slate-600">
          Dynamic Personalization Preservation:
        </span>
        <div className="flex items-center gap-1.5 flex-wrap">
          {parentPlaceholders.length === 0 ? (
            <span className="text-[11px] text-slate-400 italic">No placeholders in original copy</span>
          ) : (
            parentPlaceholders.map((ph) => {
              const isPreserved = childPlaceholders.includes(ph);
              return (
                <span
                  key={ph}
                  className={`inline-flex items-center gap-1 px-2 py-0.5 rounded font-mono text-[10px] font-medium border ${
                    isPreserved
                      ? 'bg-emerald-50 text-emerald-800 border-emerald-200'
                      : 'bg-rose-50 text-rose-800 border-rose-200'
                  }`}
                >
                  {isPreserved ? <CheckCircle2 className="w-3 h-3 text-emerald-600" /> : <AlertTriangle className="w-3 h-3 text-rose-600" />}
                  {ph} {isPreserved ? 'Preserved' : 'Missing!'}
                </span>
              );
            })
          )}
        </div>
      </div>

      {/* Telephony & Channel Constraint Divergence */}
      {(parentAsset.channel_metrics || asset.channel_metrics) && (
        <div className="p-3.5 bg-white/90 rounded-xl border border-indigo-100 space-y-2 text-xs">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold text-slate-700 flex items-center gap-1.5">
              <Radio className="w-3.5 h-3.5 text-indigo-600" />
              Telecommunications & Constraint Divergence ({asset.channel})
            </span>
            <span className="text-[10px] text-slate-400">
              Deterministic Telecom Engine
            </span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5 pt-1">
            {/* Metric 1: Encoding / Pacing */}
            <div className="p-2 rounded-lg bg-slate-50 border border-slate-200 space-y-1">
              <div className="text-[10px] text-slate-500 font-semibold uppercase">
                {asset.channel === 'SMS' ? 'Encoding Scheme' : asset.channel === 'Voice' ? 'Pacing & Duration' : 'Length Growth'}
              </div>
              <div className="flex items-center gap-1.5 font-bold text-slate-900">
                {asset.channel === 'SMS' ? (
                  <>
                    <span className="text-slate-600">{parentAsset.channel_metrics?.sms?.encoding || 'GSM-7'}</span>
                    <ArrowRight className="w-3 h-3 text-slate-400" />
                    <span className={asset.channel_metrics?.sms?.encoding === 'UCS-2' ? 'text-indigo-600' : 'text-slate-900'}>
                      {asset.channel_metrics?.sms?.encoding || 'UCS-2'}
                    </span>
                  </>
                ) : asset.channel === 'Voice' ? (
                  <>
                    <span>~{parentAsset.voice_duration_seconds || 0}s</span>
                    <ArrowRight className="w-3 h-3 text-slate-400" />
                    <span className="text-indigo-600">~{asset.voice_duration_seconds || 0}s</span>
                  </>
                ) : (
                  <>
                    <span>{parentAsset.character_count || 0}c</span>
                    <ArrowRight className="w-3 h-3 text-slate-400" />
                    <span className="text-indigo-600">{asset.character_count || 0}c</span>
                  </>
                )}
              </div>
            </div>

            {/* Metric 2: Segments / Units */}
            <div className="p-2 rounded-lg bg-slate-50 border border-slate-200 space-y-1">
              <div className="text-[10px] text-slate-500 font-semibold uppercase">
                {asset.channel === 'SMS' ? 'SMS Segments' : 'Character / Word Count'}
              </div>
              <div className="flex items-center gap-1.5 font-bold text-slate-900">
                {asset.channel === 'SMS' ? (
                  <>
                    <span>{parentAsset.sms_segment_count || 1} seg</span>
                    <ArrowRight className="w-3 h-3 text-slate-400" />
                    <span className={asset.sms_segment_count > (parentAsset.sms_segment_count || 1) ? 'text-amber-600' : 'text-emerald-600'}>
                      {asset.sms_segment_count || 1} seg{asset.sms_segment_count > 1 ? ' (Multipart)' : ''}
                    </span>
                  </>
                ) : (
                  <>
                    <span>{parentAsset.word_count || 0} words</span>
                    <ArrowRight className="w-3 h-3 text-slate-400" />
                    <span className="text-indigo-600">{asset.word_count || 0} words</span>
                  </>
                )}
              </div>
            </div>

            {/* Metric 3: Boundary Safety */}
            <div className="p-2 rounded-lg bg-slate-50 border border-slate-200 space-y-1">
              <div className="text-[10px] text-slate-500 font-semibold uppercase">
                Technical Limit Safety
              </div>
              <div className="flex items-center gap-1 font-semibold">
                {asset.channel_metrics?.is_within_hard_limit ? (
                  <span className="inline-flex items-center gap-1 text-emerald-700">
                    <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                    Within Hard Limits
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1 text-rose-700">
                    <AlertTriangle className="w-3 h-3 text-rose-600" />
                    Hard Limit Exceeded
                  </span>
                )}
              </div>
            </div>
          </div>

          {/* Encoding shift callout if shifted to UCS-2 */}
          {asset.channel === 'SMS' &&
            parentAsset.channel_metrics?.sms?.encoding === 'GSM-7' &&
            asset.channel_metrics?.sms?.encoding === 'UCS-2' && (
              <div className="p-2 rounded-lg bg-indigo-50/70 border border-indigo-200 text-[11px] text-indigo-900 flex items-start gap-1.5">
                <Info className="w-3.5 h-3.5 text-indigo-600 flex-shrink-0 mt-0.5" />
                <span>
                  <strong>Encoding Shift:</strong> Translation to {LANGUAGE_LABELS[targetLang] || targetLang} requires 16-bit UCS-2 encoding. Segment capacity switches from 160/153 septets to 70/67 code units, which naturally multiplies required SMS segments.
                </span>
              </div>
            )}
        </div>
      )}

    </div>
  );
}

