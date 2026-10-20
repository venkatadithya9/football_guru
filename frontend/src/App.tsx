import React, { useRef, useEffect } from 'react';
import { MessageItem } from './components/MessageItem';
import { InputBar } from './components/InputBar';
import { useChatStream } from './hooks/useChatStream';

export function App() {
  const {
    messages,
    isStreaming,
    sendMessage,
    stopGeneration,
  } = useChatStream();

  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll on new tokens or messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  return (
    <div className="flex flex-col h-screen w-screen bg-[#090d16] text-slate-100 overflow-hidden font-sans">
      {/* Messages Scroll Area */}
      <main className="flex-1 overflow-y-auto px-4 sm:px-6 py-6">
        <div className="max-w-3xl mx-auto min-h-full flex flex-col justify-end">
          {messages.length === 0 ? (
            <div className="my-auto text-center text-slate-500 text-sm py-12">
              <p>Type a message below to start chatting with Football Guru.</p>
            </div>
          ) : (
            <div className="space-y-4">
              {messages.map((msg) => (
                <MessageItem key={msg.id} message={msg} />
              ))}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>
      </main>

      {/* Chat Input Element */}
      <footer className="w-full bg-[#090d16] border-t border-slate-800/60 pb-4 pt-2">
        <div className="max-w-3xl mx-auto">
          <InputBar
            onSendMessage={sendMessage}
            onStop={stopGeneration}
            isStreaming={isStreaming}
          />
        </div>
      </footer>
    </div>
  );
}

export default App;
