import React, { useState, useEffect } from 'react';
import { X, AlertCircle, CheckCircle2, User, Mail, Phone, MapPin, Globe, Briefcase, Building } from 'lucide-react';
import { createAudienceMember, updateAudienceMember } from '../../services/audienceService';

const INDIAN_LANGUAGES = [
  { code: 'en', label: 'English (en)' },
  { code: 'hi', label: 'Hindi (hi)' },
  { code: 'ta', label: 'Tamil (ta)' },
  { code: 'te', label: 'Telugu (te)' },
  { code: 'bn', label: 'Bengali (bn)' },
  { code: 'mr', label: 'Marathi (mr)' },
  { code: 'gu', label: 'Gujarati (gu)' },
  { code: 'kn', label: 'Kannada (kn)' },
  { code: 'ml', label: 'Malayalam (ml)' },
  { code: 'pa', label: 'Punjabi (pa)' },
  { code: 'or', label: 'Odia (or)' },
  { code: 'as', label: 'Assamese (as)' },
];

export default function AudienceFormModal({ isOpen, onClose, member = null, onSuccess }) {
  const isEdit = !!member;

  const [formData, setFormData] = useState({
    name: '',
    email: '',
    phone: '',
    age: '',
    gender: '',
    city: '',
    state: '',
    preferred_language: 'en',
    occupation: '',
    organization_department: '',
    preferred_channel: 'Email',
    consent_status: null,
  });

  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');
  const [validationErrors, setValidationErrors] = useState({});

  useEffect(() => {
    if (member) {
      setFormData({
        name: member.name || '',
        email: member.email || '',
        phone: member.phone || '',
        age: member.age !== null && member.age !== undefined ? member.age : '',
        gender: member.gender || '',
        city: member.city || '',
        state: member.state || '',
        preferred_language: member.preferred_language || 'en',
        occupation: member.occupation || '',
        organization_department: member.organization_department || '',
        preferred_channel: member.preferred_channel || 'Email',
        consent_status: member.consent_status !== undefined ? member.consent_status : null,
      });
    } else {
      setFormData({
        name: '',
        email: '',
        phone: '',
        age: '',
        gender: '',
        city: '',
        state: '',
        preferred_language: 'en',
        occupation: '',
        organization_department: '',
        preferred_channel: 'Email',
        consent_status: null,
      });
    }
    setErrorMessage('');
    setValidationErrors({});
  }, [member, isOpen]);

  if (!isOpen) return null;

  const validate = () => {
    const errors = {};
    if (!formData.name.trim()) {
      errors.name = 'Full name is required.';
    }

    if (!formData.email.trim() && !formData.phone.trim()) {
      errors.contact = 'At least an email address or a phone number is required.';
    }

    if (formData.email.trim() && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.email.trim())) {
      errors.email = 'Please enter a valid email address.';
    }

    if (formData.preferred_channel === 'Email' && !formData.email.trim()) {
      errors.preferred_channel = 'Email address is required when preferred channel is Email.';
    }

    if ((formData.preferred_channel === 'SMS' || formData.preferred_channel === 'WhatsApp') && !formData.phone.trim()) {
      errors.preferred_channel = `Phone number is required when preferred channel is ${formData.preferred_channel}.`;
    }

    if (formData.age !== '') {
      const ageNum = Number(formData.age);
      if (isNaN(ageNum) || ageNum < 1 || ageNum > 120) {
        errors.age = 'Age must be a valid number between 1 and 120.';
      }
    }

    setValidationErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!validate()) return;

    setLoading(true);
    setErrorMessage('');

    try {
      const payload = {
        name: formData.name.trim(),
        email: formData.email.trim() || null,
        phone: formData.phone.trim() || null,
        age: formData.age !== '' ? Number(formData.age) : null,
        gender: formData.gender.trim() || null,
        city: formData.city.trim() || null,
        state: formData.state.trim() || null,
        preferred_language: formData.preferred_language,
        occupation: formData.occupation.trim() || null,
        organization_department: formData.organization_department.trim() || null,
        preferred_channel: formData.preferred_channel,
        consent_status: formData.consent_status,
      };

      if (isEdit) {
        await updateAudienceMember(member.id, payload);
      } else {
        await createAudienceMember(payload);
      }

      onSuccess(isEdit ? 'Audience member updated successfully.' : 'New audience member added successfully.');
      onClose();
    } catch (err) {
      const detail = err.response?.data?.detail;
      if (typeof detail === 'string') {
        setErrorMessage(detail);
      } else if (Array.isArray(detail)) {
        setErrorMessage(detail.map((d) => d.msg || 'Validation error').join(', '));
      } else {
        setErrorMessage(err.message || 'An error occurred while saving audience record.');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="relative bg-white rounded-2xl max-w-2xl w-full shadow-2xl border border-slate-200 overflow-hidden my-8">
        {/* Header */}
        <div className="px-6 py-4 bg-slate-50 border-b border-slate-200 flex items-center justify-between">
          <div>
            <h3 className="text-lg font-bold text-slate-900">
              {isEdit ? 'Edit Audience Member' : 'Add Audience Member'}
            </h3>
            <p className="text-xs text-slate-500">
              {isEdit ? 'Update contact handles, demographics, and channel preferences.' : 'Register a new citizen or organizational contact for communication.'}
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-200 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSubmit} className="p-6 space-y-5">
          {errorMessage && (
            <div className="p-3.5 bg-rose-50 border border-rose-200 rounded-xl flex items-start gap-2.5 text-xs text-rose-700">
              <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5 text-rose-500" />
              <span>{errorMessage}</span>
            </div>
          )}

          {validationErrors.contact && (
            <div className="p-3 bg-amber-50 border border-amber-200 rounded-xl flex items-start gap-2 text-xs text-amber-800">
              <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5 text-amber-600" />
              <span>{validationErrors.contact}</span>
            </div>
          )}

          {/* Full Name */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              Full Name <span className="text-rose-500">*</span>
            </label>
            <div className="relative">
              <User className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
              <input
                type="text"
                required
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                placeholder="e.g. Dr. Anita Desai"
                className={`w-full pl-9 pr-3 py-2 text-sm rounded-lg border ${
                  validationErrors.name ? 'border-rose-400 ring-1 ring-rose-300' : 'border-slate-300'
                } focus:outline-none focus:ring-2 focus:ring-brand-500`}
              />
            </div>
            {validationErrors.name && (
              <p className="text-[11px] text-rose-600 mt-1">{validationErrors.name}</p>
            )}
          </div>

          {/* Contact Handles Grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Email Address
              </label>
              <div className="relative">
                <Mail className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
                <input
                  type="email"
                  value={formData.email}
                  onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                  placeholder="anita@agency.gov.in"
                  className={`w-full pl-9 pr-3 py-2 text-sm rounded-lg border ${
                    validationErrors.email ? 'border-rose-400 ring-1 ring-rose-300' : 'border-slate-300'
                  } focus:outline-none focus:ring-2 focus:ring-brand-500`}
                />
              </div>
              {validationErrors.email && (
                <p className="text-[11px] text-rose-600 mt-1">{validationErrors.email}</p>
              )}
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Phone Number (Mobile)
              </label>
              <div className="relative">
                <Phone className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
                <input
                  type="text"
                  value={formData.phone}
                  onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                  placeholder="+91 98765 43210"
                  className="w-full pl-9 pr-3 py-2 text-sm rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-brand-500"
                />
              </div>
              <p className="text-[10px] text-slate-400 mt-0.5">Include country code if applicable.</p>
            </div>
          </div>

          {/* Demographics: Age & Gender */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Age</label>
              <input
                type="number"
                min="1"
                max="120"
                value={formData.age}
                onChange={(e) => setFormData({ ...formData, age: e.target.value })}
                placeholder="e.g. 35"
                className={`w-full px-3 py-2 text-sm rounded-lg border ${
                  validationErrors.age ? 'border-rose-400 ring-1 ring-rose-300' : 'border-slate-300'
                } focus:outline-none focus:ring-2 focus:ring-brand-500`}
              />
              {validationErrors.age && (
                <p className="text-[11px] text-rose-600 mt-1">{validationErrors.age}</p>
              )}
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Gender</label>
              <select
                value={formData.gender}
                onChange={(e) => setFormData({ ...formData, gender: e.target.value })}
                className="w-full px-3 py-2 text-sm rounded-lg border border-slate-300 bg-white focus:outline-none focus:ring-2 focus:ring-brand-500"
              >
                <option value="">Unspecified</option>
                <option value="Male">Male</option>
                <option value="Female">Female</option>
                <option value="Other">Other</option>
                <option value="Non-binary">Non-binary</option>
                <option value="Prefer not to say">Prefer not to say</option>
              </select>
            </div>
          </div>

          {/* Location: City & State */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">City</label>
              <div className="relative">
                <MapPin className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
                <input
                  type="text"
                  value={formData.city}
                  onChange={(e) => setFormData({ ...formData, city: e.target.value })}
                  placeholder="e.g. Bengaluru"
                  className="w-full pl-9 pr-3 py-2 text-sm rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-brand-500"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">State / Province</label>
              <input
                type="text"
                value={formData.state}
                onChange={(e) => setFormData({ ...formData, state: e.target.value })}
                placeholder="e.g. Karnataka"
                className="w-full px-3 py-2 text-sm rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-brand-500"
              />
            </div>
          </div>

          {/* Channel & Language Preferences */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Preferred Language <span className="text-rose-500">*</span>
              </label>
              <div className="relative">
                <Globe className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
                <select
                  value={formData.preferred_language}
                  onChange={(e) => setFormData({ ...formData, preferred_language: e.target.value })}
                  className="w-full pl-9 pr-3 py-2 text-sm rounded-lg border border-slate-300 bg-white focus:outline-none focus:ring-2 focus:ring-brand-500"
                >
                  {INDIAN_LANGUAGES.map((lang) => (
                    <option key={lang.code} value={lang.code}>
                      {lang.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Preferred Channel <span className="text-rose-500">*</span>
              </label>
              <select
                value={formData.preferred_channel}
                onChange={(e) => setFormData({ ...formData, preferred_channel: e.target.value })}
                className={`w-full px-3 py-2 text-sm rounded-lg border ${
                  validationErrors.preferred_channel ? 'border-rose-400 ring-1 ring-rose-300' : 'border-slate-300'
                } bg-white focus:outline-none focus:ring-2 focus:ring-brand-500`}
              >
                <option value="Email">Email</option>
                <option value="SMS">SMS</option>
                <option value="WhatsApp">WhatsApp</option>
              </select>
              {validationErrors.preferred_channel && (
                <p className="text-[11px] text-rose-600 mt-1">{validationErrors.preferred_channel}</p>
              )}
            </div>
          </div>

          {/* Occupation & Department */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Occupation</label>
              <div className="relative">
                <Briefcase className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
                <input
                  type="text"
                  value={formData.occupation}
                  onChange={(e) => setFormData({ ...formData, occupation: e.target.value })}
                  placeholder="e.g. Healthcare Officer"
                  className="w-full pl-9 pr-3 py-2 text-sm rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-brand-500"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Department / Organization</label>
              <div className="relative">
                <Building className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
                <input
                  type="text"
                  value={formData.organization_department}
                  onChange={(e) => setFormData({ ...formData, organization_department: e.target.value })}
                  placeholder="e.g. Public Health Division"
                  className="w-full pl-9 pr-3 py-2 text-sm rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-brand-500"
                />
              </div>
            </div>
          </div>

          {/* Communication Consent Selector (Tri-State for DPDP / Privacy Compliance) */}
          <div className="pt-3 border-t border-slate-200 space-y-2">
            <div className="flex flex-col">
              <span className="text-xs font-semibold text-slate-800">Communication Consent Status</span>
              <span className="text-[11px] text-slate-500">
                DPDP/privacy compliance: Explicit opt-in required before dispatching awareness campaigns.
              </span>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
              <button
                type="button"
                onClick={() => setFormData({ ...formData, consent_status: true })}
                className={`flex items-center justify-center gap-1.5 p-2.5 rounded-xl border text-xs font-medium transition ${
                  formData.consent_status === true
                    ? 'border-emerald-500 bg-emerald-50 text-emerald-800 ring-2 ring-emerald-400/30 font-semibold'
                    : 'border-slate-200 bg-white text-slate-600 hover:bg-slate-50'
                }`}
              >
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                Opted In
              </button>

              <button
                type="button"
                onClick={() => setFormData({ ...formData, consent_status: null })}
                className={`flex items-center justify-center gap-1.5 p-2.5 rounded-xl border text-xs font-medium transition ${
                  formData.consent_status === null || formData.consent_status === undefined
                    ? 'border-slate-400 bg-slate-100 text-slate-800 ring-2 ring-slate-400/30 font-semibold'
                    : 'border-slate-200 bg-white text-slate-600 hover:bg-slate-50'
                }`}
              >
                <AlertCircle className="w-3.5 h-3.5 text-slate-500" />
                Unconfirmed
              </button>

              <button
                type="button"
                onClick={() => setFormData({ ...formData, consent_status: false })}
                className={`flex items-center justify-center gap-1.5 p-2.5 rounded-xl border text-xs font-medium transition ${
                  formData.consent_status === false
                    ? 'border-rose-400 bg-rose-50 text-rose-800 ring-2 ring-rose-300/40 font-semibold'
                    : 'border-slate-200 bg-white text-slate-600 hover:bg-slate-50'
                }`}
              >
                <X className="w-3.5 h-3.5 text-rose-500" />
                Opted Out
              </button>
            </div>
          </div>

          {/* Action Buttons */}
          <div className="pt-4 border-t border-slate-200 flex items-center justify-end gap-3">
            <button
              type="button"
              onClick={onClose}
              disabled={loading}
              className="px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-100 border border-slate-300 rounded-lg transition"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="inline-flex items-center gap-1.5 px-5 py-2 text-xs font-semibold text-white bg-brand-600 hover:bg-brand-700 disabled:opacity-60 rounded-lg shadow-sm transition"
            >
              {loading ? 'Saving...' : isEdit ? 'Save Changes' : 'Create Recipient'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

