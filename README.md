<div align="center">
<img width="1200" height="475" alt="GHBanner" src="https://ai.google.dev/static/site-assets/images/share-ais-513315318.png" />
</div>

# Neo Fabel

React/Vite is the frontend and Python/FastAPI is the authoritative API. The
application defaults to paper trading (autonomy level 2). Live autonomous
trading (Level 4) requires explicit env gates plus operational scripts.

## Run Locally

**Prerequisites:** Node.js 20+, Python 3.11+, PostgreSQL for persistence, and
the official `kraken` binary for market/paper smoke tests.


1. Install frontend dependencies: `npm install`
2. Install backend dependencies: `python -m pip install -e "backend[test,lint]"`  
   (includes [google-antigravity](https://github.com/google-antigravity/antigravity-sdk-python) from PyPI — do not install from a bare git clone; wheels ship the runtime binary)
3. Copy [.env.example](.env.example) to `.env.local` and add secrets only to
   that ignored local file.
4. Start FastAPI: `python -m uvicorn backend.app.main:app --reload --port 8000`
5. Start Vite in a second terminal: `npm run dev`

### OpenAPI → frontend types

Frontend transport stays [`src/api/client.ts`](src/api/client.ts) (`apiRequest` + Firebase Bearer).
Path/schema types are generated from the live FastAPI OpenAPI document:

```powershell
# API must be running on :8000
npm run openapi:gen
```

That writes [`src/api/generated/schema.d.ts`](src/api/generated/schema.d.ts). Helpers live in [`src/api/paths.ts`](src/api/paths.ts); the paper module is the first consumer. Vite also proxies `/openapi.json`, `/docs`, and `/redoc` to the API.

Market-data endpoints:

- `GET /api/v1/market/batch?asset_class=all` queries the curated common crypto, FX, and S&P 500 universe. Crypto uses the Kraken CLI; FX and equities use Alpha Vantage.
- `GET /api/v1/market/ohlcv?asset_class=sp500&symbols=AAPL,MSFT&intervals=1min,5min,15min,60min,4h` requests OHLCV bars. Alpha Vantage's 60-minute data is deterministically aggregated into 4-hour bars. Missing provider entitlements are returned per item as explicit errors.

### AI chat wire protocol (token budget)

`POST /api/chat` no longer forwards the full UI transcript. The client builds a sliding window via `src/api/chatWire.ts` (last 12 substantive turns, 4k chars/message); the server trims again via `trim_chat_messages` (`AI_CHAT_MAX_MESSAGES` / `AI_CHAT_MAX_CHARS` / `AI_CHAT_MAX_CONTENT_CHARS`). Welcome/reset messages are `ephemeral` and excluded from the Gemini payload. `POST /api/gemini/analyze-trades` sends the last ~25 trades only. Orchestrate stays single-prompt (no history). Response may include `context: { trimmed, sent_chars, … }` for observability.

### Master Orchestrator doctrine + prompt shots

Paper-only coordinator brain under `backend/app/ai_prompts/`:

- `orchestrator_doctrine.md` — roster, status packets, convergence signals, Kraken DELEGATE/REFUSE
- `kraken_broker_skill_index.md` — slim 51-skill index (`paper_ok` | `live_gated`); never full plugin `SKILL.md` bodies
- `prompt_shots/*.json` — ≤3 few-shot templates injected into systemInstruction (≤~6k chars total)

`POST /api/gemini/orchestrate` and `POST /api/chat` with `mode: "orchestrator"` load doctrine + shots (+ index if budget). Optional `agentStatusPackets` carry compact `{id, status, lastAction≤200, directive≤280}` from the swarm UI. Usage is logged to `backend/data/academy/prompt_shot_log.jsonl`; `prompt_shot_optimizer` feeds `prompt_evolution` / A/B from careers, drills, and routing failures.

### Trading Orchestrator advisory

The dashboard's Master Orchestrator can run a manual, authenticated advisory
analysis through `src/api/orchestrator.ts`. It classifies the market regime,
scores resolved Telegram signals, explains the ranking, and recommends
informational strategy weights. It has no imports or calls into paper/live order
execution and always returns `mode: advisory` plus `executionAllowed: false`.

Enable it deliberately in `.env.local`:

```env
ORCHESTRATOR_ADVISORY_ENABLED=true
# Configure at least one provider from AI_PROVIDER_ORDER.
OPENROUTER_API_KEY=replace-locally
```

Apply the audit-table migration before using decision history:

```powershell
docker compose run --rm api alembic -c backend/alembic.ini upgrade head
```

API surface:

| Endpoint | Purpose |
|---|---|
| `POST /api/v1/orchestrator/market-regime` | Standalone regime analysis |
| `POST /api/v1/orchestrator/signal-quality` | Standalone signal scoring |
| `POST /api/v1/orchestrator/full-decision` | One consistent dashboard advisory |
| `GET /api/v1/orchestrator/decisions` | User-scoped advisory history |

The feature is manual-only: there is no polling or automatic LLM spend. Missing
providers return an explicit error and never synthesize a neutral recommendation.
Provider credentials belong only in ignored local environment files.

```powershell
python -m pytest backend/tests/test_prompt_shots.py backend/tests/test_academy.py -q
```

### Agent Academy (training loop)

Synthetic drills + career tracking for Neo sub-agents. **Paper / training only — never places live orders.** UI tab: **Academy** (hotkey `6`). Persistence: `backend/data/academy/` (gitignored).

### ONNX Neural Core (Tab 7)

Exclusive workspace (hotkey `7`) for LSTM/ONNX inference, training, and Netron graph viewing. Optional backend deps:

```bash
pip install -e "backend[onnx]"
# or from backend/: pip install -e ".[onnx]"
python -m backend.scripts.export_seed_models
```

APIs: `/api/v1/onnx/*` (status, models, train, infer). Static models for Netron: `/static/onnx/*.onnx`. Viewer: `/static/netron/` (upstream Netron when the `netron` package is installed, else a stub page). **Paper research only — never places live orders.**

### Chronos (kline language agent)

Self-taught forecasting substrate — **paper research only**. Optional Python stack:

```bash
pip install -e "backend[chronos]"
# numpy, pandas, matplotlib, PyTorch (CPU wheel), vectorbt
```

PineTS (`pinets`) is **Node.js**, not pip — install separately for Pine Script indicators:

```bash
npm install -g pinets-cli
# or: npx pinets-cli run path/to/script.pine --data candles.json
```

`GET /api/v1/chronos/status` reports `deps` (`numpy`, `pandas`, `torch`, `vectorbt`, `pinets_cli`). Additional endpoints when deps are present:

| Endpoint | Requires | Purpose |
|---|---|---|
| `POST /api/v1/chronos/indicators` | numpy + pandas | RSI, EMA distance %, ATR % |
| `POST /api/v1/chronos/research/backtest` | vectorbt | Paper EMA-cross sanity metric on lookback |

See [`CHRONOS_AGENT_PLAN.md`](CHRONOS_AGENT_PLAN.md) for Phase 2+ (AE tokenizer, decoder, ONNX export).

| Endpoint | Purpose |
|---|---|
| `GET /api/v1/academy/status` | Loop status, diversity, recent drills |
| `POST /api/v1/academy/train/start\|stop\|cycle` | Control / run one training cycle |
| `GET /api/v1/academy/agents/registry` | Remapped Neo agents + career stats |
| `GET /api/v1/academy/drills/available?scout_name=` | Generate drills (`rna_smart` uses blind candle geometry) |
| `POST /api/v1/academy/drill/evaluate` | Score a drill decision |

Flags: `TRAINING_LOOP_ENABLED`, `TRAINING_LOOP_AUTO_START` (default off), night window + drills/hour — see `.env.example`.

```powershell
python -m pytest backend/tests/test_academy.py -q
```

Set `ALPHAVANTAGE_API_KEY` (or `ALPHA_VANTAGE_API_KEY`) in `.env.local`. Full equity batches use Alpha Vantage's bulk quote entitlement, so set `ALPHAVANTAGE_BULK_QUOTES_ENABLED=true` only when that entitlement is available. Intraday equity and crypto endpoints may also require a premium Alpha Vantage plan; the API never substitutes mock data.

Docker path (required on Windows for paper trades — Kraken CLI is Linux-only):

```powershell
# Stop any native Windows uvicorn on :8000 first, then (from D:\Neo_Fabel):
Copy-Item -Force .env.local .env   # Compose expects .env for ${VAR} substitution
docker compose -f docker-compose.yml -f docker-compose.local.yml up --build api postgres
```

- API (Linux + `/usr/local/bin/kraken`): `http://127.0.0.1:8000`
- Keep Vite on the host: `npm run dev` → `http://localhost:5173`
- Do **not** run `python -m uvicorn` on Windows if you need paper orders — that process has no Kraken CLI.
- Optional Rust MCP sidecar (paper bridge health on `:9100`): `docker compose --profile mcp up --build fable-mcp` — see `mcp/fable_mcp/README.md`. Cursor should use the release binary (`mcp/fable_mcp/target/release/fable-mcp.exe`), not Compose stdio.

Apply migrations from the API image: `docker compose run --rm api alembic -c backend/alembic.ini upgrade head`

### Production web stack (nginx + compression)

Full stack including the SPA:

```powershell
docker compose up --build
```

- **Web (nginx):** `http://127.0.0.1:8080` — serves `dist/` with **gzip** for JS/CSS/JSON, **immutable cache** on `/assets/*`, **no-cache** on `index.html`, proxies `/api/` and `/static/` (ONNX/Netron) to the API container.
- **API (FastAPI):** `http://127.0.0.1:8000` — **GZipMiddleware** for direct hits; `/static/*` gets `Cache-Control: private, max-age=300`. Live JSON/WebSocket responses are not long-cached.

Firebase Hosting (`firebase.json`) mirrors the asset cache headers; CDN gzip/brotli applies at the edge.

Smoke after `docker compose up --build`:

```powershell
curl -sI -H "Accept-Encoding: gzip" http://127.0.0.1:8080/index.html   # Cache-Control: no-cache
curl -sI -H "Accept-Encoding: gzip" http://127.0.0.1:8000/openapi.json   # Content-Encoding: gzip
```

## Phase 1 — Qdrant vector index

Paper/dev vector storage for the Neural Vector Analyzer. **No live trading.**
FastAPI owns the Qdrant client; the React UI calls `/api/v1/vector/*` (Vite proxies
to port 8000) and falls back to an honest **RAM FALLBACK** label when Qdrant is down
(never claims “live Qdrant” for in-memory mode).

| Variable | Default | Purpose |
|----------|---------|---------|
| `QDRANT_ENABLED` | `true` | Feature gate |
| `QDRANT_URL` | `http://localhost:6333` | Local Docker or Qdrant Cloud URL |
| `QDRANT_API_KEY` | empty | Required for Qdrant Cloud; omit for local |
| `QDRANT_COLLECTION` | `neo_fabel_vectors` | Collection name |
| `QDRANT_VECTOR_SIZE` | `8` | Must match Neural Vector Analyzer dims |

Local Compose (Postgres + Qdrant):

```powershell
docker compose up -d postgres qdrant
```

Ports: Postgres `5432`; Qdrant REST `6333` and gRPC `6334` are bound to
`127.0.0.1` only. Containers access Qdrant over the internal Compose network.

API endpoints:

- `GET /api/v1/vector/health` — readiness probe (no auth)
- `GET /api/v1/vector/ready` — 200 only when Qdrant is up
- `POST /api/v1/vector/collections/ensure` — authenticated collection creation (cosine, size from env)
- `POST /api/v1/vector/points` — authenticated point upsert
- `POST /api/v1/vector/search` — authenticated cosine search
- `GET /api/v1/vector/points` — authenticated list/scroll
- `DELETE /api/v1/vector/points/{id}` — authenticated deletion by document id

Smoke (after API is running with `.env.local`):

```powershell
curl http://127.0.0.1:8000/api/v1/vector/health
# Supply a short-lived Firebase ID token obtained by the signed-in frontend.
$token = "FIREBASE_ID_TOKEN"
curl -X POST http://127.0.0.1:8000/api/v1/vector/collections/ensure -H "Authorization: Bearer $token"
curl -X POST http://127.0.0.1:8000/api/v1/vector/points -H "Authorization: Bearer $token" -H "Content-Type: application/json" -d "{\"points\":[{\"id\":\"VEC-SMOKE\",\"title\":\"Smoke\",\"category\":\"strategy\",\"vector\":[0.1,0.2,0.3,0.4,0.5,0.6,0.7,0.8],\"metadata\":{\"description\":\"phase1\"}}]}"
curl -X POST http://127.0.0.1:8000/api/v1/vector/search -H "Authorization: Bearer $token" -H "Content-Type: application/json" -d "{\"vector\":[0.1,0.2,0.3,0.4,0.5,0.6,0.7,0.8],\"top_k\":3,\"metric\":\"cosine\"}"
```

## Phase 2 — CCXT + WebSocket market stream

Read-only live crypto tickers. FastAPI owns a CCXT (Kraken) poller that fans out
over `WS /api/v1/market/stream`. The React UI prefers the WebSocket and falls
back to `GET /api/v1/market/batch`. **No exchange API keys. No live trading.**
TimescaleDB/Influx and Socket.io are deferred; history is an in-process ring buffer
plus the existing Alpha Vantage OHLCV HTTP path for equities/FX.

| Variable | Default | Purpose |
|----------|---------|---------|
| `MARKET_STREAM_ENABLED` | `true` | Start the stream hub + WS endpoint |
| `MARKET_CCXT_ENABLED` | `true` | Prefer CCXT for crypto batch/stream |
| `MARKET_CCXT_EXCHANGE` | `kraken` | CCXT exchange id (public only) |
| `MARKET_STREAM_INTERVAL_SECONDS` | `5` | Poll cadence for the hub |
| `MARKET_STREAM_SYMBOLS` | BTC/ETH/… | Comma-separated CCXT symbols |

Endpoints:

- `GET /api/v1/market/stream/health` — hub readiness (no auth)
- `WS /api/v1/market/stream` — ticker snapshots `{type:"tickers", tickers:[…]}`
- Existing `GET /api/v1/market/batch` — uses CCXT when enabled, else Kraken public REST

Smoke (API on `:8000`):

```powershell
curl http://127.0.0.1:8000/api/v1/market/stream/health
# Browser / Vite (`localhost:5173`) opens WS via the `/api` proxy (ws: true).
```

## Phase 3 — paper execution API

Paper-only trade surface (live trading stays gated):

| Path | Purpose |
|------|---------|
| `POST /api/v1/trade/execute` | Place paper order (alias of `/api/v1/paper/orders`) |
| `GET /api/v1/trade/positions` | Paper status / fills (alias of `/api/v1/paper/status`) |

Router order: **Kraken CLI** when present (Linux/Docker) → else **local paper ledger** (Windows without CLI). Postgres is used when available; if DB is down, orders still accept into the local ledger.

Validation commands:

- `npm run lint`
- `npm run build`
- `npm run test`
- `python -m pytest backend/tests`
- `ruff check backend`
- `mypy backend/app --ignore-missing-imports`

## Signal Routes (TradingView / MCP → paper)

Paper-only ingress for TradingView webhooks and a route-scoped MCP submit tool.
All feature flags default to **off**. Live Kraken paths are forbidden in the
`backend/app/signals` package.

| Variable | Default | Purpose |
|----------|---------|---------|
| `SIGNAL_ROUTES_ENABLED` | `false` | Global admin/ingress gate |
| `TRADINGVIEW_INGRESS_ENABLED` | `false` | Public webhook adapter |
| `MCP_SIGNAL_ADAPTER_ENABLED` | `false` | MCP submit adapter |
| `SIGNAL_WORKER_ENABLED` | `false` | Durable lease worker |
| `SIGNAL_EXECUTION_ENABLED` | `false` | Paper dispatch (shadow when false) |
| `AI_ADVISORY_ENABLED` | `false` | Production AI gate (fake allowed in dev) |
| `SIGNAL_CREDENTIAL_PEPPER` | empty | HMAC pepper for route credentials |

**Fable Engine (P1–P2):** internal Grid/DCA generators under `backend/app/signals/engine/`.
Default off + dry-run. Records intents in-memory (`dry_run_recorded`); intake/migration is P3.

| Variable | Default | Purpose |
|----------|---------|---------|
| `FABLE_ENGINE_ENABLED` | `false` | Start engine loop in API lifespan |
| `FABLE_ENGINE_DRY_RUN` | `true` | Record only (no paper submit until P3) |
| `FABLE_ENGINE_POLL_SECONDS` | `10` | Poll cadence |
| `FABLE_ENGINE_MARKET_RPM` | `30` | Token-bucket for OHLCV fetches |
| `FABLE_ENGINE_ONNX_BIAS` | `off` | Reserved for P5 |

Webhook:

```http
POST /api/v1/webhooks/tradingview/{public_route_key}
```

Ingress accepts **natural TradingView JSON** (official placeholders already expanded by TV) and normalizes it to Kraken-ready fields (`pair`, `side`, `volume`, `ordertype`, `price`) via `backend/app/signals/tv_webhook_parser.py`. Unresolved `{{placeholders}}` are rejected. Dry-run: `POST /api/v1/signals/tv-parse-preview` (signal admin).

Worker:

```powershell
$env:SIGNAL_WORKER_ENABLED = "true"
$env:KRAKEN_AUTONOMY_LEVEL = "2"
$env:KRAKEN_LIVE_TRADING_ENABLED = "false"
python -m backend.app.signals
```

## App Settings — API keys & passwords

Open **Einstellungen / Settings** in the header. The integrations panel writes to a
gitignored server vault (`backend/data/secrets/integrations.json`), applies values
into the process environment, and reloads `Settings`. List endpoints return only
configured/masked status; reveal + mutate require recent trading-admin auth.

## tvremix MCP (Pine + market tools)

Hosted client: `backend/app/integrations/tvremix_client.py`. HTTP surface:

| Endpoint | Purpose |
|----------|---------|
| `GET /api/v1/tvremix/status` | Key configured + tool list |
| `GET /api/v1/tvremix/scripts` | `pine_list_*` |
| `POST /api/v1/tvremix/search` | `pine_search_script` (+ local scan fallback) |
| `POST /api/v1/tvremix/read-lines` | `pine_read_lines` |
| `POST /api/v1/tvremix/errors` | `pine_get_errors` |
| `POST /api/v1/tvremix/strategy-report` | `get_strategy_report` |
| `POST /api/v1/tvremix/strategy-sweep` | `strategy_sweep` |
| `POST /api/v1/tvremix/mtf` | `analyze_multi_timeframe` |
| `GET/POST /api/v1/tvremix/ledger*` | Pine SHA256 change detection |

Dashboard: **Command Overview** KPIs + equity sparkline; **3D orderbook heatmap** (`three.js`) on ADAUSD.

Docker worker (profile): `docker compose --profile signals up signal-worker`

UI: main menu **Signal Routes** (shortcut `5`). Requires Firebase Auth sign-in
plus a `signal_admin` custom claim for admin APIs. Bypass switches and credential
rotation require recent auth.

## AI / TVAPI / Telegram tabs

Legacy `/api/*` routes (Vite proxies to FastAPI) power the chat, orchestrator,
TVAPI optimizer, and Telegram feed. All mutating calls require Firebase Bearer
auth (`require_user`).

| Path | Purpose |
|------|---------|
| `GET /api/ai/health` | Gemini configured? (no auth) |
| `POST /api/chat` | Gemini chat |
| `POST /api/gemini/orchestrate` | Generative plan (doctrine + prompt shots; optional status packets) |
| `POST /api/chat` | Chat; `mode: assistant\|orchestrator` + optional packets |
| `POST /api/gemini/analyze-trades` | Trade diagnostics |
| `POST /api/tvapi/optimize` | Candle OHLCV backtest (tv-extension-mvp); optional `scriptId` / `pineSource` via tvremix |
| `POST /api/tvapi/chart-strategies` | tvremix Pine list (session/saved) **+** probe catalog when `TVREMIX_API_KEY` set |
| `POST /api/tvapi/analyze-chart` | Gemini vision — **pattern only** (backtest mode rejected; use optimize) |

**tvremix Pine → Optimizer:** set `TVREMIX_API_KEY` from [tvremix account API keys](https://tvremix.xyz/account#api-keys). FastAPI calls `https://tvremix.xyz/api/mcp/v1` (same hosted MCP as Cursor). “Read chart strategies” lists your scripts when Pine tools are available for the key; selecting one passes `scriptId` into optimize (read source + parse `input.*` defaults + candle grid). Cursor MCP server `user-tvremix` should use the same Bearer key if discovery fails.

**LTM (Liquidity Trail Matrix):** bundled probe id `ltm_willy_v130` — Finn Powers / WillyAlgoTrader v1.3 precision analyzer (ATR trail bands + scored retests). Optimizer runs the Python port in `backend/app/integrations/backtest/ltm_analyzer.py`. Pine stub/full source: `assets/strategies/liquidity_trail_matrix_v1_3_0.pine` (paste complete TV script there when syncing).
| `GET/POST /api/telegram/*` | Bot config, messages, send, daemon status |

Env (see `.env.example`): `GEMINI_API_KEY`, optional `OPENROUTER_API_KEY` /
`GROQ_API_KEY` / `CEREBRAS_API_KEY`, `AI_PROVIDER_ORDER` (default
`gemini,openrouter,groq,cerebras`), `AI_CHAT_ENABLED`,
`AI_ALLOW_DETERMINISTIC_FALLBACK` (dev/tests only), `TVAPI_ENABLED`,
`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `TELEGRAM_ENABLED`. Chat/orchestrate
fail over on 429/5xx/timeout; vision (`analyze-chart`) stays Gemini-only.

Keep local trading paper-first: `KRAKEN_AUTONOMY_LEVEL=2` and
`KRAKEN_LIVE_TRADING_ENABLED=false`. If `/health/ready` reports
`live-autonomous`, fix your `.env.local` — do not commit secrets.

### Firebase Auth setup

Backend (token verification):

- `FIREBASE_PROJECT_ID`
- `GOOGLE_APPLICATION_CREDENTIALS` (path to service-account JSON), or ADC

Frontend (Vite public web configuration):

- `VITE_FIREBASE_API_KEY`
- `VITE_FIREBASE_AUTH_DOMAIN`
- `VITE_FIREBASE_PROJECT_ID`
- `VITE_FIREBASE_APP_ID`
- optional: `VITE_FIREBASE_MESSAGING_SENDER_ID`, `VITE_FIREBASE_STORAGE_BUCKET`

In Firebase Console, open **Authentication > Sign-in method**, enable **Google**,
select the support email, and add each deployed hostname under **Authorized
domains**. Use hostnames only (for example `localhost`), without protocol or port.
The frontend and backend project IDs must refer to the same Firebase project.

The browser uses Firebase's popup flow and session-scoped persistence. It sends
only short-lived Firebase ID tokens to the API as `Authorization: Bearer ...`;
manual pasted-token login is disabled. For Docker builds, Compose forwards the
public `VITE_FIREBASE_*` values as build arguments because Vite embeds them at
build time. Never pass service-account JSON or private keys to the web image.

For a local Docker API, keep the service-account JSON outside the repository and
start Compose with the read-only Firebase credential overlay:

```powershell
$env:FIREBASE_CREDENTIALS_HOST_PATH = "C:\secure\firebase-service-account.json"
docker compose -f docker-compose.yml -f docker-compose.firebase.yml up --build
```

On managed Google infrastructure, omit the overlay and use deployment-native
Application Default Credentials instead.

Grant Signal Routes administrators the custom claim `signal_admin: true`. Grant
live safety-control operators `trading_admin: true`. After changing claims, the
user must sign out and sign in again so Firebase issues a token containing the
updated claim.

Incident shutdown: set `SIGNAL_EXECUTION_ENABLED=false`, disable routes, revoke
credentials, stop the worker, preserve audit/event rows, reconcile any
`execution_unknown` records.

## Kraken autonomy Level 4

Defaults stay safe: `KRAKEN_AUTONOMY_LEVEL=2` and `KRAKEN_LIVE_TRADING_ENABLED=false`.

### Capital policy (hard rules)

- **No external replenish:** CLI deposit / withdraw / transfer / funding / earn paths are blocked in-process. The bot cannot top up from outside Kraken.
- **No debt / no below $0:** Live buys must fit available cash (USD/EUR/stables including `ZEUR`); sells cannot exceed held inventory (no shorts). Leverage &gt; 1 and non-reduce-only futures opens are rejected.
- **Max notional:** `KRAKEN_MAX_NOTIONAL` (default `2`) caps quote size per live trade for small accounts.
- **Supervised-first:** Manual Positions live desk can work with live trading on; unattended **Live algo** switch also needs `KRAKEN_LIVE_ALGO_ENABLED=true`.
- **Kill switch:** `POST /api/v1/loops/kill` (header **Kill**) stops loops and attempts cancel-all. Audit: `backend/data/trading/live_audit.jsonl`.
- **Status memory:** Full https://status.kraken.com component list is stored in `backend/data/kraken/status_components.json` (index: `status_index.json`). Live orders refuse if REST/Websocket/Kraken API or the pair’s asset component is degraded. Refresh: `POST /api/v1/kraken/status/refresh`. Agents use `.cursor/rules/kraken-status-memory.mdc`.

### Global UI switches (header)

Always-visible controls in the app header:

| Switch | Behavior |
|--------|----------|
| **Paper loop** | `POST /api/v1/loops/paper/start\|stop` — starts/stops the in-process FableEngine paper path |
| **Live algo** | `POST /api/v1/loops/live/start\|stop` — arms deadman + live session loop **only if** env gates already allow Level 4 |

The Live switch never flips `KRAKEN_LIVE_TRADING_ENABLED` from the browser. If gates are off it shows **Blocked** with the reason.

Status: `GET /api/v1/loops/status`

### Trade Agent (scheduled runtime)

Bridges the Fable5 TradeAgent schedule model into Neo (paper-first):

| Piece | Neo path |
|-------|----------|
| Scheduler + watchdog | `backend/app/trading/trade_agent/` |
| API | `GET/POST /api/v1/trade-agent/{status,start,stop,trigger/{job_id}}` |
| CLI | `python -m backend.scripts.run_trade_agent {status\|market\|pre-market\|label\|optimize\|positions\|background}` |
| Windows Task Scheduler bats | `scripts/schedule_*.bat` (morning / preopen / market / label / optimizer) |
| Register tasks | `powershell -ExecutionPolicy Bypass -File .\scripts\setup_scheduled_tasks.ps1` (−`IncludeOptimizer` optional) |

Slots include Berlin market scans + ET entry windows from `EVENT_DRIVEN_TRADING.md`, nightly GA optimizer, and 5‑minute positions watchdog. Enable in-API scheduler with `TRADE_AGENT_ENABLED=true` (optional `TRADE_AGENT_AUTO_START=true`). Scheduled scans use tvremix by default (`TRADE_AGENT_SCHEDULED_MARKET_SOURCE=tvremix`), while the continuous FableEngine loop should use `FABLE_ENGINE_CANDLE_SOURCE=ccxt`. TradingView alerts arrive through the webhook/ngrok path and are not polled. Scans drive **FableEngine dry-run** — they do not place live orders.

Windows Task Scheduler (Berlin wall clock, same as Fable5 TradeAgent):

| Time | Task | Bat |
|------|------|-----|
| 07:00 | Morning pre-market | `schedule_morning_scan.bat` |
| 15:00 | Pre-open (~09:00 ET) | `schedule_preopen_scan.bat` |
| 16:00 | Market hours (~10:00 ET) | `schedule_market_scan.bat` |
| 18:00 | ML trade labeling | `schedule_label_trades.bat` |
| 02:30 | GA optimizer (opt-in `-IncludeOptimizer`) | `schedule_optimizer.bat` |

Remove tasks: `powershell -File .\scripts\setup_scheduled_tasks.ps1 -UnregisterOnly`

Windows Task Scheduler (Berlin wall clock, same as Fable5 TradeAgent):

| Time | Task | Bat |
|------|------|-----|
| 07:00 | Morning pre-market | `schedule_morning_scan.bat` |
| 15:00 | Pre-open (~09:00 ET) | `schedule_preopen_scan.bat` |
| 16:00 | Market hours (~10:00 ET) | `schedule_market_scan.bat` |
| 18:00 | ML trade labeling | `schedule_label_trades.bat` |
| 02:30 | GA optimizer (opt-in) | `schedule_optimizer.bat` |

### Positions control desk

Positions tab can open/close (including partial + limit close), cancel / cancel-all / amend live orders, and place protective SL / TP / trailing stops. Order types mirror Kraken spot (`market`, `limit`, `stop-loss`, `stop-loss-limit`, `take-profit`, `take-profit-limit`, `trailing-stop`, `trailing-stop-limit`) plus futures place/edit/cancel via `/api/v1/orders*`. Manual live actions require autonomy ≥ 3 and live trading enabled; the algo loop still requires autonomy ≥ 4.

Guardrail env vars (enforced in agent code, not by the CLI):

| Variable | Default | Purpose |
|----------|---------|---------|
| `KRAKEN_MAX_ORDER_SIZE` | `0.01` | Max volume per order |
| `KRAKEN_MAX_OPEN_POSITIONS` | `3` | Cap concurrent open orders/positions |
| `KRAKEN_MAX_TRADES_PER_HOUR` | `10` | Frequency limit |
| `KRAKEN_MIN_TRADE_INTERVAL_SECONDS` | `30` | Min seconds between new trades |
| `KRAKEN_PAIR_ALLOWLIST` | `ADAUSD,XRPUSD` | Only these pairs |
| `KRAKEN_DEADMAN_SECONDS` | `600` | Auto-cancel open orders if agent dies |

API:

- `GET /api/v1/trading/autonomy` — current level + guardrails
- `GET /api/v1/trading/preflight` — credential/pair checks
- `GET /api/v1/trading/monitor` — Level 1 balance/open-orders snapshot
- `POST /api/v1/trading/deadman` — arm cancel-after (auth + Level 4 gates)

Session scripts (Windows):

```powershell
# 1. Preflight (does not arm deadman unless -LiveEnabled)
.\scripts\kraken-level4-preflight.ps1

# 2. When going live at Level 4
$env:KRAKEN_AUTONOMY_LEVEL = "4"
$env:KRAKEN_LIVE_TRADING_ENABLED = "true"
.\scripts\kraken-level4-preflight.ps1 -LiveEnabled
.\scripts\kraken-deadman-refresh.ps1 -Loop
.\scripts\kraken-level1-monitor.ps1
```

Use a trade-only API key (never enable Withdraw Funds). Promote only after a week of stable Level 3 supervised trading.
