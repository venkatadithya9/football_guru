import React, { useState } from 'react';
import { Loader2, Check, ChevronDown, AlertCircle } from 'lucide-react';
import { ToolCall } from '../types/chat';

interface ToolCallCardProps {
  toolCall: ToolCall;
}

export const ToolCallCard: React.FC<ToolCallCardProps> = ({ toolCall }) => {
  const [isOpen, setIsOpen] = useState(false);
  const isRunning = toolCall.status === 'running';
  const isCompleted = toolCall.status === 'completed';
  const isError = toolCall.status === 'error';

  const paramsStr = Object.entries(toolCall.input || {})
    .map(([k, v]) => `${k}=${JSON.stringify(v)}`)
    .join(', ');

  return (
    <div className="w-full my-1 text-xs border border-slate-800/80 rounded-lg bg-[#0d1320] overflow-hidden">
      <button
        type="button"
        onClick={() => !isRunning && setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between px-3 py-1.5 text-left text-slate-400 hover:text-slate-200 transition-colors"
      >
        <div className="flex items-center gap-2 font-mono text-[11px] truncate">
          {isRunning && <Loader2 className="w-3.5 h-3.5 text-emerald-500 animate-spin flex-shrink-0" />}
          {isCompleted && <Check className="w-3.5 h-3.5 text-emerald-400 flex-shrink-0" />}
          {isError && <AlertCircle className="w-3.5 h-3.5 text-rose-400 flex-shrink-0" />}

          <span className="text-slate-300 font-semibold">{toolCall.tool}</span>
          {paramsStr && (
            <span className="text-slate-500 truncate">({paramsStr})</span>
          )}
        </div>

        {!isRunning && toolCall.output && (
          <div className="flex items-center gap-1 text-[11px] text-slate-500 flex-shrink-0 ml-2">
            <span>{isOpen ? 'hide' : 'output'}</span>
            <ChevronDown className={`w-3 h-3 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
          </div>
        )}
      </button>

      {isOpen && toolCall.output && (
        <div className="px-3 py-2 border-t border-slate-800/60 text-slate-400 font-mono text-[11px] leading-relaxed max-h-52 overflow-y-auto whitespace-pre-wrap">
          {toolCall.output}
        </div>
      )}
    </div>
  );
};
