import {apiRequest} from "./client";
import type {ApiJsonBody, ApiJsonOk, Schemas} from "./paths";
import type {Trade} from "../types";

/** OpenAPI-backed order request (defaults applied in submitPaperOrder). */
export type PaperOrderRequest = ApiJsonBody<"/api/v1/paper/orders", "post">;
export type PaperOrderResponse = Schemas["PaperOrderResponse"];

export type MarketType = PaperOrderRequest["market_type"];

/** Caller may omit fields that have FastAPI defaults. */
export type SubmitPaperOrderBody = Omit<
  PaperOrderRequest,
  "order_type" | "market_type" | "leverage" | "price"
> &
  Partial<Pick<PaperOrderRequest, "order_type" | "market_type" | "leverage" | "price">>;

/**
 * Client refinement of OpenAPI `/paper/status` (schema is opaque dict until
 * the backend adds a response_model).
 */
export type PaperBookSummary = {
  usd_balance?: string;
  starting_balance_usd?: string;
  margin_balance_usd?: string;
  starting_margin_usd?: string;
  open_positions?: number;
};

export type PaperStatusData = {
  mode?: string;
  source?: string;
  version?: number;
  spot?: PaperBookSummary;
  futures?: PaperBookSummary;
  usd_balance?: string;
  orders?: unknown[];
  fills?: unknown[];
};

export type PaperStatusResponse = ApiJsonOk<"/api/v1/paper/status", "get"> & {
  mode: string;
  data: PaperStatusData;
  request_id?: string;
};

export type PaperPosition = {
  pair: string;
  market_type?: MarketType;
  side?: string;
  leverage?: number;
  volume: string;
  avg_entry: string;
  mark_price: string;
  market_value_usd: string;
  cost_basis_usd: string;
  unrealized_pnl_usd: string;
  initial_margin_usd?: string;
};

export type PaperFill = {
  txid: string;
  pair: string;
  market_type?: MarketType;
  side: string;
  volume: string;
  price: string;
  fee: string;
  fee_rate?: string;
  leverage?: number;
  realized_pnl: string;
  time: string;
  ordertype?: string;
};

export type PaperSymbolStats = {
  pair: string;
  fills: number;
  buy_volume: string;
  sell_volume: string;
  realized_pnl_usd: string;
  fees_usd: string;
};

export type PaperEquityPoint = {
  time: string | null;
  equity_usd: string;
  cash_usd?: string;
  realized_pnl_usd?: string;
  event?: string;
};

export type PaperBookPerformance = {
  source: string;
  fee_model: string;
  starting_balance_usd?: string;
  usd_balance?: string;
  starting_margin_usd?: string;
  margin_balance_usd?: string;
  equity_usd: string;
  position_value_usd: string;
  realized_pnl_usd: string;
  unrealized_pnl_usd: string;
  total_pnl_usd: string;
  fees_paid_usd: string;
  win_rate: number | null;
  wins: number;
  losses: number;
  closed_rounds: number;
  fill_count: number;
  max_drawdown_pct: string;
  positions: PaperPosition[];
  by_symbol: PaperSymbolStats[];
  equity_curve: PaperEquityPoint[];
  fills: PaperFill[];
};

/**
 * Client refinement of OpenAPI `/paper/performance` (opaque dict in schema).
 */
export type PaperPerformanceResponse = ApiJsonOk<"/api/v1/paper/performance", "get"> & {
  mode: string;
  execution: string;
  request_id?: string;
  router_source?: string;
  ledger_version?: number;
  source: string;
  fee_model: string;
  starting_balance_usd: string;
  usd_balance: string;
  starting_margin_usd?: string;
  margin_balance_usd?: string;
  equity_usd: string;
  combined_equity_usd?: string;
  position_value_usd: string;
  realized_pnl_usd: string;
  unrealized_pnl_usd: string;
  total_pnl_usd: string;
  fees_paid_usd: string;
  win_rate: number | null;
  wins: number;
  losses: number;
  closed_rounds: number;
  fill_count: number;
  max_drawdown_pct: string;
  positions: PaperPosition[];
  by_symbol: PaperSymbolStats[];
  equity_curve: PaperEquityPoint[];
  fills: PaperFill[];
  spot?: PaperBookPerformance | null;
  futures?: PaperBookPerformance | null;
};

