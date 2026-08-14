//! MCP JSON-RPC 2.0 stdio server — initialize, tools/list, tools/call (place_order).

use crate::blindfold::RawBar;
use crate::bridge::PaperBridge;
use crate::execution::{ExecutionEngine, PendingSignal, PositionSide};
use crate::prompt_builder::{OnnxScore, PatternHit, PromptBuilder, RnaContext};
use serde::Deserialize;
use serde_json::{json, Value};
use std::sync::Arc;
use thiserror::Error;
use tokio::io::{AsyncBufReadExt, AsyncWriteExt, BufReader};
use tokio::sync::Mutex;
use tracing::{debug, error, info};

const PROTOCOL_VERSION: &str = "2024-11-05";
const SERVER_NAME: &str = "fable-mcp";
const SERVER_VERSION: &str = env!("CARGO_PKG_VERSION");

#[derive(Debug, Error)]
pub enum McpError {
    #[error("parse error: {0}")]
    Parse(String),
    #[error("invalid request")]
    InvalidRequest,
    #[error("method not found: {0}")]
    MethodNotFound(String),
    #[error("invalid params: {0}")]
    InvalidParams(String),
}

pub struct McpServer {
    execution: Arc<Mutex<ExecutionEngine>>,
    prompt_builder: PromptBuilder,
    bridge: PaperBridge,
    initialized: bool,
}

impl Default for McpServer {
    fn default() -> Self {
        Self::new(10_000.0)
    }
}

impl McpServer {
    pub fn new(starting_balance: f64) -> Self {
        Self {
            execution: Arc::new(Mutex::new(ExecutionEngine::new(
                starting_balance,
                Default::default(),
            ))),
            prompt_builder: PromptBuilder::default(),
            bridge: PaperBridge::from_env(),
            initialized: false,
        }
    }

    /// Override bridge (tests).
    pub fn with_bridge(mut self, bridge: PaperBridge) -> Self {
        self.bridge = bridge;
        self
    }

    pub async fn run_stdio(&mut self) -> Result<(), McpError> {
        let stdin = tokio::io::stdin();
        let mut stdout = tokio::io::stdout();
        let mut reader = BufReader::new(stdin);
        let mut line = String::new();

        loop {
            line.clear();
            let n = reader
                .read_line(&mut line)
                .await
                .map_err(|e| McpError::Parse(e.to_string()))?;
            if n == 0 {
                break;
            }
            let trimmed = line.trim();
            if trimmed.is_empty() {
                continue;
            }

            let response = match serde_json::from_str::<JsonRpcRequest>(trimmed) {
                Ok(req) => self.handle_request(req).await,
                Err(e) => json!({
                    "jsonrpc": "2.0",
                    "id": null,
                    "error": { "code": -32700, "message": format!("Parse error: {e}") }
                }),
            };

            let frame =
                serde_json::to_string(&response).map_err(|e| McpError::Parse(e.to_string()))?;
            stdout
                .write_all(format!("{frame}\n").as_bytes())
                .await
                .map_err(|e| McpError::Parse(e.to_string()))?;
            stdout
                .flush()
                .await
                .map_err(|e| McpError::Parse(e.to_string()))?;
        }
        Ok(())
    }

    async fn handle_request(&mut self, req: JsonRpcRequest) -> Value {
        let id = req.id.clone();
        let result = match req.method.as_str() {
            "initialize" => self.handle_initialize(req.params).await,
            "notifications/initialized" => Ok(json!({})),
            "tools/list" => self.handle_tools_list().await,
            "tools/call" => self.handle_tools_call(req.params).await,
            "ping" => Ok(json!({})),
            other => Err(McpError::MethodNotFound(other.to_string())),
        };

        match result {
            Ok(value) => json!({ "jsonrpc": "2.0", "id": id, "result": value }),
            Err(err) => {
                let code = match &err {
                    McpError::Parse(_) => -32700,
                    McpError::InvalidRequest => -32600,
                    McpError::MethodNotFound(_) => -32601,
                    McpError::InvalidParams(_) => -32602,
                };
                error!(?err, "MCP error");
                json!({
                    "jsonrpc": "2.0",
                    "id": id,
                    "error": { "code": code, "message": err.to_string() }
                })
            }
        }
    }

