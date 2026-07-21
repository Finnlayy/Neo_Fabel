# Fable MCP (Rust)

Datei: README.md  
Zweck: Build, run, tools, paper bridge, Docker for `fable-mcp`.  
Erstellt: 2026-07-21 | Version: 1.0

Paper-only MCP stdio server: prompt snapshots, next-bar execution, and HTTP bridge into Neo Fabel `LocalPaperLedger`. **Never places live Kraken orders.**

## Build

```powershell
cargo build --release --manifest-path mcp/fable_mcp/Cargo.toml
```

| OS | Release binary |
|----|----------------|
| Windows | `mcp/fable_mcp/target/release/fable-mcp.exe` |
| Linux / macOS | `mcp/fable_mcp/target/release/fable-mcp` |

## Run (MCP stdio)

Logs go to **stderr**; JSON-RPC frames only on **stdout**.

```powershell
# Preferred (production): release binary
$env:FABLE_MCP_BRIDGE_URL = "http://127.0.0.1:8000"
.\mcp\fable_mcp\target\release\fable-mcp.exe

# Dev: cargo run
cargo run --quiet --manifest-path mcp/fable_mcp/Cargo.toml
```

Cursor / Claude Desktop: see `mcp_config.example.json` (release binary preferred).

### Tools

| Tool | Role |
|------|------|
| `place_order` | Queue paper signal for t+1 open (rationale ≤180 chars) |
| `process_next_bar` | Fill at next open + SL/TP; POST fills to paper bridge (fail-soft) |
| `build_prompt_snapshot` | Blindfolded prompt context |

### Bridge env vars

| Variable | Default | Meaning |
|----------|---------|---------|
| `FABLE_MCP_BRIDGE_URL` | `http://127.0.0.1:8000` | FastAPI base URL |
| `FABLE_MCP_BRIDGE_ENABLED` | `true` | Skip HTTP when `false` |
| `FABLE_MCP_BRIDGE_TOKEN` | _(empty)_ | Optional `Authorization: Bearer` |
| `FABLE_MCP_BRIDGE_TIMEOUT_MS` | `3000` | HTTP timeout |
| `FABLE_MCP_DEFAULT_PAIR` | `ADAUSD` | Default paper pair |
| `FABLE_MCP_MODE` | `stdio` | `stdio` or `health` |
| `FABLE_MCP_HEALTH_PORT` | `9100` | Health bind for Docker |

Bridge endpoint (API side): `POST /api/v1/mcp/paper/fill` — paper only.

## Docker

```powershell
docker compose --profile mcp up --build fable-mcp api
```

Service `fable-mcp` runs **health mode** (`GET :9100`) so Compose has a long-lived process. MCP clients should use the release binary on the host (or `docker compose exec fable-mcp fable-mcp --stdio`). Bridge URL inside Compose: `http://api:8000`.

## Tests

```powershell
cargo test --manifest-path mcp/fable_mcp/Cargo.toml
python -m pytest backend/tests/test_mcp_paper_bridge.py backend/tests/test_onnx_bias.py -q
```
