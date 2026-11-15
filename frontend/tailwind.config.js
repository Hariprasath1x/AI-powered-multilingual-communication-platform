/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Modern, simple, practical operational color system
        brand: {
          50: '#EFF6FF',
          100: '#DBEAFE',
          200: '#BFDBFE',
          300: '#93C5FD',
          400: '#60A5FA',
          500: '#3B82F6',
          600: '#2563EB', // Primary action Blue
          700: '#1D4ED8', // Primary hover
          800: '#1E40AF',
          900: '#1E3A8A',
          950: '#172554',
        },
        teal: {
          50: '#F0FDFA',
          100: '#CCFBF1',
          200: '#99F6E4',
          300: '#5EEAD4',
          400: '#2DD4BF',
          500: '#14B8A6',
          600: '#0D9488',
          700: '#0F766E', // Secondary accent Teal
          800: '#115E59',
          900: '#134E4A',
          950: '#042F2E',
        },
        slate: {
          50: '#F8FAFC',  // Main background
          100: '#F1F5F9',
          200: '#E2E8F0', // Main borders
          300: '#CBD5E1',
          400: '#94A3B8',
          500: '#64748B', // Secondary text
          600: '#475569',
          700: '#334155',
          800: '#1E293B', // Main text
          900: '#0F172A', // Dark accents / nav
          950: '#020617',
        },
        // Backward-compatible semantic color aliases
        accent: {
          DEFAULT: '#2563EB',
          hover: '#1D4ED8',
          active: '#1E40AF',
          light: '#EFF6FF',
          border: '#BFDBFE',
        },
        navy: {
          50: '#F8FAFC',
          100: '#F1F5F9',
          200: '#E2E8F0',
          300: '#CBD5E1',
          400: '#94A3B8',
          500: '#64748B',
          600: '#475569',
          700: '#334155',
          800: '#1E293B',
          900: '#0F172A',
          950: '#020617',
        },
        ink: {
          DEFAULT: '#1E293B',
          light: '#64748B',
          muted: '#94A3B8',
          border: '#E2E8F0',
        },
        ivory: {
          50: '#FFFFFF',
          100: '#F8FAFC',
          200: '#F1F5F9',
          300: '#E2E8F0',
          400: '#CBD5E1',
          500: '#94A3B8',
        },
        soft: {
          blue: '#EFF6FF',
          green: '#F0FDF4',
          purple: '#FAF5FF',
          amber: '#FFFBEB',
          rose: '#FEF2F2',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
      },
      boxShadow: {
        'subtle': '0 1px 2px 0 rgba(0, 0, 0, 0.05)',
        'elevated': '0 4px 6px -1px rgba(0, 0, 0, 0.08), 0 2px 4px -2px rgba(0, 0, 0, 0.05)',
      },
    },
  },
  plugins: [],
}

