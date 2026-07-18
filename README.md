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

Market-data endpoints:

- `GET /api/v1/market/batch?asset_class=all` queries the curated common crypto, FX, and S&P 500 universe. Crypto uses the Kraken CLI; FX and equities use Alpha Vantage.
- `GET /api/v1/market/ohlcv?asset_class=sp500&symbols=AAPL,MSFT&intervals=1min,5min,15min,60min,4h` requests OHLCV bars. Alpha Vantage's 60-minute data is deterministically aggregated into 4-hour bars. Missing provider entitlements are returned per item as explicit errors.

Set `ALPHAVANTAGE_API_KEY` (or `ALPHA_VANTAGE_API_KEY`) in `.env.local`. Full equity batches use Alpha Vantage's bulk quote entitlement, so set `ALPHAVANTAGE_BULK_QUOTES_ENABLED=true` only when that entitlement is available. Intraday equity and crypto endpoints may also require a premium Alpha Vantage plan; the API never substitutes mock data.

Docker path:

- `docker compose --env-file .env.local up --build`
- Apply migrations from the API image: `docker compose run --rm api alembic -c backend/alembic.ini upgrade head`

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

Webhook:

```http
POST /api/v1/webhooks/tradingview/{public_route_key}
```

Worker:

```powershell
$env:SIGNAL_WORKER_ENABLED = "true"
$env:KRAKEN_AUTONOMY_LEVEL = "2"
$env:KRAKEN_LIVE_TRADING_ENABLED = "false"
python -m backend.app.signals
```

Docker worker (profile): `docker compose --profile signals up signal-worker`

UI: main menu **Signal Routes** (shortcut `5`). Requires Firebase Auth sign-in
plus a `signal_admin` custom claim for admin APIs. Bypass switches and credential
rotation require recent auth.

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

Guardrail env vars (enforced in agent code, not by the CLI):

| Variable | Default | Purpose |
|----------|---------|---------|
| `KRAKEN_MAX_ORDER_SIZE` | `0.01` | Max volume per order |
| `KRAKEN_MAX_OPEN_POSITIONS` | `3` | Cap concurrent open orders/positions |
| `KRAKEN_MAX_TRADES_PER_HOUR` | `10` | Frequency limit |
| `KRAKEN_PAIR_ALLOWLIST` | `BTCUSD,ETHUSD` | Only these pairs |
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
