import React, { createContext, useContext, useState, useEffect } from 'react';

const TRANSLATIONS = {
  en: {
    platformTitle: 'MassCommAI Platform',
    dashboard: 'Platform Dashboard',
    analytics: 'Analytics & Insights',
    audience: 'Audience Database',
    segments: 'Audience Segments',
    templates: 'Message Templates',
    campaigns: 'Campaign Studio',
    contentStudio: 'AI Content Studio',
    distribution: 'Multi-Channel Distribution',
    deliveryTracking: 'Delivery Tracking',
    feedback: 'Citizen Feedback',
    userGovernance: 'User Governance & Roles',
    channelSettings: 'Channel Settings',
    systemConnected: 'API & DB Connected',
    connecting: 'Connecting...',
    systemOffline: 'API Offline',
    switchLang: 'Language',
    newCampaign: 'New Campaign',
    exportReport: 'Export Report',
    refresh: 'Refresh',
    allChannels: 'All Channels',
    overview: 'Overview',
  },
  hi: {
    platformTitle: 'मासकॉम एआई मंच',
    dashboard: 'मंच डैशबोर्ड',
    analytics: 'विश्लेषण एवं अंतर्दृष्टि',
    audience: 'नागरिक डेटाबेस',
    segments: 'लक्षित वर्ग विभाजन',
    templates: 'संदेश प्रारूप',
    campaigns: 'अभियान केंद्र',
    contentStudio: 'एआई सामग्री स्टूडियो',
    distribution: 'बहु-चैनल वितरण',
    deliveryTracking: 'वितरण ट्रैकिंग',
    feedback: 'नागरिक प्रतिक्रिया',
    userGovernance: 'उपयोगकर्ता प्रशासन',
    channelSettings: 'चैनल सेटिंग्स',
    systemConnected: 'एपीआई एवं डेटाबेस सक्रिय',
    connecting: 'संपर्क जारी...',
    systemOffline: 'एपीआई ऑफ़लाइन',
    switchLang: 'भाषा',
    newCampaign: 'नया अभियान',
    exportReport: 'रिपोर्ट निर्यात',
    refresh: 'रीफ़्रेश करें',
    allChannels: 'सभी चैनल',
    overview: 'अवलोकन',
  },
};

const LanguageContext = createContext();

export function LanguageProvider({ children }) {
  const [currentLang, setCurrentLang] = useState(() => {
    return localStorage.getItem('masscomm_ui_lang') || 'en';
  });

  useEffect(() => {
    localStorage.setItem('masscomm_ui_lang', currentLang);
  }, [currentLang]);

  const toggleLanguage = () => {
    setCurrentLang((prev) => (prev === 'en' ? 'hi' : 'en'));
  };

  const setLanguage = (lang) => {
    if (lang === 'en' || lang === 'hi') {
      setCurrentLang(lang);
    }
  };

  const t = (key) => {
    return TRANSLATIONS[currentLang]?.[key] || TRANSLATIONS['en']?.[key] || key;
  };

  return (
    <LanguageContext.Provider value={{ currentLang, setLanguage, toggleLanguage, t }}>
      {children}
    </LanguageContext.Provider>
  );
}

export function useLanguage() {
  const context = useContext(LanguageContext);
  if (!context) {
    throw new Error('useLanguage must be used within a LanguageProvider');
  }
  return context;
}
