import React from 'react';
import { MessageSquareShare, Github, Heart } from 'lucide-react';
import { API_BASE_URL } from '../../services/api';

export default function Footer() {
  return (
    <footer className="bg-slate-900 text-slate-300 border-t border-slate-800">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
          
          {/* Brand & Purpose */}
          <div className="md:col-span-2 space-y-3">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center text-white">
                <MessageSquareShare className="w-4 h-4" />
              </div>
              <span className="text-lg font-bold tracking-tight text-white">
                MassComm<span className="text-blue-400">AI</span>
              </span>
            </div>
            <p className="text-xs text-slate-400 max-w-md leading-relaxed">
              AI-Powered Multilingual Public Awareness and Mass Communication Platform.
              Empowering civic authorities, educators, healthcare agencies, and public institutions
              to bridge linguistic barriers and deliver mission-critical announcements at scale.
            </p>
            <div className="text-xs text-slate-500 font-mono">
              Infosys Springboard Virtual Internship &bull; Telecommunication Infrastructure
            </div>
          </div>

          {/* Platform Sections */}
          <div>
            <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-200 mb-3">
              Platform
            </h4>
            <ul className="space-y-2 text-xs text-slate-400">
              <li><a href="#features" className="hover:text-white transition">Core Features</a></li>
              <li><a href="#how-it-works" className="hover:text-white transition">Workflow Engine</a></li>
              <li><a href="#impact" className="hover:text-white transition">Impact Domains</a></li>
              <li><a href={`${API_BASE_URL}/docs`} target="_blank" rel="noreferrer" className="hover:text-blue-400 transition">API Documentation</a></li>
            </ul>
          </div>

          {/* Technology & Architecture */}
          <div>
            <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-200 mb-3">
              Architecture
            </h4>
            <ul className="space-y-2 text-xs text-slate-400 font-mono">
              <li>FastAPI & SQLAlchemy 2.0</li>
              <li>PostgreSQL & Alembic</li>
              <li>React 18 & Tailwind CSS</li>
              <li>Role-Based Access Control</li>
            </ul>
          </div>

        </div>

        {/* Bottom Line */}
        <div className="mt-8 pt-6 border-t border-slate-800 flex flex-col sm:flex-row items-center justify-between text-xs text-slate-500 gap-3">
          <p>&copy; {new Date().getFullYear()} MassCommAI. Developed for Infosys Springboard Internship.</p>
          <div className="flex items-center gap-4">
            <span className="inline-flex items-center gap-1">
              Backend Status: <span className="text-green-400 font-medium">PostgreSQL Ready</span>
            </span>
            <span>&bull;</span>
            <span className="font-mono">Milestone 2</span>
          </div>
        </div>
      </div>
    </footer>
  );
}