    async fn handle_initialize(&mut self, params: Option<Value>) -> Result<Value, McpError> {
        let _ = params;
        self.initialized = true;
        info!("MCP initialize");
        Ok(json!({
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": { "tools": {} },
            "serverInfo": { "name": SERVER_NAME, "version": SERVER_VERSION }
        }))
    }

    async fn handle_tools_list(&self) -> Result<Value, McpError> {
        Ok(json!({
            "tools": [
                {
                    "name": "place_order",
                    "description": "Queue a paper order for next-bar open execution (t+1). Logs rationale to audit trail. Fill is bridged to LocalPaperLedger on process_next_bar.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "side": { "type": "string", "enum": ["buy", "sell"] },
                            "volume": { "type": "number", "minimum": 0 },
                            "stop_loss": { "type": "number" },
                            "take_profit": { "type": "number" },
                            "pair": { "type": "string", "description": "Paper pair (default FABLE_MCP_DEFAULT_PAIR / ADAUSD)" },
                            "rationale": { "type": "string", "maxLength": 180 }
                        },
                        "required": ["side", "volume", "rationale"]
                    }
                },
                {
                    "name": "build_prompt_snapshot",
                    "description": "Build blindfolded prompt context from raw OHLCV bars and pattern/RNA/ONNX inputs.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "bars": { "type": "array" },
                            "patterns": { "type": "array" },
                            "rna": { "type": "object" },
                            "onnx": { "type": "object" },
                            "rationale_tail": { "type": "array", "items": { "type": "string" } }
                        },
                        "required": ["bars"]
                    }
                },
                {
                    "name": "process_next_bar",
                    "description": "Advance execution engine one bar (next-bar open fill + SL/TP). Entry/exit fills POST to paper bridge (fail-soft).",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "open": { "type": "number" },
                            "high": { "type": "number" },
                            "low": { "type": "number" },
                            "close": { "type": "number" }
                        },
                        "required": ["open", "high", "low", "close"]
                    }
                }
            ]
        }))
    }

    async fn handle_tools_call(&self, params: Option<Value>) -> Result<Value, McpError> {
        let params = params.ok_or(McpError::InvalidParams("missing params".into()))?;
        let name = params
            .get("name")
            .and_then(|v| v.as_str())
            .ok_or_else(|| McpError::InvalidParams("missing tool name".into()))?;
        let args = params.get("arguments").cloned().unwrap_or(json!({}));

        let content = match name {
            "place_order" => self.tool_place_order(args).await?,
            "build_prompt_snapshot" => self.tool_build_prompt_snapshot(args)?,
            "process_next_bar" => self.tool_process_next_bar(args).await?,
            other => return Err(McpError::MethodNotFound(format!("tool:{other}"))),
        };

        Ok(json!({
            "content": [{ "type": "text", "text": content }],
            "isError": false
        }))
    }

    async fn tool_place_order(&self, args: Value) -> Result<String, McpError> {
        let side_str = args
            .get("side")
            .and_then(|v| v.as_str())
            .ok_or_else(|| McpError::InvalidParams("side required".into()))?;
        let volume = args
            .get("volume")
            .and_then(|v| v.as_f64())
            .ok_or_else(|| McpError::InvalidParams("volume required".into()))?;
        if volume <= 0.0 {
            return Err(McpError::InvalidParams("volume must be > 0".into()));
        }
        let rationale = args
            .get("rationale")
            .and_then(|v| v.as_str())
            .unwrap_or("MCP place_order")
            .chars()
            .take(180)
            .collect::<String>();

        let side = match side_str.to_lowercase().as_str() {
            "buy" => PositionSide::Buy,
            "sell" => PositionSide::Sell,
            _ => return Err(McpError::InvalidParams("side must be buy or sell".into())),
        };

        let pair = args
            .get("pair")
            .and_then(|v| v.as_str())
            .map(|s| s.trim().to_uppercase().replace(['/', '-'], ""))
            .filter(|s| !s.is_empty())
            .unwrap_or_else(|| {
                std::env::var("FABLE_MCP_DEFAULT_PAIR").unwrap_or_else(|_| "ADAUSD".into())
            });

        let signal = PendingSignal {
            side,
            volume,
            stop_loss: args.get("stop_loss").and_then(|v| v.as_f64()),
            take_profit: args.get("take_profit").and_then(|v| v.as_f64()),
            rationale: rationale.clone(),
            pair: pair.clone(),
        };

        let mut eng = self.execution.lock().await;
        eng.queue_signal(signal);
        info!(side = ?side, volume, %pair, %rationale, "place_order queued for t+1");
        Ok(serde_json::to_string(&json!({
            "status": "queued",
            "side": side_str,
            "volume": volume,
            "pair": pair,
            "rationale": rationale,
        }))
        .map_err(|e| McpError::Parse(e.to_string()))?)
    }

    fn tool_build_prompt_snapshot(&self, args: Value) -> Result<String, McpError> {
        let bars_val = args
            .get("bars")
            .and_then(|v| v.as_array())
            .ok_or_else(|| McpError::InvalidParams("bars array required".into()))?;

        let raw_bars: Vec<RawBar> = bars_val
            .iter()
            .filter_map(|b| {
                Some(RawBar {
                    open: b.get("open")?.as_f64()?,
                    high: b.get("high")?.as_f64()?,
                    low: b.get("low")?.as_f64()?,
                    close: b.get("close")?.as_f64()?,
                    volume: b.get("volume").and_then(|v| v.as_f64()).unwrap_or(0.0),
                })
            })
            .collect();

        let patterns: Vec<PatternHit> = args
            .get("patterns")
            .and_then(|v| v.as_array())
            .map(|arr| {
                arr.iter()
                    .filter_map(|p| {
                        Some(PatternHit {
                            name: p.get("name")?.as_str()?.to_string(),
                            bias: p.get("bias")?.as_str()?.to_string(),
                            confidence: p.get("confidence")?.as_f64()?,
                            kind: p
                                .get("kind")
                                .and_then(|k| k.as_str())
                                .unwrap_or("single")
                                .to_string(),
                        })
                    })
                    .collect()
            })
            .unwrap_or_default();

        let rna = args.get("rna").and_then(|v| {
            Some(RnaContext {
                bias: v.get("bias")?.as_str()?.to_string(),
                confidence: v.get("confidence")?.as_f64()?,
                symbol: v.get("symbol").and_then(|s| s.as_str()).map(str::to_string),
            })
        });

        let onnx = args.get("onnx").and_then(|v| {
            Some(OnnxScore {
                direction: v.get("direction")?.as_str()?.to_string(),
                confidence: v.get("confidence")?.as_f64()?,
                prediction: v.get("prediction").and_then(|p| p.as_f64()).unwrap_or(0.0),
                model_id: v
                    .get("model_id")
                    .and_then(|m| m.as_str())
                    .unwrap_or("model4")
                    .to_string(),
            })
        });

        let rationale_tail: Vec<String> = args
            .get("rationale_tail")
            .and_then(|v| v.as_array())
            .map(|arr| {
                arr.iter()
                    .filter_map(|s| s.as_str().map(str::to_string))
                    .collect()
            })
            .unwrap_or_default();

        let snap = self.prompt_builder.build_prompt_snapshot(
            &raw_bars,
            &patterns,
            rna,
            onnx,
            &rationale_tail,
        );
        serde_json::to_string(&snap).map_err(|e| McpError::Parse(e.to_string()))
    }

    async fn tool_process_next_bar(&self, args: Value) -> Result<String, McpError> {
        use crate::execution::NextBar;
        let bar = NextBar {
            open: args
                .get("open")
                .and_then(|v| v.as_f64())
                .ok_or_else(|| McpError::InvalidParams("open required".into()))?,
            high: args
                .get("high")
                .and_then(|v| v.as_f64())
                .ok_or_else(|| McpError::InvalidParams("high required".into()))?,
            low: args
                .get("low")
                .and_then(|v| v.as_f64())
                .ok_or_else(|| McpError::InvalidParams("low required".into()))?,
            close: args
                .get("close")
                .and_then(|v| v.as_f64())
                .ok_or_else(|| McpError::InvalidParams("close required".into()))?,
        };
        let mut eng = self.execution.lock().await;
        let events = eng.process_next_bar_open(&bar);
        let balance_usd = eng.balance_usd;
        let position = eng.position.clone();
        drop(eng);

        // Fail-soft: bridge errors are reported in the tool result, never panic MCP.
        let bridge_results = self.bridge.post_fills(&events).await;
        let bridge_ok = bridge_results.iter().all(|r| r.ok);
        debug!(events = events.len(), bridge_ok, "process_next_bar");

        serde_json::to_string(&json!({
            "events": events,
            "balance_usd": balance_usd,
            "position": position,
            "bridge": {
                "ok": bridge_ok,
                "results": bridge_results.iter().map(|r| r.to_json()).collect::<Vec<_>>(),
            }
        }))
        .map_err(|e| McpError::Parse(e.to_string()))
    }
}

