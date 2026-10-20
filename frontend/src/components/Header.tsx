import React from 'react';
import { RotateCcw, Sparkles } from 'lucide-react';
import { QuotaBadge } from './QuotaBadge';
import { QuotaStatus, ServerStatus } from '../types/chat';

interface HeaderProps {
  onReset: () => void;
  quota: QuotaStatus | null;
  serverStatus: ServerStatus;
  isStreaming: boolean;
}

export const Header: React.FC<HeaderProps> = ({
  onReset,
  quota,
  serverStatus,
  isStreaming,
}) => {
  return (
    <header className="sticky top-0 z-30 w-full border-b border-pitch-border/80 bg-turf-950/80 backdrop-blur-md px-4 sm:px-6 py-3">
      <div className="max-w-6xl mx-auto flex items-center justify-between gap-4">
        {/* Logo and Brand */}
        <div className="flex items-center gap-3">
          <div className="relative flex items-center justify-center w-10 h-10 rounded-xl bg-gradient-to-br from-pitch-dark via-pitch-green to-emerald-400 text-white shadow-lg shadow-pitch-green/20 ring-1 ring-white/20">
            <span className="text-xl select-none animate-spin-slow" style={{ animationDuration: '12s' }}>
              ⚽
            </span>
            <div className="absolute -bottom-0.5 -right-0.5 w-3 h-3 bg-pitch-neon rounded-full ring-2 ring-turf-950" />
          </div>

          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-base sm:text-lg font-bold tracking-tight text-white flex items-center gap-1.5">
                Football Guru
                <span className="text-xs px-1.5 py-0.5 rounded bg-pitch-green/20 text-pitch-light font-semibold border border-pitch-green/30">
                  AGENTIC
                </span>
              </h1>
            </div>
            <p className="text-xs text-slate-400 hidden sm:block">
              Analytical tactician powered by Gemini 3.8 & Football MCP
            </p>
          </div>
        </div>

        {/* Status Badges & Actions */}
        <div className="flex items-center gap-2 sm:gap-4">
          <QuotaBadge quota={quota} serverStatus={serverStatus} />

          <button
            onClick={onReset}
            disabled={isStreaming}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-slate-300 hover:text-white bg-turf-850 hover:bg-turf-800 border border-slate-700/80 rounded-lg transition-all duration-150 disabled:opacity-40 disabled:cursor-not-allowed hover:border-slate-500 shadow-sm active:scale-95"
            title="Start a new tactical session"
          >
            <RotateCcw className="w-3.5 h-3.5 text-slate-400 group-hover:rotate-180 transition-transform" />
            <span className="hidden sm:inline">New Session</span>
          </button>
        </div>
      </div>
    </header>
  );
};
