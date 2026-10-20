import React from 'react';
import { Shield, Activity, AlertTriangle } from 'lucide-react';
import { QuotaStatus, ServerStatus } from '../types/chat';

interface QuotaBadgeProps {
  quota: QuotaStatus | null;
  serverStatus: ServerStatus;
}

export const QuotaBadge: React.FC<QuotaBadgeProps> = ({ quota, serverStatus }) => {
  const isMcpReady = serverStatus.status === 'ready';

  return (
    <div className="flex items-center gap-2 sm:gap-3 text-xs">
      {/* MCP Connection Status */}
      <div
        className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full border transition-colors ${
          isMcpReady
            ? 'bg-emerald-950/60 border-emerald-500/40 text-emerald-400'
            : 'bg-amber-950/60 border-amber-500/40 text-amber-300'
        }`}
        title={serverStatus.error || (isMcpReady ? `Connected to MCP with ${serverStatus.tools_count} tools` : 'MCP Server disconnected')}
      >
        <span className={`w-2 h-2 rounded-full ${isMcpReady ? 'bg-emerald-400 animate-pulse' : 'bg-amber-400'}`} />
        <span className="font-medium hidden sm:inline">
          {isMcpReady ? `MCP Active (${serverStatus.tools_count} tools)` : 'MCP Offline'}
        </span>
        <span className="font-medium sm:hidden">
          {isMcpReady ? 'MCP' : 'Offline'}
        </span>
      </div>

      {/* Daily API Quota Gauge */}
      {quota && (
        <div
          className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full border transition-colors ${
            quota.requests_remaining > 20
              ? 'bg-turf-850 border-slate-700/60 text-slate-300'
              : quota.requests_remaining > 10
              ? 'bg-amber-950/60 border-amber-500/40 text-amber-300'
              : 'bg-rose-950/60 border-rose-500/40 text-rose-400'
          }`}
          title={`Daily Quota: ${quota.requests_remaining} requests remaining out of ${quota.max_daily_quota}. Safe threshold: ${quota.safety_threshold}`}
        >
          <Shield className="w-3.5 h-3.5 text-pitch-neon" />
          <span className="font-mono">
            <span className="text-white font-semibold">{quota.requests_remaining}</span>
            <span className="text-slate-400">/{quota.max_daily_quota} req</span>
          </span>
        </div>
      )}
    </div>
  );
};
