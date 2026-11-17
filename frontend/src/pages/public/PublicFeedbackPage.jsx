import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  Star,
  MessageSquare,
  CheckCircle2,
  AlertCircle,
  ShieldCheck,
  Globe,
  Send,
  Loader2,
  Building2,
  ArrowRight,
} from 'lucide-react';
import { getPublicFeedbackInfo, submitPublicFeedback } from '../../services/campaignService';

const RATING_LABELS = {
  1: 'Poor / असंतोषजनक',
  2: 'Fair / साधारण',
  3: 'Average / ठीक',
  4: 'Good / अच्छा',
  5: 'Excellent / उत्कृष्ट',
};

const SUPPORTED_LANGUAGES = [
  { code: 'en', name: 'English' },
  { code: 'hi', name: 'हिंदी (Hindi)' },
  { code: 'ta', name: 'தமிழ் (Tamil)' },
  { code: 'te', name: 'తెలుగు (Telugu)' },
  { code: 'kn', name: 'ಕನ್ನಡ (Kannada)' },
  { code: 'mr', name: 'मराठी (Marathi)' },
  { code: 'bn', name: 'বাংলা (Bengali)' },
  { code: 'gu', name: 'ગુજરાતી (Gujarati)' },
];

export default function PublicFeedbackPage() {
  const { token } = useParams();

  const [campaignInfo, setCampaignInfo] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);

  const [rating, setRating] = useState(0);
  const [hoverRating, setHoverRating] = useState(0);
  const [comment, setComment] = useState('');
  const [selectedLanguage, setSelectedLanguage] = useState('en');

  const [submitting, setSubmitting] = useState(false);
  const [submitSuccess, setSubmitSuccess] = useState(false);
  const [submitError, setSubmitError] = useState(null);

  useEffect(() => {
    async function loadInfo() {
      if (!token) {
        setLoadError('Feedback token is missing.');
        setLoading(false);
        return;
      }
      try {
        setLoading(true);
        const info = await getPublicFeedbackInfo(token);
        setCampaignInfo(info);
        if (info.preferred_language) {
          setSelectedLanguage(info.preferred_language);
        }
      } catch (err) {
        const detail = err.response?.data?.detail || 'Invalid or expired feedback link.';
        setLoadError(detail);
      } finally {
        setLoading(false);
      }
    }
    loadInfo();
  }, [token]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (rating === 0) {
      setSubmitError('Please select a star rating between 1 and 5.');
      return;
    }

    try {
      setSubmitting(true);
      setSubmitError(null);
      await submitPublicFeedback({
        feedback_token: token,
        rating,
        comment: comment.trim() || null,
        language: selectedLanguage,
      });
      setSubmitSuccess(true);
    } catch (err) {
      const msg = err.response?.data?.detail || 'Failed to submit feedback. Please try again.';
      setSubmitError(msg);
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center p-4">
        <Loader2 className="w-10 h-10 text-indigo-600 animate-spin mb-4" />
        <p className="text-slate-600 font-medium">Loading feedback portal...</p>
      </div>
    );
  }

  if (loadError) {
    return (
      <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center p-4">
        <div className="max-w-md w-full bg-white rounded-2xl shadow-xl border border-slate-200 p-8 text-center">
          <div className="w-16 h-16 bg-red-50 text-red-600 rounded-full flex items-center justify-center mx-auto mb-4 border border-red-100">
            <AlertCircle className="w-8 h-8" />
          </div>
          <h2 className="text-xl font-bold text-slate-900 mb-2">Feedback Link Invalid</h2>
          <p className="text-slate-600 text-sm mb-6">{loadError}</p>
          <Link
            to="/announcements"
            className="inline-flex items-center gap-2 px-5 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl text-sm font-semibold transition"
          >
            View Public Announcements
            <ArrowRight className="w-4 h-4" />
          </Link>
        </div>
      </div>
    );
  }

  if (submitSuccess) {
    return (
      <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center p-4">
        <div className="max-w-lg w-full bg-white rounded-3xl shadow-xl border border-slate-200 p-8 sm:p-10 text-center animate-in fade-in duration-300">
          <div className="w-20 h-20 bg-emerald-50 text-emerald-600 rounded-3xl flex items-center justify-center mx-auto mb-6 border border-emerald-100 shadow-sm">
            <CheckCircle2 className="w-10 h-10" />
          </div>
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200 mb-4">
            <ShieldCheck className="w-3.5 h-3.5" />
            Official Response Recorded
          </span>
          <h2 className="text-2xl font-bold text-slate-900 mb-3">Thank You for Your Feedback!</h2>
          <p className="text-slate-600 text-sm leading-relaxed mb-6">
            Your response regarding <span className="font-semibold text-slate-800">{campaignInfo?.campaign_name}</span> has been securely recorded. Public feedback directly helps government teams improve citizen communication and service delivery.
          </p>
          <div className="bg-slate-50 rounded-2xl p-4 border border-slate-200/60 mb-6 text-left text-xs text-slate-500 space-y-1">
            <p><strong>Campaign:</strong> {campaignInfo?.campaign_name}</p>
            <p><strong>Rating:</strong> {rating} / 5 Stars</p>
            {comment && <p className="italic">"{comment}"</p>}
          </div>
          <Link
            to="/announcements"
            className="inline-flex items-center justify-center gap-2 w-full py-3 bg-slate-900 hover:bg-slate-800 text-white rounded-xl text-sm font-semibold transition"
          >
            Return to Public Portal
            <ArrowRight className="w-4 h-4" />
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-100 via-slate-50 to-white py-12 px-4 sm:px-6">
      <div className="max-w-xl mx-auto">
        {/* Header Branding */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-indigo-50 border border-indigo-200/60 text-indigo-700 text-xs font-semibold mb-3">
            <Building2 className="w-3.5 h-3.5" />
            Official Citizen Feedback Portal
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">
            {campaignInfo?.campaign_name}
          </h1>
          {campaignInfo?.campaign_objective && (
            <p className="text-sm text-slate-600 mt-2 max-w-md mx-auto">
              {campaignInfo.campaign_objective}
            </p>
          )}
        </div>

        {/* Feedback Card */}
        <div className="bg-white rounded-3xl shadow-xl border border-slate-200/80 p-6 sm:p-8">
          {submitError && (
            <div className="mb-6 p-4 rounded-2xl bg-red-50 border border-red-200 flex items-start gap-3 text-red-700 text-sm">
              <AlertCircle className="w-5 h-5 shrink-0 mt-0.5" />
              <div>{submitError}</div>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-6">
            {/* Language Preference */}
            <div>
              <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                <Globe className="w-3.5 h-3.5 text-slate-400" />
                Response Language / भाषा
              </label>
              <select
                value={selectedLanguage}
                onChange={(e) => setSelectedLanguage(e.target.value)}
                className="w-full px-4 py-2.5 rounded-xl border border-slate-300 bg-white text-slate-900 text-sm font-medium focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 shadow-xs"
              >
                {SUPPORTED_LANGUAGES.map((lang) => (
                  <option key={lang.code} value={lang.code}>
                    {lang.name}
                  </option>
                ))}
              </select>
            </div>

            {/* Star Rating */}
            <div className="text-center py-4 bg-slate-50/80 rounded-2xl border border-slate-200/60">
              <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-3">
                How would you rate this service or advisory?
              </label>
              <div className="flex items-center justify-center gap-2 sm:gap-3">
                {[1, 2, 3, 4, 5].map((star) => (
                  <button
                    key={star}
                    type="button"
                    onClick={() => setRating(star)}
                    onMouseEnter={() => setHoverRating(star)}
                    onMouseLeave={() => setHoverRating(0)}
                    className="p-1 focus:outline-none transition-transform hover:scale-115 active:scale-95"
                    aria-label={`${star} star`}
                  >
                    <Star
                      className={`w-9 h-9 sm:w-10 sm:h-10 transition-colors ${
                        (hoverRating || rating) >= star
                          ? 'fill-amber-400 text-amber-400'
                          : 'fill-slate-100 text-slate-300'
                      }`}
                    />
                  </button>
                ))}
              </div>
              <div className="h-6 mt-2">
                {(hoverRating || rating) > 0 ? (
                  <span className="text-xs font-semibold text-slate-700">
                    {RATING_LABELS[hoverRating || rating]}
                  </span>
                ) : (
                  <span className="text-xs text-slate-400">Click a star to rate (1 to 5)</span>
                )}
              </div>
            </div>

            {/* Comment Area */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider flex items-center gap-1.5">
                  <MessageSquare className="w-3.5 h-3.5 text-slate-400" />
                  Your Comments or Questions (Optional)
                </label>
                <span className="text-xs text-slate-400">{comment.length} / 2000</span>
              </div>
              <textarea
                rows={4}
                value={comment}
                onChange={(e) => setComment(e.target.value)}
                maxLength={2000}
                placeholder="Share your experience, questions about the advisory, booth timings, or suggestions in any language..."
                className="w-full px-4 py-3 rounded-2xl border border-slate-300 bg-white text-slate-900 text-sm placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 shadow-xs resize-none"
              />
            </div>

            {/* Privacy Safeguard Notice */}
            <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200/60 flex items-start gap-2.5 text-xs text-slate-500">
              <ShieldCheck className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
              <p>
                <strong>Privacy Guaranteed:</strong> Your feedback is linked solely to this official notification. No personal identifiers or phone numbers are publicly exposed.
              </p>
            </div>

            {/* Submit Button */}
            <button
              type="submit"
              disabled={submitting}
              className="w-full py-3.5 px-6 rounded-2xl bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-sm shadow-md hover:shadow-lg transition flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {submitting ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Submitting Feedback...
                </>
              ) : (
                <>
                  <Send className="w-4 h-4" />
                  Submit Official Feedback
                </>
              )}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