export async function submitPaperOrder(body: SubmitPaperOrderBody): Promise<PaperOrderResponse> {
  const payload: PaperOrderRequest = {
    order_type: "market",
    market_type: "spot",
    leverage: 1,
    ...body,
    volume: body.volume,
  };
  return apiRequest<PaperOrderResponse>("/api/v1/paper/orders", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function fetchPaperStatus(): Promise<PaperStatusResponse> {
  return apiRequest<PaperStatusResponse>("/api/v1/paper/status");
}

export async function fetchPaperPerformance(): Promise<PaperPerformanceResponse> {
  return apiRequest<PaperPerformanceResponse>("/api/v1/paper/performance");
}

export function performanceFillsToCsv(fills: PaperFill[]): string {
  const header = "time,market_type,pair,side,volume,price,fee,realized_pnl,ordertype";
  const rows = fills.map((f) =>
    [
      f.time,
      f.market_type ?? "spot",
      f.pair,
      f.side,
      f.volume,
      f.price,
      f.fee,
      f.realized_pnl,
      f.ordertype ?? "",
    ]
      .map((v) => `"${String(v).replace(/"/g, '""')}"`)
      .join(","),
  );
  return [header, ...rows].join("\n");
}

/** Best-effort map of opaque Kraken paper status JSON into Trade rows. */
export function mapPaperStatusToTrades(data: unknown): Trade[] {
  if (!data || typeof data !== "object") return [];
  const root = data as Record<string, unknown>;
  const candidates: unknown[] = [];
  for (const key of ["orders", "open_orders", "closed_orders", "fills", "trades", "history"]) {
    const value = root[key];
    if (Array.isArray(value)) candidates.push(...value);
  }
  const spot = root.spot as Record<string, unknown> | undefined;
  const futures = root.futures as Record<string, unknown> | undefined;
  if (spot && Array.isArray(spot.fills)) candidates.push(...spot.fills);
  if (futures && Array.isArray(futures.fills)) candidates.push(...futures.fills);
  if (Array.isArray(root.result)) candidates.push(...root.result);
  if (root.result && typeof root.result === "object") {
    const nested = root.result as Record<string, unknown>;
    for (const value of Object.values(nested)) {
      if (Array.isArray(value)) candidates.push(...value);
      else if (value && typeof value === "object") candidates.push(value);
    }
  }

  const trades: Trade[] = [];
  const seenIds = new Set<string>();

  candidates.forEach((item, index) => {
    if (!item || typeof item !== "object") return;
    const row = item as Record<string, unknown>;
    const id = String(row.txid ?? row.id ?? row.order_id ?? `PAPER-${index}`);
    if (seenIds.has(id)) return;
    seenIds.add(id);

    const pair = String(row.pair ?? row.symbol ?? row.descr ?? "UNKNOWN");
    const asset = pair.replace(/USD$|\/USD$/i, "").replace(/^PF_/, "").replace(/XBT/, "BTC").replace(/[^A-Z0-9]/gi, "") || "UNK";
    const sideRaw = String(row.side ?? row.type ?? row.ordertype ?? "buy").toLowerCase();
    const type: "BUY" | "SELL" = sideRaw.includes("sell") ? "SELL" : "BUY";
    const price = Number(row.price ?? row.avg_price ?? row.limit_price ?? 0) || 0;
    const amount = Number(row.vol ?? row.volume ?? row.amount ?? row.qty ?? 0) || 0;
    const pnl = Number(row.pnl ?? row.realized_pnl ?? row.net ?? 0) || 0;
    const statusRaw = String(row.status ?? row.state ?? "PENDING").toUpperCase();
    const status: Trade["status"] =
      statusRaw.includes("CLOSE") || statusRaw.includes("FILL") || statusRaw === "CLOSED"
        ? "COMPLETED"
        : statusRaw.includes("CANCEL") || statusRaw.includes("HALT")
          ? "HALTED"
          : "PENDING";
    const time = String(row.time ?? row.opentm ?? row.closetm ?? new Date().toLocaleTimeString());
    trades.push({id, time, asset, type, price, amount, positionCost: price * amount, pnl, status});
  });
  return trades;
}
