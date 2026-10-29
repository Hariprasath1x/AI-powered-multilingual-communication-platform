import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Shield, ArrowLeft, Clock } from 'lucide-react';

export default function PlaceholderAuth() {
  const location = useLocation();
  const isRegister = location.pathname.includes('register');
  const taskTitle = isRegister ? 'Task 2: User Registration' : 'Task 3: JWT Authentication & RBAC';

  return (
    <div className="min-h-[70vh] flex items-center justify-center py-16 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full space-y-6 bg-white p-8 rounded-2xl border border-slate-200 shadow-xl text-center">
        <div className="w-12 h-12 rounded-xl bg-brand-100 text-brand-600 flex items-center justify-center mx-auto">
          <Shield className="w-6 h-6" />
        </div>

        <div className="space-y-2">
          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-amber-50 text-amber-700 border border-amber-200">
            <Clock className="w-3.5 h-3.5" />
            <span>Scheduled for Next Task</span>
          </div>
          <h2 className="text-2xl font-bold text-slate-900">
            {isRegister ? 'User Registration' : 'Account Sign In'}
          </h2>
          <p className="text-sm text-slate-600">
            This module will be activated in <span className="font-semibold text-slate-800">{taskTitle}</span>.
            The database tables (<code className="bg-slate-100 px-1 py-0.5 rounded text-xs text-brand-700">roles</code> and <code className="bg-slate-100 px-1 py-0.5 rounded text-xs text-brand-700">users</code>) have already been created and verified.
          </p>
        </div>

        <div className="pt-4 border-t border-slate-100">
          <Link
            to="/"
            className="inline-flex items-center justify-center gap-2 w-full px-4 py-2.5 rounded-lg text-sm font-semibold text-slate-700 bg-slate-100 hover:bg-slate-200 transition"
          >
            <ArrowLeft className="w-4 h-4" />
            Return to Landing Page
          </Link>
        </div>
      </div>
    </div>
  );
}

