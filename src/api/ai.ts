import {apiRequest} from "./client";
import {tradesForAnalyzeWire} from "./chatWire";
import type {GenerativePlan, Trade} from "../types";

export type AiHealth = {
  configured: boolean;
  provider: "gemini" | "openrouter" | "groq" | "cerebras" | "aiprimetech" | "none" | string;
  providers?: string[];
  provider_order?: string[];
  active_chain?: string[];
  deterministic_fallback?: boolean;
  chat_enabled?: boolean;
  rotate?: boolean;
};

export type ChatMessage = {role: "user" | "assistant" | "system"; content: string};

export type ChatContextMeta = {
  input_messages?: number;
  input_chars?: number;
  sent_messages?: number;
  sent_chars?: number;
  trimmed?: boolean;
};

export type ChatResponse = {
  success: boolean;
  reply?: string;
  modelUsed?: string;
  routeLabel?: string;
  provider?: string;
  citations?: {title: string; uri: string}[];
  context?: ChatContextMeta;
  error?: string;
};

export async function fetchAiHealth(): Promise<AiHealth> {
  return apiRequest<AiHealth>("/api/ai/health");
}

export async function postChat(body: {
  messages: ChatMessage[];
  modelSelection: "auto" | "pro-preview" | "flash" | "flash-lite";
  enableSearch: boolean;
  mode?: "assistant" | "orchestrator";
  agentStatusPackets?: any[];
}): Promise<ChatResponse> {
  return apiRequest<ChatResponse>("/api/chat", {method: "POST", body: JSON.stringify(body)});
}

export async function postOrchestrate(
  prompt: string,
  agentStatusPackets: any[] = [],
): Promise<GenerativePlan> {
  return apiRequest<GenerativePlan>("/api/gemini/orchestrate", {
    method: "POST",
    body: JSON.stringify({prompt, agentStatusPackets}),
  });
}

export async function postAnalyzeTrades(trades: Trade[]): Promise<{analysis?: string; error?: string}> {
  return apiRequest<{analysis?: string; error?: string}>("/api/gemini/analyze-trades", {
    method: "POST",
    // Wire budget: last ~25 trades only (server also caps).
    body: JSON.stringify({trades: tradesForAnalyzeWire(trades)}),
  });
}

export type TvapiOptimizePayload = {
  strategy: string;
  symbol: string;
  timeframe: string;
  minTrades: number;
  primaryObjective: string;
  secondaryObjective: string;
  parameters: Record<string, unknown>;
  scriptId?: string;
  pineName?: string;
  pineSource?: string;
};

export type TvapiOptimizeResult = {
  success: boolean;
  winner?: Record<string, unknown> | null;
  bericht?: string;
  selfTest?: string;
  results?: Array<Record<string, unknown>>;
  error?: string;
  source?: string;
};

export async function postTvapiOptimize(payload: TvapiOptimizePayload): Promise<TvapiOptimizeResult> {
  return apiRequest<TvapiOptimizeResult>("/api/tvapi/optimize", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export type ChartStrategy = {
  id: string;
  name: string;
  kind: string;
  pane?: string;
  inputs?: Record<string, unknown>;
  origin?: string;
  hasSource?: boolean;
};

export async function fetchChartStrategies(symbol: string): Promise<{
  success: boolean;
  symbol?: string;
  strategies: ChartStrategy[];
  source?: string;
  note?: string;
  error?: string;
  tvremixConfigured?: boolean;
  tvremixCount?: number;
}> {
  return apiRequest("/api/tvapi/chart-strategies", {
    method: "POST",
    body: JSON.stringify({symbol, includeProbe: true}),
  });
}

export async function postTvapiAnalyzeChart(body: {
  image: string;
  mimeType: string;
  promptMode: "pattern" | "backtest";
}): Promise<{success: boolean; analysis?: string; error?: string}> {
  return apiRequest("/api/tvapi/analyze-chart", {method: "POST", body: JSON.stringify(body)});
}
