import { useState, useRef, useCallback } from 'react';
import { Message, ToolCall } from '../types/chat';

export function useChatStream() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [threadId, setThreadId] = useState<string>(() => {
    return localStorage.getItem('football_thread_id') || '';
  });

  const abortControllerRef = useRef<AbortController | null>(null);

  // Reset conversation
  const resetChat = useCallback(async () => {
    if (isStreaming && abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    try {
      const res = await fetch('/api/reset', { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        setThreadId(data.thread_id);
        localStorage.setItem('football_thread_id', data.thread_id);
      }
    } catch {
      const fallbackId = 'thread_' + Math.random().toString(36).substring(2, 9);
      setThreadId(fallbackId);
      localStorage.setItem('football_thread_id', fallbackId);
    }
    setMessages([]);
    setIsStreaming(false);
  }, [isStreaming]);

  // Stop Generation
  const stopGeneration = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setIsStreaming(false);
    setMessages((prev) =>
      prev.map((m) =>
        m.role === 'assistant' && m.isStreaming
          ? { ...m, isStreaming: false, content: m.content + '\n\n*(Generation stopped)*' }
          : m
      )
    );
  }, []);

  // Send message and stream SSE
  const sendMessage = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || isStreaming) return;

      const userMsgId = 'user_' + Date.now();
      const botMsgId = 'bot_' + Date.now();

      const userMessage: Message = {
        id: userMsgId,
        role: 'user',
        content: trimmed,
        timestamp: Date.now(),
      };

      const initialBotMessage: Message = {
        id: botMsgId,
        role: 'assistant',
        content: '',
        thought: '',
        toolCalls: [],
        isStreaming: true,
        timestamp: Date.now(),
      };

      setMessages((prev) => [...prev, userMessage, initialBotMessage]);
      setIsStreaming(true);

      // Local accumulators: single source of truth during the stream
      let accumulatedContent = '';
      let accumulatedThought = '';
      let accumulatedToolCalls: ToolCall[] = [];

      abortControllerRef.current = new AbortController();

      try {
        const response = await fetch('/api/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            message: trimmed,
            thread_id: threadId || undefined,
          }),
          signal: abortControllerRef.current.signal,
        });

        if (!response.ok) {
          throw new Error(`HTTP Error ${response.status}: ${response.statusText}`);
        }

        if (!response.body) {
          throw new Error('ReadableStream not supported by response');
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          buffer = buffer.replace(/\r\n/g, '\n');

          const parts = buffer.split('\n\n');
          buffer = parts.pop() || '';

          for (const part of parts) {
            const lines = part.split('\n');
            for (const rawLine of lines) {
              const line = rawLine.trim();
              if (!line.startsWith('data:')) continue;
              const jsonStr = line.replace(/^data:\s*/, '');
              if (!jsonStr) continue;

              try {
                const data = JSON.parse(jsonStr);

                if (data.type === 'start') {
                  if (data.thread_id && data.thread_id !== threadId) {
                    setThreadId(data.thread_id);
                    localStorage.setItem('football_thread_id', data.thread_id);
                  }
                } else if (data.type === 'thought') {
                  accumulatedThought += data.content;
                  setMessages((prev) =>
                    prev.map((m) =>
                      m.id === botMsgId
                        ? { ...m, thought: accumulatedThought }
                        : m
                    )
                  );
                } else if (data.type === 'token') {
                  accumulatedContent += data.content;
                  setMessages((prev) =>
                    prev.map((m) =>
                      m.id === botMsgId
                        ? { ...m, content: accumulatedContent }
                        : m
                    )
                  );
                } else if (data.type === 'tool_start') {
                  const newTool: ToolCall = {
                    runId: data.run_id || 'tool_' + Math.random().toString(36).substring(2, 9),
                    tool: data.tool,
                    input: data.input || {},
                    status: 'running',
                    startTime: Date.now(),
                  };
                  accumulatedToolCalls = [...accumulatedToolCalls, newTool];
                  setMessages((prev) =>
                    prev.map((m) =>
                      m.id === botMsgId
                        ? { ...m, toolCalls: [...accumulatedToolCalls] }
                        : m
                    )
                  );
                } else if (data.type === 'tool_end') {
                  accumulatedToolCalls = accumulatedToolCalls.map((tc) =>
                    tc.runId === data.run_id || tc.tool === data.tool
                      ? {
                          ...tc,
                          status: 'completed',
                          output: data.output,
                          endTime: Date.now(),
                        }
                      : tc
                  );
                  setMessages((prev) =>
                    prev.map((m) =>
                      m.id === botMsgId
                        ? { ...m, toolCalls: [...accumulatedToolCalls] }
                        : m
                    )
                  );
                } else if (data.type === 'error') {
                  accumulatedContent += `\n\n⚠️ **Error:** ${data.error}`;
                  setMessages((prev) =>
                    prev.map((m) =>
                      m.id === botMsgId
                        ? { ...m, content: accumulatedContent, isStreaming: false }
                        : m
                    )
                  );
                } else if (data.type === 'done') {
                  setMessages((prev) =>
                    prev.map((m) =>
                      m.id === botMsgId
                        ? { ...m, isStreaming: false }
                        : m
                    )
                  );
                }
              } catch (e) {
                console.error('Error parsing SSE event chunk:', e, jsonStr);
              }
            }
          }
        }
      } catch (err: any) {
        if (err.name === 'AbortError') {
          console.log('Stream aborted');
        } else {
          console.error('Stream failure:', err);
          setMessages((prev) =>
            prev.map((m) =>
              m.id === botMsgId
                ? {
                    ...m,
                    content: (m.content || '') + `\n\n❌ **Connection Error:** ${err.message || err}`,
                    isStreaming: false,
                  }
                : m
            )
          );
        }
      } finally {
        setIsStreaming(false);
        abortControllerRef.current = null;
      }
    },
    [threadId, isStreaming]
  );

  return {
    messages,
    isStreaming,
    threadId,
    sendMessage,
    resetChat,
    stopGeneration,
  };
}
