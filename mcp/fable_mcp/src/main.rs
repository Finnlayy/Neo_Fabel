//! Fable MCP stdio entrypoint — all logs to stderr, JSON-RPC on stdout.
//!
//! Modes:
//! - default / `--stdio`: MCP JSON-RPC on stdin/stdout
//! - `--health`: long-running HTTP health on FABLE_MCP_HEALTH_PORT (default 9100)
//!   for Docker compose (stdio is for Cursor / MCP clients attaching the binary)

use fable_mcp::McpServer;
use std::env;
use tokio::io::{AsyncReadExt, AsyncWriteExt};
use tokio::net::TcpListener;
use tracing::{info, warn};
use tracing_subscriber::EnvFilter;

#[tokio::main]
async fn main() {
    tracing_subscriber::fmt()
        .with_env_filter(EnvFilter::from_default_env().add_directive("fable_mcp=info".parse().unwrap()))
        .with_writer(std::io::stderr)
        .init();

    let args: Vec<String> = env::args().collect();
    let mode = args
        .iter()
        .find(|a| a.starts_with("--mode="))
        .map(|a| a.trim_start_matches("--mode=").to_string())
        .or_else(|| {
            if args.iter().any(|a| a == "--health") {
                Some("health".into())
            } else if args.iter().any(|a| a == "--stdio") {
                Some("stdio".into())
            } else {
                env::var("FABLE_MCP_MODE").ok()
            }
        })
        .unwrap_or_else(|| "stdio".into());

    match mode.as_str() {
        "health" => {
            if let Err(err) = run_health().await {
                eprintln!("fable-mcp health fatal: {err}");
                std::process::exit(1);
            }
        }
        _ => {
            let mut server = McpServer::default();
            if let Err(err) = server.run_stdio().await {
                eprintln!("fable-mcp fatal: {err}");
                std::process::exit(1);
            }
        }
    }
}

async fn run_health() -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    let port: u16 = env::var("FABLE_MCP_HEALTH_PORT")
        .ok()
        .and_then(|s| s.parse().ok())
        .unwrap_or(9100);
    let bind = format!("0.0.0.0:{port}");
    let listener = TcpListener::bind(&bind).await?;
    info!(%bind, "fable-mcp health listening (paper bridge sidecar; use binary for MCP stdio)");
    loop {
        let (mut socket, addr) = listener.accept().await?;
        tokio::spawn(async move {
            let mut buf = [0u8; 1024];
            let _ = socket.read(&mut buf).await;
            let body = b"{\"ok\":true,\"service\":\"fable-mcp\",\"mode\":\"health\",\"paper_only\":true}\n";
            let resp = format!(
                "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{}",
                body.len(),
                std::str::from_utf8(body).unwrap_or("{}")
            );
            if let Err(e) = socket.write_all(resp.as_bytes()).await {
                warn!(?addr, %e, "health write failed");
            }
        });
    }
}
