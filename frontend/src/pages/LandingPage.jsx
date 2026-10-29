import React from 'react';
import { Link } from 'react-router-dom';
import { 
  Globe2, 
  Sparkles, 
  Send, 
  BarChart3, 
  Layers, 
  CheckCircle2, 
  Users, 
  ShieldAlert, 
  Languages, 
  Hospital, 
  GraduationCap, 
  Megaphone,
  ArrowRight,
  Database,
  Cpu,
  Clock
} from 'lucide-react';

export default function LandingPage() {
  const features = [
    {
      icon: Languages,
      title: 'Multilingual Communication',
      tagline: 'Break linguistic barriers across diverse communities',
      description: 'Support major Indian languages including Hindi, Tamil, Telugu, Kannada, Marathi, and Bengali while safeguarding dynamic placeholder tokens like {name} and {area}.',
      badge: 'Indic NLP Ready',
      color: 'from-blue-500/10 to-indigo-500/10 text-brand-600',
    },
    {
      icon: Sparkles,
      title: 'AI-Powered Content Generation',
      tagline: 'Context-aware drafting for critical announcements',
      description: 'Generate tailored announcements, awareness notifications, and emergency alerts adjusted for formal, urgent, or advisory tones with strict character limits for SMS and Push.',
      badge: 'LLM Assisted',
      color: 'from-purple-500/10 to-pink-500/10 text-purple-600',
    },
    {
      icon: Send,
      title: 'Multi-Channel Distribution',
      tagline: 'Unified outreach across citizen touchpoints',
      description: 'Orchestrate campaigns across Email, SMS, WhatsApp Business API, Push Notifications, and Web Broadcasts with automated delivery tracking and intelligent retry policies.',
      badge: 'Omnichannel',
      color: 'from-emerald-500/10 to-teal-500/10 text-emerald-600',
    },
    {
      icon: BarChart3,
      title: 'Engagement Analytics & Sentiment',
      tagline: 'Data-driven visibility into outreach effectiveness',
      description: 'Monitor open rates, click-through rates, and recipient feedback with sentiment classification to evaluate public reaction and optimize subsequent awareness drives.',
      badge: 'Actionable Insights',
      color: 'from-amber-500/10 to-orange-500/10 text-amber-600',
    },
  ];

  const steps = [
    {
      step: '01',
      title: 'Define Campaign Objectives',
      description: 'Establish awareness drives, health alerts, or public advisories. Configure priority, scheduling, and distribution windows.',
    },
    {
      step: '02',
      title: 'Target & Segment Audience',
      description: 'Group recipients by geographic region, preferred language, occupation, or demographic filters with instant query preview.',
    },
    {
      step: '03',
      title: 'AI Content & Translation',
      description: 'Draft context-rich content using structured templates, auto-translate into target regional dialects, and verify compliance.',
    },
    {
      step: '04',
      title: 'Select Distribution Channels',
      description: 'Dispatch simultaneously across Email, SMS, WhatsApp, and Web based on recipient channel preferences and urgency level.',
    },
    {
      step: '05',
      title: 'Track Engagement & Feedback',
      description: 'Inspect real-time delivery telemetry, citizen sentiment, and response metrics via interactive performance dashboards.',
    },
  ];

  const impactDomains = [
    {
      icon: Hospital,
      title: 'Healthcare & Public Health',
      description: 'Vaccination drives, epidemic prevention advisories, and maternal health guidance delivered in localized dialects.',
    },
    {
      icon: ShieldAlert,
      title: 'Emergency & Disaster Alerts',
      description: 'High-priority weather warnings, flood evacuation notices, and civil defense bulletins broadcast within seconds.',
    },
    {
      icon: GraduationCap,
      title: 'Education & Public Schemes',
      description: 'Scholarship enrollment alerts, skilling program registrations, and academic schedules reaching rural students.',
    },
    {
      icon: Megaphone,
      title: 'Civic & Institutional Notices',
      description: 'Municipal utility updates, civic welfare programs, and policy announcements with guaranteed citizen reach.',
    },
  ];

  return (
    <div className="flex flex-col">
      
      {/* HERO SECTION */}
      <section className="relative overflow-hidden pt-12 pb-20 lg:pt-20 lg:pb-28 gradient-mesh border-b border-slate-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 items-center">
            
            {/* Hero Copy */}
            <div className="lg:col-span-7 space-y-6 text-center lg:text-left">
              <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-semibold bg-brand-100 text-brand-800 border border-brand-200 shadow-sm">
                <Sparkles className="w-3.5 h-3.5 text-brand-600" />
                <span>Infosys Springboard Virtual Internship &bull; Milestone 1</span>
              </div>

              <h1 className="text-4xl sm:text-5xl lg:text-6xl font-extrabold text-slate-900 tracking-tight leading-[1.15]">
                AI-Powered Multilingual <br className="hidden sm:inline" />
                <span className="text-transparent bg-clip-text bg-gradient-to-r from-brand-600 to-indigo-600">
                  Public Awareness & Mass Communication
                </span>
              </h1>

              <p className="text-lg sm:text-xl text-slate-600 max-w-2xl leading-relaxed">
                Empower government departments, healthcare institutions, and organizations to create,
                translate, personalize, and distribute awareness campaigns across diverse linguistic communities with automated delivery and real-time analytics.
              </p>

              {/* CTAs */}
              <div className="flex flex-wrap items-center justify-center lg:justify-start gap-4 pt-2">
                <Link
                  to="/register"
                  className="inline-flex items-center gap-2 px-6 py-3.5 rounded-xl font-semibold text-white bg-brand-600 hover:bg-brand-700 shadow-lg shadow-brand-500/25 transition active:scale-[0.98]"
                >
                  Get Started
                  <ArrowRight className="w-4 h-4" />
                </Link>
                <a
                  href="#features"
                  className="inline-flex items-center gap-2 px-6 py-3.5 rounded-xl font-semibold text-slate-700 bg-white hover:bg-slate-50 border border-slate-300 shadow-sm transition hover:border-slate-400"
                >
                  Explore Platform
                </a>
              </div>

              {/* Architecture highlights pill */}
              <div className="pt-6 border-t border-slate-200/80 flex flex-wrap items-center justify-center lg:justify-start gap-6 text-xs text-slate-500">
                <div className="flex items-center gap-1.5 font-medium">
                  <Database className="w-4 h-4 text-brand-600" />
                  <span>PostgreSQL 14+ Relational Engine</span>
                </div>
                <div className="flex items-center gap-1.5 font-medium">
                  <Cpu className="w-4 h-4 text-brand-600" />
                  <span>FastAPI Asynchronous Backend</span>
                </div>
                <div className="flex items-center gap-1.5 font-medium">
                  <Globe2 className="w-4 h-4 text-brand-600" />
                  <span>Multi-Language Indic Support</span>
                </div>
              </div>
            </div>

            {/* Hero Visual Mockup */}
            <div className="lg:col-span-5">
              <div className="relative mx-auto max-w-md lg:max-w-none">
                
                {/* Glow backdrop */}
                <div className="absolute -inset-1 rounded-2xl bg-gradient-to-r from-brand-500 to-indigo-500 opacity-20 blur-xl"></div>
                
                {/* Card Container */}
                <div className="relative rounded-2xl bg-white border border-slate-200/90 shadow-2xl p-6 space-y-5">
                  
                  {/* Mock Dashboard Top Bar */}
                  <div className="flex items-center justify-between border-b border-slate-100 pb-4">
                    <div className="flex items-center gap-2">
                      <div className="w-3 h-3 rounded-full bg-rose-500" />
                      <div className="w-3 h-3 rounded-full bg-amber-500" />
                      <div className="w-3 h-3 rounded-full bg-emerald-500" />
                      <span className="text-xs font-semibold text-slate-600 ml-2">Campaign Dispatcher</span>
                    </div>
                    <span className="text-[11px] font-semibold px-2.5 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200">
                      High Priority Alert
                    </span>
                  </div>

                  {/* Multilingual Preview Card */}
                  <div className="bg-slate-50 rounded-xl p-4 border border-slate-200 space-y-3">
                    <div className="flex items-center justify-between text-xs text-slate-500">
                      <span className="font-semibold text-slate-700">Target: Disaster Advisory</span>
                      <span>Reach: 24,500 Citizens</span>
                    </div>

                    <div className="space-y-2 text-xs">
                      <div className="p-2.5 rounded-lg bg-white border border-slate-200 text-slate-800">
                        <span className="font-bold text-brand-600 uppercase text-[10px] block">English:</span>
                        "Heavy rainfall warning in Chennai coastal zones. Please avoid low-lying bridges."
                      </div>
                      <div className="p-2.5 rounded-lg bg-white border border-slate-200 text-slate-800">
                        <span className="font-bold text-brand-600 uppercase text-[10px] block">Tamil (தமிழ்):</span>
                        "சென்னை கடலோரப் பகுதிகளில் பலத்த மழை எச்சரிக்கை. தரைப்பாலங்களை தவிர்க்கவும்."
                      </div>
                      <div className="p-2.5 rounded-lg bg-white border border-slate-200 text-slate-800">
                        <span className="font-bold text-brand-600 uppercase text-[10px] block">Hindi (हिंदी):</span>
                        "चेन्नई तटीय क्षेत्रों में भारी बारिश की चेतावनी। निचले पुलों से बचें।"
                      </div>
                    </div>
                  </div>

                  {/* Channel Metrics Row */}
                  <div className="grid grid-cols-3 gap-2 text-center">
                    <div className="p-2 rounded-lg bg-slate-50 border border-slate-100">
                      <span className="block text-[10px] uppercase font-bold text-slate-400">SMS</span>
                      <span className="text-sm font-bold text-slate-800">99.4%</span>
                    </div>
                    <div className="p-2 rounded-lg bg-slate-50 border border-slate-100">
                      <span className="block text-[10px] uppercase font-bold text-slate-400">WhatsApp</span>
                      <span className="text-sm font-bold text-slate-800">92.1%</span>
                    </div>
                    <div className="p-2 rounded-lg bg-slate-50 border border-slate-100">
                      <span className="block text-[10px] uppercase font-bold text-slate-400">Email</span>
                      <span className="text-sm font-bold text-slate-800">88.7%</span>
                    </div>
                  </div>

                </div>
              </div>
            </div>

          </div>
        </div>
      </section>

      {/* CORE FEATURES SECTION */}
      <section id="features" className="py-20 bg-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          
          <div className="text-center max-w-3xl mx-auto space-y-4 mb-16">
            <h2 className="text-xs font-bold uppercase tracking-widest text-brand-600">
              End-to-End Capabilities
            </h2>
            <p className="text-3xl sm:text-4xl font-extrabold text-slate-900 tracking-tight">
              Engineered for Linguistic Inclusivity & Precision Outreach
            </p>
            <p className="text-slate-600 text-base leading-relaxed">
              Every component of MassCommAI is designed to simplify mass communication while eliminating linguistic misunderstandings during urgent and civic broadcasts.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
            {features.map((feat) => {
              const Icon = feat.icon;
              return (
                <div
                  key={feat.title}
                  className="rounded-2xl p-8 border border-slate-200 bg-white hover:border-brand-300 hover:shadow-xl transition-all duration-200 flex flex-col justify-between group"
                >
                  <div className="space-y-4">
                    <div className="flex items-center justify-between">
                      <div className={`w-12 h-12 rounded-xl flex items-center justify-center bg-gradient-to-br ${feat.color}`}>
                        <Icon className="w-6 h-6" />
                      </div>
                      <span className="text-xs font-semibold px-2.5 py-1 rounded-full bg-slate-100 text-slate-700 border border-slate-200">
                        {feat.badge}
                      </span>
                    </div>

                    <div>
                      <h3 className="text-xl font-bold text-slate-900 group-hover:text-brand-600 transition">
                        {feat.title}
                      </h3>
                      <p className="text-sm font-medium text-slate-500 mt-1">
                        {feat.tagline}
                      </p>
                    </div>

                    <p className="text-sm text-slate-600 leading-relaxed">
                      {feat.description}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>

        </div>
      </section>

      {/* HOW IT WORKS SECTION */}
      <section id="how-it-works" className="py-20 bg-slate-50 border-y border-slate-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          
          <div className="text-center max-w-3xl mx-auto space-y-4 mb-16">
            <h2 className="text-xs font-bold uppercase tracking-widest text-brand-600">
              Communication Workflow
            </h2>
            <p className="text-3xl sm:text-4xl font-extrabold text-slate-900 tracking-tight">
              From Draft to Multilingual Delivery in 5 Steps
            </p>
            <p className="text-slate-600 text-base leading-relaxed">
              A structured lifecycle supporting compliance validation, role approval, and targeted channel orchestration.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-5 gap-6">
            {steps.map((st, idx) => (
              <div
                key={st.step}
                className="relative bg-white rounded-xl p-6 border border-slate-200 shadow-sm flex flex-col justify-between"
              >
                <div className="space-y-3">
                  <div className="text-2xl font-black text-brand-600">
                    {st.step}
                  </div>
                  <h4 className="text-base font-bold text-slate-900">
                    {st.title}
                  </h4>
                  <p className="text-xs text-slate-600 leading-relaxed">
                    {st.description}
                  </p>
                </div>

                <div className="pt-4 mt-4 border-t border-slate-100 flex items-center text-[11px] font-semibold text-slate-400">
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500 mr-1.5" />
                  Step {idx + 1} of 5
                </div>
              </div>
            ))}
          </div>

        </div>
      </section>

      {/* IMPACT DOMAINS SECTION */}
      <section id="impact" className="py-20 bg-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          
          <div className="text-center max-w-3xl mx-auto space-y-4 mb-16">
            <h2 className="text-xs font-bold uppercase tracking-widest text-brand-600">
              Real-World Applications
            </h2>
            <p className="text-3xl sm:text-4xl font-extrabold text-slate-900 tracking-tight">
              Designed for Critical Public Awareness
            </p>
            <p className="text-slate-600 text-base leading-relaxed">
              Serving diverse civic sectors with reliable information delivery when communication clarity matters most.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
            {impactDomains.map((domain) => {
              const Icon = domain.icon;
              return (
                <div
                  key={domain.title}
                  className="rounded-xl p-6 border border-slate-200 bg-slate-50 hover:bg-white hover:border-brand-300 hover:shadow-lg transition space-y-3"
                >
                  <div className="w-10 h-10 rounded-lg bg-brand-100 text-brand-700 flex items-center justify-center">
                    <Icon className="w-5 h-5" />
                  </div>
                  <h3 className="text-base font-bold text-slate-900">
                    {domain.title}
                  </h3>
                  <p className="text-xs text-slate-600 leading-relaxed">
                    {domain.description}
                  </p>
                </div>
              );
            })}
          </div>

        </div>
      </section>

      {/* MILESTONE 1 STATUS CALLOUT */}
      <section className="py-12 bg-slate-900 text-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="rounded-2xl bg-slate-800/80 border border-slate-700 p-8 flex flex-col md:flex-row items-center justify-between gap-6">
            <div className="space-y-2 text-center md:text-left">
              <div className="inline-flex items-center gap-2 text-xs font-semibold px-2.5 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                <CheckCircle2 className="w-3.5 h-3.5" />
                Milestone 1 &bull; Task 1 Complete
              </div>
              <h3 className="text-xl font-bold text-white">
                Database Schema, Alembic Migrations & Foundation Verified
              </h3>
              <p className="text-sm text-slate-400 max-w-xl">
                Ready to proceed to Task 2 (User Registration) and Task 3 (JWT Authentication & Role-Based Access Control).
              </p>
            </div>

            <div className="flex items-center gap-3">
              <Link
                to="/register"
                className="px-5 py-2.5 rounded-lg text-sm font-semibold bg-brand-600 hover:bg-brand-500 text-white transition shadow-md"
              >
                Register Account
              </Link>
              <Link
                to="/login"
                className="px-5 py-2.5 rounded-lg text-sm font-semibold bg-slate-700 hover:bg-slate-600 text-slate-200 transition"
              >
                Sign In
              </Link>
            </div>
          </div>
        </div>
      </section>

    </div>
  );
}
