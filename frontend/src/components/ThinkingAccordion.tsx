import React, { useState } from 'react';
import { ChevronDown } from 'lucide-react';

interface ThinkingAccordionProps {
  thought: string;
  isStreaming: boolean;
  hasOutput: boolean;
}

export const ThinkingAccordion: React.FC<ThinkingAccordionProps> = ({
  thought,
  isStreaming,
}) => {
  const [isOpen, setIsOpen] = useState(isStreaming);

  if (!thought) return null;

  return (
    <div className="w-full my-2 text-xs border border-slate-800/80 rounded-lg bg-[#0d1320] overflow-hidden">
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between px-3 py-1.5 text-slate-400 hover:text-slate-200 transition-colors"
      >
        <div className="flex items-center gap-2">
          {isStreaming && (
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
          )}
          <span className="font-mono text-[11px]">
            {isStreaming ? 'Thinking...' : 'Thought process'}
          </span>
        </div>
        <div className="flex items-center gap-1 text-[11px] text-slate-500">
          <span>{isOpen ? 'hide' : 'show'}</span>
          <ChevronDown className={`w-3 h-3 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
        </div>
      </button>

      {isOpen && (
        <div className="px-3 py-2 border-t border-slate-800/60 text-slate-400 font-mono text-[11px] leading-relaxed max-h-60 overflow-y-auto whitespace-pre-wrap">
          {thought}
        </div>
      )}
    </div>
  );
};
