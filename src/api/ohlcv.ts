import {apiRequest} from "./client";

export type OhlcvBar = {
  timestamp: string;
  open: string;
  high: string;
  low: string;
  close: string;
  volume: string;
};

export type OhlcvItem = {
  symbol: string;
  asset_class: string;
  interval: string;
  status: "ok" | "error";
  source: string;
  data?: {bars?: OhlcvBar[]; requested_interval?: string} | null;
  error?: {code?: string; message?: string} | null;
};

export type OhlcvBatchResponse = {
  requested: number;
  succeeded: number;
  failed: number;
  as_of: string;
  items: OhlcvItem[];
};

export type CandlePoint = {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
};

const TF_TO_INTERVAL: Record<string, string> = {
  "1m": "1min",
  "5m": "5min",
  "15m": "15min",
  "30m": "30min",
  "1h": "60min",
  "4h": "4h",
};

export async function fetchOhlcvCandles(options: {
  symbol: string;
  timeframe?: string;
  assetClass?: "crypto" | "forex" | "sp500";
}): Promise<{candles: CandlePoint[]; asOf: string; source: string}> {
  const interval = TF_TO_INTERVAL[options.timeframe ?? "5m"] ?? "5min";
  const assetClass = options.assetClass ?? "forex";
  // Alpha Vantage OHLCV path is forex/sp500 oriented; crypto callers may get errors.
  const symbol = options.symbol.replace("/", "").toUpperCase();
  const body = await apiRequest<OhlcvBatchResponse>(
    `/api/v1/market/ohlcv?asset_class=${encodeURIComponent(assetClass)}&symbols=${encodeURIComponent(symbol)}&intervals=${encodeURIComponent(interval)}`,
  );
  const item = body.items.find((row) => row.status === "ok" && row.data?.bars?.length) ?? body.items[0];
  if (!item || item.status !== "ok" || !item.data?.bars?.length) {
    return {candles: [], asOf: body.as_of, source: item?.source ?? "none"};
  }
  const candles = item.data.bars.map((bar) => ({
    time: bar.timestamp,
    open: Number(bar.open) || 0,
    high: Number(bar.high) || 0,
    low: Number(bar.low) || 0,
    close: Number(bar.close) || 0,
    volume: Number(bar.volume) || 0,
  }));
  return {candles, asOf: body.as_of, source: item.source};
}
