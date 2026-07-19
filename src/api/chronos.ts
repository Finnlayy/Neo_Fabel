import { apiRequest } from "./client";

export type ChronosVocab = {
  coarse: number;
  fine: number;
  full_bits: number;
};

export type ChronosStatus = {
  agent: string;
  paper_only: boolean;
  live_trading: boolean;
  phase: number;
  encoder: string;
  latent_dim: number;
  vocab: ChronosVocab;
  features: string[];
  normalization?: {
    type: string;
    ddof: number;
    clip: number;
    eps: number;
  };
  matplotlib_available?: boolean;
  endpoints?: Record<string, string>;
  note?: string;
};

export type ChronosWindowBody = {
  bars: number[][];
  eps?: number;
  clip_val?: number;
};

export type ChronosNormalizeResponse = {
  paper_only: boolean;
  lookback: number;
  feature_order: string[];
  mean: number[];
  std: number[];
  x_norm: number[][];
};

export type ChronosTokenizeResponse = ChronosNormalizeResponse & {
  encoder: string;
  s1_ids: number[];
  s2_ids: number[];
  vocab: ChronosVocab;
  entropy_mean: number;
  live_trading: boolean;
};

export type ChronosBsqEncodeResponse = {
  s1_id: number;
  s2_id: number;
  bits: number[];
  entropy_loss: number;
  paper_only: boolean;
};

export type ChronosBsqDecodeResponse = {
  z: number[];
  scale: number;
  paper_only: boolean;
};

export type ChronosChartsResponse = {
  charts: {
    ohlc?: string;
    zscore?: string;
    tokens?: string;
    token_hist?: string;
  };
  lookback: number;
  paper_only: boolean;
  renderer: string;
  entropy_mean?: number;
  encoder?: string;
};

export type ChronosOhlcvaRow = {
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  amount: number;
};

export type ChronosPredictResponse = {
  paper_only: boolean;
  live_trading: boolean;
  encoder: string;
  lookback: number;
  pred_len: number;
  sample_count: number;
  T: number;
  top_p: number;
  columns: string[];
  pred: ChronosOhlcvaRow[];
  history: ChronosOhlcvaRow[];
  charts?: {
    prediction?: string;
    prediction_wo_vol?: string;
    monte_carlo?: string;
  };
  chart_error?: string;
};

export async function fetchChronosStatus(): Promise<ChronosStatus> {
  return apiRequest<ChronosStatus>("/api/v1/chronos/status");
}

export async function normalizeChronos(body: ChronosWindowBody): Promise<ChronosNormalizeResponse> {
  return apiRequest<ChronosNormalizeResponse>("/api/v1/chronos/normalize", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function tokenizeChronos(body: ChronosWindowBody): Promise<ChronosTokenizeResponse> {
  return apiRequest<ChronosTokenizeResponse>("/api/v1/chronos/tokenize", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function fetchChronosCharts(
  body: ChronosWindowBody & { include_tokens?: boolean },
): Promise<ChronosChartsResponse> {
  return apiRequest<ChronosChartsResponse>("/api/v1/chronos/charts", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function predictChronos(body: {
  bars: number[][];
  eps?: number;
  clip_val?: number;
  pred_len?: number;
  T?: number;
  top_p?: number;
  sample_count?: number;
  include_volume?: boolean;
  monte_carlo?: boolean;
  mc_samples?: number;
}): Promise<ChronosPredictResponse> {
  return apiRequest<ChronosPredictResponse>("/api/v1/chronos/predict", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function bsqEncode(z: number[]): Promise<ChronosBsqEncodeResponse> {
  return apiRequest<ChronosBsqEncodeResponse>("/api/v1/chronos/bsq/encode", {
    method: "POST",
    body: JSON.stringify({ z }),
  });
}

export async function bsqDecode(s1_id: number, s2_id: number): Promise<ChronosBsqDecodeResponse> {
  return apiRequest<ChronosBsqDecodeResponse>("/api/v1/chronos/bsq/decode", {
    method: "POST",
    body: JSON.stringify({ s1_id, s2_id }),
  });
}
