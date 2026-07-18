export type SignalMode = "bypass_ai" | "advisory";

export interface SignalAutomationStatus {
  signal_routes_enabled: boolean;
  tradingview_ingress_enabled: boolean;
  mcp_signal_adapter_enabled: boolean;
  signal_worker_enabled: boolean;
  signal_execution_enabled: boolean;
  ai_advisory_enabled: boolean;
  execution_target: "kraken_paper";
  paper_only: true;
  queue_depth: number;
  oldest_ready_age_seconds: number | null;
  worker_heartbeat_ok: boolean;
  advisory_ready: boolean;
}

export interface SignalRoute {
  id: string;
  public_route_key: string;
  name: string;
  strategy_id: string;
  mode: SignalMode;
  enabled: boolean;
  execution_target: "kraken_paper";
  pair_allowlist: string;
  max_volume: string;
  max_notional: string | null;
  allowed_order_types: string;
  max_event_age_seconds: number;
  max_rate_per_minute: number;
  max_backlog: number;
  policy_version: string;
  version: number;
  created_at: string;
  updated_at: string;
  webhook_url_path: string;
  has_tradingview_credential: boolean;
  has_mcp_credential: boolean;
}

export interface CredentialReveal {
  credential_id: string;
  kind: "tradingview_secret" | "mcp_bearer";
  plaintext: string;
  display_prefix: string;
  activated_at: string;
}

export interface SignalSubmission {
  id: string;
  route_id: string;
  source: "tradingview" | "mcp";
  signal_id: string;
  pair: string;
  side: string;
  volume: string;
  order_type: string;
  mode_snapshot: string;
  status: string;
  reason_code: string | null;
  request_id: string;
  paper_intent_id: string | null;
  occurred_at: string;
  created_at: string;
  updated_at: string;
  advisory_decision: string | null;
}