#[derive(Debug, Deserialize)]
struct JsonRpcRequest {
    #[serde(default)]
    id: Value,
    method: String,
    #[serde(default)]
    params: Option<Value>,
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::bridge::BridgeConfig;

    #[tokio::test]
    async fn tools_list_includes_place_order() {
        let server = McpServer::default();
        let res = server.handle_tools_list().await.unwrap();
        let tools = res.get("tools").unwrap().as_array().unwrap();
        assert!(tools
            .iter()
            .any(|t| t.get("name").unwrap() == "place_order"));
    }

    #[tokio::test]
    async fn place_order_queues_signal() {
        let server = McpServer::default().with_bridge(PaperBridge::new(BridgeConfig {
            enabled: false,
            base_url: "http://127.0.0.1:1".into(),
            token: None,
            timeout_ms: 200,
        }));
        let res = server
            .handle_tools_call(Some(json!({
                "name": "place_order",
                "arguments": {
                    "side": "buy",
                    "volume": 1.5,
                    "rationale": "grid zone 2"
                }
            })))
            .await
            .unwrap();
        let text = res["content"][0]["text"].as_str().unwrap();
        assert!(text.contains("queued"));
    }

    #[tokio::test]
    async fn process_next_bar_reports_bridge_failure_soft() {
        let server = McpServer::default().with_bridge(PaperBridge::new(BridgeConfig {
            enabled: true,
            base_url: "http://127.0.0.1:1".into(),
            token: None,
            timeout_ms: 300,
        }));
        server
            .handle_tools_call(Some(json!({
                "name": "place_order",
                "arguments": {
                    "side": "buy",
                    "volume": 10.0,
                    "pair": "ADAUSD",
                    "rationale": "smoke entry"
                }
            })))
            .await
            .unwrap();
        let res = server
            .handle_tools_call(Some(json!({
                "name": "process_next_bar",
                "arguments": { "open": 0.5, "high": 0.51, "low": 0.49, "close": 0.505 }
            })))
            .await
            .unwrap();
        let text = res["content"][0]["text"].as_str().unwrap();
        let body: Value = serde_json::from_str(text).unwrap();
        assert!(body["events"].as_array().unwrap().len() >= 1);
        assert_eq!(body["bridge"]["ok"], false);
        // Local execution still applied despite bridge failure.
        assert!(body["position"].is_object());
    }
}
