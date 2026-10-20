/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        turf: {
          950: '#070b12',
          900: '#0b111c',
          850: '#0f1726',
          800: '#141e30',
          700: '#1e2c45',
          600: '#2c3e5e',
        },
        pitch: {
          green: '#10b981',
          neon: '#22c55e',
          light: '#34d399',
          dark: '#059669',
        },
        golden: '#f59e0b',
        referee: '#ef4444',
      },
      fontFamily: {
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'Monaco', 'Consolas', 'monospace'],
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'spin-slow': 'spin 3s linear infinite',
      },
    },
  },
  plugins: [],
}
