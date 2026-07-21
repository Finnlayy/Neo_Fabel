import {apiRequest} from "./client";

export type PaperLoopStatus = {
  running: boolean;
  mode: string;
  last_error?: string | null;
  engine?: Record<string, unknown> | null;
};

export type PositionSizingMode = "half_kelly" | "full_kelly" | "ai_chronos" | "manual";
export type AmountUnit = "eur" | "usd" | "pct";

export type CapAmount = {
  value: number;
  unit: AmountUnit;
};

export type LiveSessionStatus = {
  session_name?: string;
  started_at?: string;
  ended_at?: string | null;
  max_margin_eur?: number;
  starting_capital_eur?: number;
  max_concurrent_trades?: number;
  symbol_allowlist?: string[];
  position_sizing?: {
    mode?: PositionSizingMode | string;
    manual_notional_eur?: number | null;
  };
  risk_policy?: Record<string, unknown>;
  uptime_seconds?: number;
  time_in_trades_seconds?: number;
  peak_open_trades?: number;
  status?: string;
} | null;

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
  session?: LiveSessionStatus;
  sizing_modes?: PositionSizingMode[];
  pending_approvals?: Record<string, unknown>[];
};

export type LoopsStatus = {
  paper: PaperLoopStatus;
  live: LiveLoopStatus;
};

export type LiveStartConfig = {
  max_margin_eur?: number;
  max_session_size?: CapAmount | number;
  max_concurrent_trades: number;
  starting_capital_eur?: number;
  daily_loss_limit?: CapAmount | number;
  min_confidence_pct?: number;
  allow_pre_post_market?: boolean;
  human_verification?: boolean;
  symbols?: string[];
  position_sizing_mode?: PositionSizingMode;
  manual_notional_eur?: number;
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

export async function startLiveLoop(config: LiveStartConfig): Promise<Record<string, unknown>> {
  const body: Record<string, unknown> = {
    max_concurrent_trades: config.max_concurrent_trades,
    position_sizing_mode: config.position_sizing_mode ?? "half_kelly",
    min_confidence_pct: config.min_confidence_pct ?? 0,
    allow_pre_post_market: config.allow_pre_post_market ?? true,
    human_verification: config.human_verification ?? false,
  };
  if (config.max_session_size != null) {
    body.max_session_size = config.max_session_size;
  } else if (config.max_margin_eur != null) {
    body.max_margin_eur = config.max_margin_eur;
    body.max_session_size = {value: config.max_margin_eur, unit: "eur"};
  }
  if (config.starting_capital_eur != null) {
    body.starting_capital_eur = config.starting_capital_eur;
  }
  if (config.daily_loss_limit != null) {
    body.daily_loss_limit = config.daily_loss_limit;
  }
  if (config.symbols && config.symbols.length > 0) {
    body.symbols = config.symbols;
  }
  if (config.manual_notional_eur != null) {
    body.manual_notional_eur = config.manual_notional_eur;
  }
  return apiRequest("/api/v1/loops/live/start", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function stopLiveLoop(): Promise<Record<string, unknown>> {
  return apiRequest("/api/v1/loops/live/stop", {method: "POST"});
}

export async function killTradingLoops(): Promise<Record<string, unknown>> {
  return apiRequest("/api/v1/loops/kill", {method: "POST"});
}

/** Parse "XRPUSD, METAUSD, ADAUSD" or whitespace-separated symbols. */
export function parseLiveSymbols(raw: string): string[] {
  return raw
    .split(/[\s,;]+/)
    .map((s) => s.trim().toUpperCase().replace(/[^A-Z0-9]/g, ""))
    .filter(Boolean)
    .filter((s, i, arr) => arr.indexOf(s) === i);
}
