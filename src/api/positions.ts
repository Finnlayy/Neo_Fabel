import {apiRequest} from "./client";
import type {PaperPosition} from "./paper";

export type LivePosition = {
  mode: "live";
  asset: string;
  pair: string;
  volume: string;
  avg_entry: string | null;
  mark_price: string | null;
  market_value_usd: string | null;
  cost_basis_usd: string | null;
  unrealized_pnl_usd: string | null;
  source: string;
};

export type OpenOrderRow = {
  mode: "live";
  order_id: string;
  pair: string;
  side: string;
  volume: string;
  price: string;
  status: string;
  source: string;
};

export type PositionsSnapshot = {
  request_id?: string;
  execution: string;
  autonomy_level: number;
  paper: Array<PaperPosition & {mode?: "paper"}>;
  live: LivePosition[];
  open_orders: OpenOrderRow[];
  live_trading_enabled: boolean;
  trade_commands_enabled: boolean;
  live_close_available: boolean;
  errors: Array<{source: string; category: string; message: string}>;
  total_open: number;
};

export type ClosePositionResponse = {
  idempotency_key: string;
  mode?: string;
  status: string;
  result: Record<string, unknown>;
  request_id: string;
};

export async function fetchPositions(): Promise<PositionsSnapshot> {
  return apiRequest<PositionsSnapshot>("/api/v1/positions");
}

export async function closePosition(body: {
  pair: string;
  mode: "paper" | "live";
  market_type?: "spot" | "futures";
  volume?: string;
  order_type?: "market" | "limit";
  price?: string;
  idempotency_key: string;
}): Promise<ClosePositionResponse> {
  return apiRequest<ClosePositionResponse>("/api/v1/positions/close", {
    method: "POST",
    body: JSON.stringify(body),
  });
}
