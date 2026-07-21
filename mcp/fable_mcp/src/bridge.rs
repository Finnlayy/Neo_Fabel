//! HTTP bridge: Rust fable-mcp fills → Neo Fabel LocalPaperLedger.
//!
//! Datei: bridge.rs
//! Zweck: Soft-fail POST von Fill-Events an POST /api/v1/mcp/paper/fill (nur Paper).
//! Erstellt: 2026-07-21 | Version: 1.0
//! Sicherheit: Nie Live-Kraken; Bridge-Fehler panic'en nicht den MCP-Stdio-Server.

use crate::execution::FillEvent;
use serde_json::{json, Value};
use tracing::{info, warn};

const DEFAULT_BRIDGE_URL: &str = "http://127.0.0.1:8000";
const FILL_PATH: &str = "/api/v1/mcp/paper/fill";

/// Env-driven bridge configuration (paper-only).
#[derive(Debug, Clone)]
pub struct BridgeConfig {
    pub enabled: bool,
    pub base_url: String,
    pub token: Option<String>,
    pub timeout_ms: u64,
}

impl BridgeConfig {
    pub fn from_env() -> Self {
        let enabled = std::env::var("FABLE_MCP_BRIDGE_ENABLED")
            .map(|v| !matches!(v.to_lowercase().as_str(), "0" | "false" | "no" | "off"))
            .unwrap_or(true);
        let base_url = std::env::var("FABLE_MCP_BRIDGE_URL")
            .unwrap_or_else(|_| DEFAULT_BRIDGE_URL.into())
            .trim_end_matches('/')
            .to_string();
        let token = std::env::var("FABLE_MCP_BRIDGE_TOKEN")
            .ok()
            .map(|t| t.trim().to_string())
            .filter(|t| !t.is_empty());
        let timeout_ms = std::env::var("FABLE_MCP_BRIDGE_TIMEOUT_MS")
            .ok()
            .and_then(|s| s.parse().ok())
            .unwrap_or(3_000);
        Self {
            enabled,
            base_url,
            token,
            timeout_ms,
        }
    }

    pub fn fill_url(&self) -> String {
        format!("{}{}", self.base_url, FILL_PATH)
    }
}

/// Result of a soft-fail bridge POST (never panics the caller).
#[derive(Debug, Clone, PartialEq)]
pub struct BridgePostResult {
    pub ok: bool,
    pub status: Option<u16>,
    pub error: Option<String>,
}

impl BridgePostResult {
    pub fn skipped() -> Self {
        Self {
            ok: true,
            status: None,
            error: None,
        }
    }

    pub fn to_json(&self) -> Value {
        json!({
            "ok": self.ok,
            "status": self.status,
            "error": self.error,
        })
    }
}

/// Build JSON body for the FastAPI paper fill endpoint.
pub fn fill_payload(event: &FillEvent) -> Value {
    let rationale: String = event.rationale.chars().take(180).collect();
    json!({
        "event": event.event,
        "side": match event.side {
            crate::execution::PositionSide::Buy => "buy",
            crate::execution::PositionSide::Sell => "sell",
        },
        "pair": event.pair,
        "price": event.price,
        "volume": event.volume,
        "pnl": event.pnl,
        "rationale": rationale,
        "market_type": "spot",
        "source": "fable-mcp",
    })
}

/// HTTP client that posts fills to Neo Fabel (fail-soft).
#[derive(Debug, Clone)]
pub struct PaperBridge {
    pub config: BridgeConfig,
    client: reqwest::Client,
}

impl PaperBridge {
    pub fn from_env() -> Self {
        Self::new(BridgeConfig::from_env())
    }

    pub fn new(config: BridgeConfig) -> Self {
        let client = reqwest::Client::builder()
            .timeout(std::time::Duration::from_millis(config.timeout_ms))
            .build()
            .unwrap_or_else(|_| reqwest::Client::new());
        Self { config, client }
    }

    /// POST a single fill. Never panics; returns soft-fail status.
    pub async fn post_fill(&self, event: &FillEvent) -> BridgePostResult {
        if !self.config.enabled {
            return BridgePostResult::skipped();
        }
        let url = self.config.fill_url();
        let body = fill_payload(event);
        let mut req = self.client.post(&url).json(&body);
        if let Some(token) = &self.config.token {
            req = req.bearer_auth(token);
        }
        match req.send().await {
            Ok(resp) => {
                let status = resp.status().as_u16();
                if resp.status().is_success() {
                    info!(%url, status, event = %event.event, "bridge fill ok");
                    BridgePostResult {
                        ok: true,
                        status: Some(status),
                        error: None,
                    }
                } else {
                    let text = resp.text().await.unwrap_or_default();
                    let msg: String = text.chars().take(200).collect();
                    warn!(%url, status, %msg, "bridge fill HTTP error");
                    BridgePostResult {
                        ok: false,
                        status: Some(status),
                        error: Some(format!("HTTP {status}: {msg}")),
                    }
                }
            }
            Err(err) => {
                let msg = err.to_string();
                warn!(%url, %msg, "bridge fill transport error");
                BridgePostResult {
                    ok: false,
                    status: None,
                    error: Some(msg),
                }
            }
        }
    }

    /// Post all fill events; returns per-event bridge results (fail-soft).
    pub async fn post_fills(&self, events: &[FillEvent]) -> Vec<BridgePostResult> {
        let mut out = Vec::with_capacity(events.len());
        for ev in events {
            out.push(self.post_fill(ev).await);
        }
        out
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::execution::PositionSide;

    fn sample_entry() -> FillEvent {
        FillEvent {
            event: "entry".into(),
            side: PositionSide::Buy,
            price: 0.45,
            volume: 100.0,
            pnl: None,
            rationale: "grid zone 2".into(),
            pair: "ADAUSD".into(),
        }
    }

    #[test]
    fn fill_payload_truncates_rationale() {
        let mut ev = sample_entry();
        ev.rationale = "x".repeat(250);
        let body = fill_payload(&ev);
        assert_eq!(body["rationale"].as_str().unwrap().len(), 180);
        assert_eq!(body["pair"], "ADAUSD");
        assert_eq!(body["side"], "buy");
        assert_eq!(body["event"], "entry");
    }

    #[test]
    fn bridge_config_defaults() {
        let cfg = BridgeConfig {
            enabled: true,
            base_url: "http://api:8000".into(),
            token: None,
            timeout_ms: 3000,
        };
        assert_eq!(cfg.fill_url(), "http://api:8000/api/v1/mcp/paper/fill");
    }

    #[tokio::test]
    async fn post_fill_fails_soft_when_unreachable() {
        let bridge = PaperBridge::new(BridgeConfig {
            enabled: true,
            base_url: "http://127.0.0.1:1".into(), // closed port
            token: None,
            timeout_ms: 500,
        });
        let result = bridge.post_fill(&sample_entry()).await;
        assert!(!result.ok);
        assert!(result.error.is_some());
    }

    #[tokio::test]
    async fn post_fill_skipped_when_disabled() {
        let bridge = PaperBridge::new(BridgeConfig {
            enabled: false,
            base_url: "http://127.0.0.1:1".into(),
            token: None,
            timeout_ms: 500,
        });
        let result = bridge.post_fill(&sample_entry()).await;
        assert!(result.ok);
        assert!(result.error.is_none());
    }
}
