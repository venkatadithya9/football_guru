import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Copy, Check } from 'lucide-react';
import { Message } from '../types/chat';
import { ThinkingAccordion } from './ThinkingAccordion';
import { ToolCallCard } from './ToolCallCard';

interface MessageItemProps {
  message: Message;
}

export const MessageItem: React.FC<MessageItemProps> = ({ message }) => {
  const isUser = message.role === 'user';
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  if (isUser) {
    return (
      <div className="w-full flex justify-end my-3">
        <div className="max-w-[85%] sm:max-w-[75%] px-4 py-2.5 rounded-2xl bg-slate-800 text-slate-100 text-sm leading-relaxed whitespace-pre-wrap">
          {message.content}
        </div>
      </div>
    );
  }

  return (
    <div className="w-full flex justify-start my-3">
      <div className="w-full rounded-2xl bg-[#0f1624] border border-slate-800/80 p-4 text-slate-100 text-sm leading-relaxed shadow-sm">
        {/* Thinking Block */}
        {message.thought && (
          <ThinkingAccordion
            thought={message.thought}
            isStreaming={Boolean(message.isStreaming && !message.content)}
            hasOutput={Boolean(message.content)}
          />
        )}

        {/* Tool Invocations */}
        {message.toolCalls && message.toolCalls.length > 0 && (
          <div className="space-y-1 my-2">
            {message.toolCalls.map((tc) => (
              <ToolCallCard key={tc.runId} toolCall={tc} />
            ))}
          </div>
        )}

        {/* Assistant Markdown Content */}
        {message.content && (
          <div className="football-prose text-slate-200 mt-2 break-words">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                table: ({ node, ...props }) => (
                  <div className="w-full my-3 overflow-x-auto rounded-lg border border-slate-800 bg-[#0a0f1a]">
                    <table className="w-full text-xs text-left border-collapse" {...props} />
                  </div>
                ),
                thead: ({ node, ...props }) => (
                  <thead className="bg-slate-800/80 text-slate-300 uppercase text-[10px] tracking-wider font-semibold border-b border-slate-700" {...props} />
                ),
                th: ({ node, ...props }) => (
                  <th className="px-3 py-2 font-bold" {...props} />
                ),
                td: ({ node, ...props }) => (
                  <td className="px-3 py-2 border-b border-slate-800/60 font-mono text-slate-300" {...props} />
                ),
                tr: ({ node, ...props }) => (
                  <tr className="hover:bg-slate-800/40 transition-colors" {...props} />
                ),
              }}
            >
              {message.content}
            </ReactMarkdown>

            {message.isStreaming && (
              <span className="inline-block w-1.5 h-4 ml-1 bg-emerald-400 animate-pulse align-middle" />
            )}
          </div>
        )}

        {/* Action bar */}
        {!message.isStreaming && message.content && (
          <div className="flex items-center justify-end mt-2 pt-1">
            <button
              onClick={handleCopy}
              className="flex items-center gap-1 text-[11px] text-slate-500 hover:text-slate-300 px-2 py-0.5 rounded hover:bg-slate-800/50 transition-colors"
              title="Copy message"
            >
              {copied ? (
                <>
                  <Check className="w-3 h-3 text-emerald-400" />
                  <span className="text-emerald-400">Copied</span>
                </>
              ) : (
                <>
                  <Copy className="w-3 h-3" />
                  <span>Copy</span>
                </>
              )}
            </button>
          </div>
        )}
      </div>
    </div>
  );
};
