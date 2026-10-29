import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { 
  UserPlus, 
  Mail, 
  Lock, 
  User, 
  Phone, 
  Building2, 
  Eye, 
  EyeOff, 
  ArrowLeft, 
  CheckCircle2, 
  AlertCircle, 
  Loader2, 
  ShieldCheck 
} from 'lucide-react';
import { registerUser } from '../services/authService';

export default function RegisterPage() {
  const navigate = useNavigate();

  // Form State
  const [formData, setFormData] = useState({
    full_name: '',
    email: '',
    phone: '',
    organization: '',
    password: '',
    confirm_password: '',
  });

  // UI State
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [clientErrors, setClientErrors] = useState({});
  const [serverError, setServerError] = useState('');
  const [registrationSuccess, setRegistrationSuccess] = useState(null);

  // Field change handler
  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
    // Clear field-specific error on edit
    if (clientErrors[name]) {
      setClientErrors((prev) => ({ ...prev, [name]: '' }));
    }
    if (serverError) setServerError('');
  };

  // Client-side validation
  const validateForm = () => {
    const errors = {};
    if (!formData.full_name.trim()) {
      errors.full_name = 'Full name is required.';
    } else if (formData.full_name.trim().length < 2) {
      errors.full_name = 'Name must be at least 2 characters.';
    }

    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!formData.email.trim()) {
      errors.email = 'Email address is required.';
    } else if (!emailRegex.test(formData.email.trim())) {
      errors.email = 'Please enter a valid email address.';
    }

    if (!formData.password) {
      errors.password = 'Password is required.';
    } else if (formData.password.length < 8) {
      errors.password = 'Password must be at least 8 characters long.';
    } else if (new TextEncoder().encode(formData.password).length > 72) {
      errors.password = 'Password cannot exceed 72 bytes.';
    } else if (!/[A-Za-z]/.test(formData.password) || !/\d/.test(formData.password)) {
      errors.password = 'Password must contain at least one letter and one number.';
    }

    if (!formData.confirm_password) {
      errors.confirm_password = 'Please confirm your password.';
    } else if (formData.password !== formData.confirm_password) {
      errors.confirm_password = 'Passwords do not match.';
    }

    setClientErrors(errors);
    return Object.keys(errors).length === 0;
  };

  // Submission handler
  const handleSubmit = async (e) => {
    e.preventDefault();
    setServerError('');

    if (!validateForm()) return;

    setIsSubmitting(true);
    try {
      const result = await registerUser(formData);
      if (result.success) {
        setRegistrationSuccess(result.data.user);
      } else {
        setServerError(result.error);
      }
    } catch (err) {
      setServerError('An unexpected error occurred. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  // Calculate password strength indicator
  const getPasswordStrength = () => {
    const pwd = formData.password;
    if (!pwd) return { label: 'Empty', color: 'bg-slate-200', width: 'w-0' };
    let score = 0;
    if (pwd.length >= 8) score += 1;
    if (/[A-Z]/.test(pwd)) score += 1;
    if (/[0-9]/.test(pwd)) score += 1;
    if (/[^A-Za-z0-9]/.test(pwd)) score += 1;

    switch (score) {
      case 1:
        return { label: 'Weak', color: 'bg-rose-500', width: 'w-1/4' };
      case 2:
        return { label: 'Fair', color: 'bg-amber-500', width: 'w-2/4' };
      case 3:
        return { label: 'Good', color: 'bg-blue-500', width: 'w-3/4' };
      case 4:
        return { label: 'Strong', color: 'bg-emerald-500', width: 'w-full' };
      default:
        return { label: 'Weak', color: 'bg-rose-500', width: 'w-1/4' };
    }
  };

  const strength = getPasswordStrength();

  return (
    <div className="min-h-[85vh] flex items-center justify-center py-12 px-4 sm:px-6 lg:px-8 bg-slate-50">
      <div className="max-w-xl w-full space-y-8">
        
        {/* Navigation Breadcrumb */}
        <div>
          <Link
            to="/"
            className="inline-flex items-center text-xs font-medium text-slate-500 hover:text-brand-600 transition"
          >
            <ArrowLeft className="w-3.5 h-3.5 mr-1" />
            Back to Home
          </Link>
        </div>

        {/* Card Container */}
        <div className="bg-white p-8 sm:p-10 rounded-2xl border border-slate-200/90 shadow-xl space-y-6">
          
          {/* Header */}
          <div className="text-center space-y-2">
            <div className="w-12 h-12 rounded-xl bg-brand-100 text-brand-600 flex items-center justify-center mx-auto shadow-sm">
              <UserPlus className="w-6 h-6" />
            </div>
            <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">
              Create your Account
            </h1>
            <p className="text-sm text-slate-600">
              Join the AI-Powered Multilingual Communication Platform
            </p>
          </div>

          {/* Success State View */}
          {registrationSuccess ? (
            <div className="p-6 rounded-xl bg-emerald-50 border border-emerald-200 space-y-5 text-center">
              <div className="w-12 h-12 rounded-full bg-emerald-100 text-emerald-600 flex items-center justify-center mx-auto">
                <CheckCircle2 className="w-7 h-7" />
              </div>
              
              <div className="space-y-1">
                <h3 className="text-lg font-bold text-emerald-900">
                  Registration Successful!
                </h3>
                <p className="text-sm text-emerald-700">
                  Welcome aboard, <span className="font-semibold">{registrationSuccess.full_name}</span>. Your account has been registered with the <span className="font-semibold">{registrationSuccess.role_name}</span> role.
                </p>
              </div>

              <div className="p-3 bg-white rounded-lg border border-emerald-100 text-xs text-slate-600 space-y-1 text-left">
                <div><span className="font-semibold text-slate-700">Account Email:</span> {registrationSuccess.email}</div>
                <div><span className="font-semibold text-slate-700">Organization:</span> {registrationSuccess.organization || 'Not specified'}</div>
                <div><span className="font-semibold text-slate-700">Account ID:</span> #{registrationSuccess.id}</div>
              </div>

              <div className="pt-2 flex flex-col sm:flex-row items-center justify-center gap-3">
                <Link
                  to="/login"
                  className="w-full sm:w-auto px-6 py-2.5 rounded-lg text-sm font-semibold text-white bg-emerald-600 hover:bg-emerald-700 shadow-sm transition"
                >
                  Proceed to Login
                </Link>
                <Link
                  to="/"
                  className="w-full sm:w-auto px-5 py-2.5 rounded-lg text-sm font-medium text-slate-700 bg-white border border-slate-200 hover:bg-slate-50 transition"
                >
                  Return to Home
                </Link>
              </div>
            </div>
          ) : (
            /* Registration Form */
            <form onSubmit={handleSubmit} className="space-y-5" noValidate>
              
              {/* Server-Side Error Banner */}
              {serverError && (
                <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 flex items-start gap-3 text-rose-800 text-sm">
                  <AlertCircle className="w-5 h-5 flex-shrink-0 text-rose-600 mt-0.5" />
                  <div className="flex-grow font-medium leading-relaxed">
                    {serverError}
                  </div>
                </div>
              )}

              {/* Full Name Field */}
              <div>
                <label htmlFor="full_name" className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                  Full Name <span className="text-rose-500">*</span>
                </label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
                    <User className="w-4 h-4" />
                  </div>
                  <input
                    id="full_name"
                    name="full_name"
                    type="text"
                    required
                    value={formData.full_name}
                    onChange={handleChange}
                    placeholder="e.g. Dr. Anita Desai"
                    className={`block w-full pl-10 pr-3.5 py-2.5 text-sm rounded-xl border ${clientErrors.full_name ? 'border-rose-300 focus:ring-rose-500 focus:border-rose-500 bg-rose-50/30' : 'border-slate-300 focus:ring-brand-500 focus:border-brand-500'} focus:outline-none focus:ring-2`}
                  />
                </div>
                {clientErrors.full_name && (
                  <p className="mt-1 text-xs text-rose-600">{clientErrors.full_name}</p>
                )}
              </div>

              {/* Email Address Field */}
              <div>
                <label htmlFor="email" className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                  Email Address <span className="text-rose-500">*</span>
                </label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
                    <Mail className="w-4 h-4" />
                  </div>
                  <input
                    id="email"
                    name="email"
                    type="email"
                    required
                    value={formData.email}
                    onChange={handleChange}
                    placeholder="e.g. anita.desai@health.gov.in"
                    className={`block w-full pl-10 pr-3.5 py-2.5 text-sm rounded-xl border ${clientErrors.email ? 'border-rose-300 focus:ring-rose-500 focus:border-rose-500 bg-rose-50/30' : 'border-slate-300 focus:ring-brand-500 focus:border-brand-500'} focus:outline-none focus:ring-2`}
                  />
                </div>
                {clientErrors.email && (
                  <p className="mt-1 text-xs text-rose-600">{clientErrors.email}</p>
                )}
              </div>

              {/* Grid: Phone & Organization */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {/* Phone Number */}
                <div>
                  <label htmlFor="phone" className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                    Phone Number
                  </label>
                  <div className="relative">
                    <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
                      <Phone className="w-4 h-4" />
                    </div>
                    <input
                      id="phone"
                      name="phone"
                      type="tel"
                      value={formData.phone}
                      onChange={handleChange}
                      placeholder="+91 98765 43210"
                      className="block w-full pl-10 pr-3.5 py-2.5 text-sm rounded-xl border border-slate-300 focus:ring-brand-500 focus:border-brand-500 focus:outline-none focus:ring-2"
                    />
                  </div>
                </div>

                {/* Organization */}
                <div>
                  <label htmlFor="organization" className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                    Organization
                  </label>
                  <div className="relative">
                    <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
                      <Building2 className="w-4 h-4" />
                    </div>
                    <input
                      id="organization"
                      name="organization"
                      type="text"
                      value={formData.organization}
                      onChange={handleChange}
                      placeholder="e.g. Health Directorate"
                      className="block w-full pl-10 pr-3.5 py-2.5 text-sm rounded-xl border border-slate-300 focus:ring-brand-500 focus:border-brand-500 focus:outline-none focus:ring-2"
                    />
                  </div>
                </div>
              </div>

              {/* Account Role Policy Information */}
              <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-2">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-semibold text-slate-700">Assigned Platform Role:</span>
                  <span className="inline-flex items-center gap-1 font-semibold text-brand-700 bg-brand-50 px-2.5 py-0.5 rounded-full border border-brand-200">
                    <ShieldCheck className="w-3.5 h-3.5 text-brand-600" />
                    Communication Team (Standard)
                  </span>
                </div>
                <p className="text-[11px] text-slate-500 leading-relaxed">
                  Public self-registration assigns standard communication permissions. Elevated access such as <strong>Campaign Manager</strong> or <strong>Administrator</strong> requires administrative authorization and assignment.
                </p>
              </div>

              {/* Password Field */}
              <div>
                <label htmlFor="password" className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                  Password <span className="text-rose-500">*</span>
                </label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
                    <Lock className="w-4 h-4" />
                  </div>
                  <input
                    id="password"
                    name="password"
                    type={showPassword ? 'text' : 'password'}
                    required
                    value={formData.password}
                    onChange={handleChange}
                    placeholder="Min. 8 characters with letters & numbers"
                    className={`block w-full pl-10 pr-10 py-2.5 text-sm rounded-xl border ${clientErrors.password ? 'border-rose-300 focus:ring-rose-500 focus:border-rose-500 bg-rose-50/30' : 'border-slate-300 focus:ring-brand-500 focus:border-brand-500'} focus:outline-none focus:ring-2`}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute inset-y-0 right-0 pr-3.5 flex items-center text-slate-400 hover:text-slate-600 focus:outline-none"
                    aria-label="Toggle password visibility"
                  >
                    {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
                {clientErrors.password && (
                  <p className="mt-1 text-xs text-rose-600">{clientErrors.password}</p>
                )}

                {/* Password Strength Meter */}
                {formData.password && (
                  <div className="mt-2 space-y-1">
                    <div className="h-1.5 w-full bg-slate-100 rounded-full overflow-hidden">
                      <div className={`h-full ${strength.color} ${strength.width} transition-all duration-300`} />
                    </div>
                    <div className="flex justify-between items-center text-[11px] text-slate-500">
                      <span>Password strength: <strong className="text-slate-700">{strength.label}</strong></span>
                      <span>Min 8 chars, letter + number</span>
                    </div>
                  </div>
                )}
              </div>

              {/* Confirm Password Field */}
              <div>
                <label htmlFor="confirm_password" className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                  Confirm Password <span className="text-rose-500">*</span>
                </label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
                    <Lock className="w-4 h-4" />
                  </div>
                  <input
                    id="confirm_password"
                    name="confirm_password"
                    type={showConfirmPassword ? 'text' : 'password'}
                    required
                    value={formData.confirm_password}
                    onChange={handleChange}
                    placeholder="Repeat password"
                    className={`block w-full pl-10 pr-10 py-2.5 text-sm rounded-xl border ${clientErrors.confirm_password ? 'border-rose-300 focus:ring-rose-500 focus:border-rose-500 bg-rose-50/30' : 'border-slate-300 focus:ring-brand-500 focus:border-brand-500'} focus:outline-none focus:ring-2`}
                  />
                  <button
                    type="button"
                    onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                    className="absolute inset-y-0 right-0 pr-3.5 flex items-center text-slate-400 hover:text-slate-600 focus:outline-none"
                    aria-label="Toggle confirm password visibility"
                  >
                    {showConfirmPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
                {clientErrors.confirm_password && (
                  <p className="mt-1 text-xs text-rose-600">{clientErrors.confirm_password}</p>
                )}
              </div>

              {/* Submit CTA */}
              <div className="pt-2">
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="w-full inline-flex items-center justify-center py-3 px-4 border border-transparent rounded-xl shadow-sm text-sm font-semibold text-white bg-brand-600 hover:bg-brand-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand-500 disabled:opacity-60 disabled:cursor-not-allowed transition"
                >
                  {isSubmitting ? (
                    <>
                      <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                      Creating Account...
                    </>
                  ) : (
                    'Create Account'
                  )}
                </button>
              </div>

              {/* Footer link to Login */}
              <div className="pt-2 text-center text-xs text-slate-500">
                Already registered?{' '}
                <Link to="/login" className="font-semibold text-brand-600 hover:text-brand-700 transition">
                  Sign in here
                </Link>
              </div>

            </form>
          )}

        </div>
      </div>
    </div>
  );
}

