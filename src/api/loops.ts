import {apiRequest} from "./client";

export type PaperLoopStatus = {
  running: boolean;
  mode: string;
  last_error?: string | null;
  engine?: Record<string, unknown> | null;
};

export type LiveLoopStatus = {
  running: boolean;
  blocked_reason?: string | null;
  can_start: boolean;
  deadman_armed: boolean;
  autonomy: number;
  live_enabled: boolean;
  algo_enabled?: boolean;
  supervised_manual?: boolean;
  last_error?: string | null;
};

export type LoopsStatus = {
  paper: PaperLoopStatus;
  live: LiveLoopStatus;
};

export async function fetchLoopsStatus(): Promise<LoopsStatus> {
  return apiRequest<LoopsStatus>("/api/v1/loops/status");
}

export async function startPaperLoop(): Promise<Record<string, unknown>> {
  return apiRequest("/api/v1/loops/paper/start", {method: "POST"});
}

export async function stopPaperLoop(): Promise<Record<string, unknown>> {
  return apiRequest("/api/v1/loops/paper/stop", {method: "POST"});
}

export async function startLiveLoop(): Promise<Record<string, unknown>> {
  return apiRequest("/api/v1/loops/live/start", {method: "POST"});
}

export async function stopLiveLoop(): Promise<Record<string, unknown>> {
  return apiRequest("/api/v1/loops/live/stop", {method: "POST"});
}

export async function killTradingLoops(): Promise<Record<string, unknown>> {
  return apiRequest("/api/v1/loops/kill", {method: "POST"});
}
