export interface ToolCall {
  runId: string;
  tool: string;
  input: Record<string, any>;
  output?: string;
  status: 'running' | 'completed' | 'error';
  startTime: number;
  endTime?: number;
}

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  thought?: string;
  toolCalls?: ToolCall[];
  isStreaming?: boolean;
  timestamp: number;
}

export interface QuotaStatus {
  requests_made_today: number;
  requests_remaining: number;
  max_daily_quota: number;
  safety_threshold: number;
  can_make_request: boolean;
  rate_limit_per_minute: number;
  error?: string;
}

export interface ServerStatus {
  status: 'ready' | 'mcp_disconnected' | 'connecting' | 'error';
  mcp_url: string;
  tools_count: number;
  error?: string | null;
}
