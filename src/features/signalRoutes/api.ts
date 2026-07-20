import { apiRequest } from "../../api/client";
import type {
  CredentialReveal,
  SignalAutomationStatus,
  SignalRoute,
  SignalSubmission,
} from "./types";

export function fetchSignalStatus(): Promise<SignalAutomationStatus> {
  return apiRequest<SignalAutomationStatus>("/api/v1/signal-automation/status");
}

export function fetchSignalRoutes(): Promise<SignalRoute[]> {
  return apiRequest<SignalRoute[]>("/api/v1/signal-routes");
}

export function createSignalRoute(body: {
  name: string;
  strategy_id: string;
  pair_allowlist?: string;
  max_volume?: string;
}): Promise<SignalRoute> {
  return apiRequest<SignalRoute>("/api/v1/signal-routes", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function patchSignalRoute(
  routeId: string,
  body: Record<string, unknown>
): Promise<SignalRoute> {
  return apiRequest<SignalRoute>(`/api/v1/signal-routes/${routeId}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export function rotateTradingViewCredential(routeId: string): Promise<CredentialReveal> {
  return apiRequest<CredentialReveal>(
    `/api/v1/signal-routes/${routeId}/credentials/tradingview/rotate`,
    { method: "POST" }
  );
}

export function rotateMcpCredential(routeId: string): Promise<CredentialReveal> {
  return apiRequest<CredentialReveal>(
    `/api/v1/signal-routes/${routeId}/credentials/mcp/rotate`,
    { method: "POST" }
  );
}

export function fetchSubmissions(params?: {
  route_id?: string;
  source?: string;
  status?: string;
}): Promise<SignalSubmission[]> {
  const qs = new URLSearchParams();
  if (params?.route_id) qs.set("route_id", params.route_id);
  if (params?.source) qs.set("source", params.source);
  if (params?.status) qs.set("status", params.status);
  const suffix = qs.toString() ? `?${qs}` : "";
  return apiRequest<SignalSubmission[]>(`/api/v1/signal-submissions${suffix}`);
}

export function fetchSubmission(id: string): Promise<SignalSubmission> {
  return apiRequest<SignalSubmission>(`/api/v1/signal-submissions/${id}`);
}

export interface FableEngineStatus {
  enabled: boolean;
  dry_run: boolean;
  started: boolean;
  poll_seconds: number;
  market_rpm: number;
  onnx_bias: string;
  strategy_count: number;
  ticks: number;
  last_tick_at: string | null;
  last_error: string | null;
  dry_run_count: number;
  candle_source: string;
  interval: string;
  note?: string;
}

export interface FableEngineDryRun {
  recorded_at: string;
  terminal: string;
  strategy_id: string;
  kind: string;
  pair: string;
  side: string;
  volume: string;
  reason: string;
  zone: number | null;
  price: number | null;
}

export function fetchEngineStatus(): Promise<FableEngineStatus> {
  return apiRequest<FableEngineStatus>("/api/v1/signals/engine/status");
}

export function fetchEngineDryRuns(limit = 50): Promise<FableEngineDryRun[]> {
  return apiRequest<FableEngineDryRun[]>(`/api/v1/signals/engine/dryruns?limit=${limit}`);
}

export function pineJsonTemplate(credentialPlaceholder = "tvsec_YOUR_SECRET"): string {
  return JSON.stringify(
    {
      schema_version: 1,
      credential: credentialPlaceholder,
      signal_id: "{{strategy.order.id}}:{{timenow}}",
      occurred_at: "{{timenow}}",
      strategy_id: "YOUR_STRATEGY",
      pair: "BTCUSD",
      side: "buy",
      volume: "0.001",
      order_type: "market",
      price: null,
      order_id: "{{strategy.order.id}}",
      raw_symbol: "{{ticker}}",
      observed_price: "{{close}}",
    },
    null,
    2
  );
}
