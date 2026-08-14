import {apiRequest} from "./client";

export const SPOT_ORDER_TYPES = [
  "market",
  "limit",
  "stop-loss",
  "stop-loss-limit",
  "take-profit",
  "take-profit-limit",
  "trailing-stop",
  "trailing-stop-limit",
] as const;

export type SpotOrderType = (typeof SPOT_ORDER_TYPES)[number];

export type PlaceOrderBody = {
  mode: "paper" | "live";
  market_type?: "spot" | "futures";
  pair: string;
  side: "buy" | "sell";
  volume: string;
  order_type?: SpotOrderType | string;
  price?: string;
  price2?: string;
  time_in_force?: "GTC" | "IOC" | "GTD" | "FOK";
  leverage?: number;
  reduce_only?: boolean;
  validate_only?: boolean;
  idempotency_key: string;
};

export type PlaceOrderResponse = {
  idempotency_key: string;
  mode: "paper" | "live";
  status: string;
  result: Record<string, unknown>;
  request_id: string;
};

export async function placeOrder(body: PlaceOrderBody): Promise<PlaceOrderResponse> {
  return apiRequest<PlaceOrderResponse>("/api/v1/orders", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function cancelOrder(body: {
  mode?: "paper" | "live";
  market_type?: "spot" | "futures";
  order_id: string;
}): Promise<Record<string, unknown>> {
  return apiRequest("/api/v1/orders/cancel", {
    method: "POST",
    body: JSON.stringify({mode: "live", market_type: "spot", ...body}),
  });
}

export async function cancelAllOrders(body: {
  mode?: "paper" | "live";
  market_type?: "spot" | "futures";
  symbol?: string;
  confirm: boolean;
}): Promise<Record<string, unknown>> {
  return apiRequest("/api/v1/orders/cancel-all", {
    method: "POST",
    body: JSON.stringify({mode: "live", market_type: "spot", ...body}),
  });
}

export async function amendOrder(body: {
  mode?: "paper" | "live";
  market_type?: "spot" | "futures";
  order_id: string;
  price?: string;
  volume?: string;
  pair?: string;
  side?: "buy" | "sell";
  order_type?: string;
  replace_on_amend_fail?: boolean;
}): Promise<Record<string, unknown>> {
  return apiRequest("/api/v1/orders/amend", {
    method: "POST",
    body: JSON.stringify({mode: "live", market_type: "spot", replace_on_amend_fail: true, ...body}),
  });
}

export async function fetchOrderTypes(): Promise<{
  spot: string[];
  futures: string[];
  paper: string[];
  time_in_force: string[];
}> {
  return apiRequest("/api/v1/orders/types");
}
