import React, { useState, useRef, useEffect } from 'react';
import { ArrowUp, Square } from 'lucide-react';

interface InputBarProps {
  onSendMessage: (text: string) => void;
  onStop: () => void;
  isStreaming: boolean;
  disabled?: boolean;
}

export const InputBar: React.FC<InputBarProps> = ({
  onSendMessage,
  onStop,
  isStreaming,
  disabled = false,
}) => {
  const [input, setInput] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-resize textarea height
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 180)}px`;
    }
  }, [input]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleSubmit = () => {
    if (isStreaming) {
      onStop();
      return;
    }
    const trimmed = input.trim();
    if (!trimmed || disabled) return;
    onSendMessage(trimmed);
    setInput('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  };

  return (
    <div className="w-full px-2 sm:px-0">
      <div className="flex items-end gap-2 rounded-xl border border-slate-700/70 bg-[#111726] p-2 focus-within:border-slate-500 transition-colors">
        <textarea
          ref={textareaRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask Football Guru anything..."
          rows={1}
          disabled={disabled}
          className="flex-1 max-h-44 min-h-[40px] resize-none bg-transparent px-3 py-2 text-sm text-slate-100 placeholder-slate-500 focus:outline-none leading-relaxed"
        />

        <div className="flex-shrink-0 mb-1 mr-1">
          {isStreaming ? (
            <button
              type="button"
              onClick={onStop}
              className="flex items-center justify-center w-8 h-8 rounded-lg bg-rose-600 hover:bg-rose-500 text-white transition-colors"
              title="Stop generation"
            >
              <Square className="w-3.5 h-3.5 fill-white" />
            </button>
          ) : (
            <button
              type="button"
              onClick={handleSubmit}
              disabled={!input.trim() || disabled}
              className={`flex items-center justify-center w-8 h-8 rounded-lg transition-colors ${
                input.trim() && !disabled
                  ? 'bg-emerald-500 hover:bg-emerald-400 text-slate-950 cursor-pointer'
                  : 'bg-slate-800 text-slate-600 cursor-not-allowed'
              }`}
              title="Send message"
            >
              <ArrowUp className="w-4 h-4 stroke-[2.5]" />
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
