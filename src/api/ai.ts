import {apiRequest} from "./client";
import type {GenerativePlan, Trade} from "../types";

export type AiHealth = {
  configured: boolean;
  provider: "gemini" | "none" | string;
  deterministic_fallback?: boolean;
  chat_enabled?: boolean;
};

export type ChatMessage = {role: "user" | "assistant" | "system"; content: string};

export type ChatResponse = {
  success: boolean;
  reply?: string;
  modelUsed?: string;
  routeLabel?: string;
  citations?: {title: string; uri: string}[];
  error?: string;
};

export async function fetchAiHealth(): Promise<AiHealth> {
  return apiRequest<AiHealth>("/api/ai/health");
}

export async function postChat(body: {
  messages: ChatMessage[];
  modelSelection: "auto" | "pro-preview" | "flash" | "flash-lite";
  enableSearch: boolean;
}): Promise<ChatResponse> {
  return apiRequest<ChatResponse>("/api/chat", {method: "POST", body: JSON.stringify(body)});
}

export async function postOrchestrate(prompt: string): Promise<GenerativePlan> {
  return apiRequest<GenerativePlan>("/api/gemini/orchestrate", {
    method: "POST",
    body: JSON.stringify({prompt}),
  });
}

export async function postAnalyzeTrades(trades: Trade[]): Promise<{analysis?: string; error?: string}> {
  return apiRequest<{analysis?: string; error?: string}>("/api/gemini/analyze-trades", {
    method: "POST",
    body: JSON.stringify({trades}),
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

export async function postTvapiAnalyzeChart(body: {
  image: string;
  mimeType: string;
  promptMode: "pattern" | "backtest";
}): Promise<{success: boolean; analysis?: string; error?: string}> {
  return apiRequest("/api/tvapi/analyze-chart", {method: "POST", body: JSON.stringify(body)});
}
