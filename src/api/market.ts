import {apiRequest} from "./client";
import type {TickerData} from "../types";

export type MarketBatchItem = {
  symbol: string;
  asset_class: "crypto" | "forex" | "sp500";
  status: "ok" | "error";
  source: string;
  data?: Record<string, unknown> | null;
  error?: {code?: string; message?: string} | null;
};

export type MarketBatchResponse = {
  requested: number;
  succeeded: number;
  failed: number;
  as_of: string;
  request_id: string;
  items: MarketBatchItem[];
};

const SYMBOL_TO_PAIR: Record<string, string> = {
  BTC: "BTCUSD",
  ETH: "ETHUSD",
  SOL: "SOLUSD",
  MATIC: "MATICUSD",
  AVAX: "AVAXUSD",
  DOT: "DOTUSD",
  XRP: "XRPUSD",
  ADA: "ADAUSD",
};

const PAIR_TO_SYMBOL: Record<string, string> = Object.fromEntries(
  Object.entries(SYMBOL_TO_PAIR).map(([symbol, pair]) => [pair, symbol]),
);

const NAMES: Record<string, string> = {
  BTC: "Bitcoin",
  ETH: "Ethereum",
  SOL: "Solana",
  MATIC: "Polygon",
  AVAX: "Avalanche",
  DOT: "Polkadot",
  XRP: "Ripple",
  ADA: "Cardano",
};

function asNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim()) {
    const n = Number(value);
    return Number.isFinite(n) ? n : null;
  }
  if (Array.isArray(value) && value.length > 0) return asNumber(value[0]);
  return null;
}

/** Extract last/close price from Kraken CLI or REST-shaped ticker payloads. */
export function extractLastPrice(data: Record<string, unknown> | null | undefined): number | null {
  if (!data) return null;
  const directKeys = ["last", "price", "close", "c", "a", "b"];
  for (const key of directKeys) {
    const n = asNumber(data[key]);
    if (n !== null && n > 0) return n;
  }
  // Classic Kraken result map: { XXBTZUSD: { c: ["123", "..."] } }
  for (const value of Object.values(data)) {
    if (value && typeof value === "object" && !Array.isArray(value)) {
      const nested = extractLastPrice(value as Record<string, unknown>);
      if (nested !== null) return nested;
    }
  }
  return null;
}

export function extractChangePct(data: Record<string, unknown> | null | undefined, last: number): number {
  if (!data) return 0;
  const explicit = asNumber(data.change_pct) ?? asNumber(data.changePercent) ?? asNumber(data.percent_change);
  if (explicit !== null) return explicit;
  const open = asNumber(data.open) ?? asNumber(data.o) ?? asNumber(data.yesterday);
  if (open !== null && open > 0) return ((last - open) / open) * 100;
  return 0;
}

function itemsToTickers(body: MarketBatchResponse, symbolMode: "crypto" | "equity"): TickerData[] {
  const tickers: TickerData[] = [];
  for (const item of body.items) {
    if (item.status !== "ok" || !item.data) continue;
    const last = extractLastPrice(item.data);
    if (last === null) continue;
    const symbol =
      symbolMode === "crypto"
        ? PAIR_TO_SYMBOL[item.symbol] ?? item.symbol.replace(/USD$/, "")
        : item.symbol.toUpperCase();
    const change = extractChangePct(item.data, last);
    tickers.push({
      symbol,
      name: NAMES[symbol] ?? (typeof item.data.symbol === "string" ? String(item.data.symbol) : symbol),
      price: last,
      change,
      history: [last],
    });
  }
  return tickers;
}

export async function fetchCryptoTickers(symbols: string[] = Object.keys(SYMBOL_TO_PAIR)): Promise<{
  tickers: TickerData[];
  asOf: string;
}> {
  const pairs = symbols.map((s) => SYMBOL_TO_PAIR[s] ?? `${s}USD`).join(",");
  const body = await apiRequest<MarketBatchResponse>(
    `/api/v1/market/batch?asset_class=crypto&symbols=${encodeURIComponent(pairs)}`,
  );
  return {tickers: itemsToTickers(body, "crypto"), asOf: body.as_of};
}

/** Alpha Vantage GLOBAL_QUOTE batch for equities (use ~hourly to respect rate limits). */
export async function fetchEquityTickers(symbols: string[] = ["NIO"]): Promise<{
  tickers: TickerData[];
  asOf: string;
}> {
  if (symbols.length === 0) return {tickers: [], asOf: new Date().toISOString()};
  const body = await apiRequest<MarketBatchResponse>(
    `/api/v1/market/batch?asset_class=sp500&symbols=${encodeURIComponent(symbols.join(","))}`,
  );
  return {tickers: itemsToTickers(body, "equity"), asOf: body.as_of};
}

export function mergeTickerHistory(prev: TickerData[], next: TickerData[]): TickerData[] {
  const prevMap = new Map(prev.map((t) => [t.symbol, t]));
  return next.map((t) => {
    const old = prevMap.get(t.symbol);
    const history = [...(old?.history ?? []), t.price].slice(-24);
    return {...t, history};
  });
}

/** Merge/upsert by symbol so crypto + equity batches can share one ticker list. */
export function upsertTickerHistory(prev: TickerData[], next: TickerData[]): TickerData[] {
  const map = new Map(prev.map((t) => [t.symbol, t]));
  for (const t of next) {
    const old = map.get(t.symbol);
    const history = [...(old?.history ?? []), t.price].slice(-24);
    map.set(t.symbol, {...t, history});
  }
  return Array.from(map.values());
}
