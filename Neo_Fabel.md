# Neo Fabel — AI Trading & Signal Ecosystem

## 1. Projektübersicht & Vision

**Neo Fabel** ist ein hochentwickeltes, AI-gestütztes Trading- und Signal-Ökosystem für automatisierte Marktanalysen, Signal-Generierung und regelbasierte Orderausführung auf Kryptowährungsmärkten (insbesondere Kraken Spot).

Das System kombiniert deterministische Sicherheits-Policy-Gates, neurales Pattern-Matching (ONNX Neural Core), kontinuierliches Lernen (Academy Training Loop), Backtesting (Chronos Engine) sowie autonome Aufgaben-Steuerung nach Google ADK Standards (ADK Task Scheduler).

---

## 2. Systemarchitektur & Komponenten

```
                               ┌─────────────────────────────────────────┐
                               │            React / Vite UI              │
                               │  (Dashboards, Signal Routes, Autonomy)  │
                               └────────────────────┬────────────────────┘
                                                    │ REST / WebSocket
                                                    ▼
┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                       FastAPI Backend (App Core)                                       │
│                                                                                                        │
│  ┌───────────────────────┐   ┌───────────────────────┐   ┌───────────────────────┐                    │
│  │   Trading Autonomy    │   │   Signal Pipeline     │   │   ADK Task Scheduler  │                    │
│  │   (Level 1 - 4 Session)│   │  (Lease-Worker/Gates) │   │  (Scheduled Agent)    │                    │
│  └───────────┬───────────┘   └───────────┬───────────┘   └───────────┬───────────┘                    │
└──────────────┼───────────────────────────┼───────────────────────────┼────────────────────────────────┘
               │                           │                           │
               ▼                           ▼                           ▼
┌──────────────────────────────┐ ┌───────────────────┐ ┌────────────────────────────────────────────────┐
│   Kraken CLI / REST API      │ │ PostgreSQL DB     │ │ Qdrant Vector Store                            │
│  (Spot Trading & Deadman)    │ │ (Signals/Leases)  │ │ (Pattern & RNA Bias Embeddings)                │
└──────────────────────────────┘ └───────────────────┘ └────────────────────────────────────────────────┘
```

### 2.1 Backend (Python 3.11 / FastAPI)
- **FastAPI Core (`backend/app/main.py`)**: Asynchrone REST API mit modularer Lifespan-Steuerung, CORS-Schutz, Request ID Tracking und Dependency Injection.
- **Datenbank & Persistenz (`backend/app/database.py`)**: Async SQLAlchemy 2.0 ORM gekoppelt mit PostgreSQL (`neo_fabel` DB) und Alembic-Migrationen.
- **Operator Vault (`backend/app/integrations/secrets_store.py`)**: Sichere Schlüsselverwaltung in `backend/data/secrets/integrations.json`.

### 2.2 Signal Pipeline & Engine
- **Webhook Ingress (`backend/app/signals/router.py`)**: Sichere Annahme von TradingView-Webhooks (`/api/v1/webhooks/tradingview/{public_route_key}`).
- **Deterministische Policy Gates (`backend/app/signals/policy.py`)**: Automatische Validierung von Preisen, Timestamps, Pair-Allowlists und Risikogrenzen.
- **Fable Engine (`backend/app/signals/engine/`)**: Grid- und DCA-Signalgenerator mit dynamischem RNA-Pattern Bias (`rna_context.py`).
- **State Machine (`backend/app/signals/domain.py`)**: Haltbare Signalzustände (`RECEIVED`, `LEASED`, `EVALUATED`, `EXECUTED`, `REJECTED`, `EXPIRED`).

### 2.3 Trading Autonomy & Execution Engine (`backend/app/trading/`)
- **Autonomie-Level 1–4**:
  - **Level 1**: Reader/Monitor (Nur Balance- und Orderbuch-Anzeige).
  - **Level 2**: Paper Trading (Simulierte Order-Ausführung).
  - **Level 3**: Supervised Live (Menschliche Freigabe erforderlich).
  - **Level 4**: Autonomous Live (Automatische Live-Orderausführung mit Deadman Switch & Guardrails).
- **Deadman Switch (`kraken-deadman-refresh.ps1`)**: Automatischer Schutzschalter; stoppt den Live-Handel sofort, falls das System nicht alle 600 Sekunden ein Heartbeat-Signal erhält.
- **Capital & Risk Policy (`backend/app/trading/session.py`)**: Erzwingt strikte Limits: Zero Leverage, keine Ein-/Auszahlungen, maximale Notional Limit per Trade (`KRAKEN_MAX_NOTIONAL=2.5`), maximale Order-Größe (`KRAKEN_MAX_ORDER_SIZE=10`).

### 2.4 Google ADK Task Scheduler (`backend/app/trading/adk_scheduler.py`)
- **ADK Task Scheduler Manager**: In-Memory Async Scheduler zur Ausführung von Agenten-Aufgaben via Intervall, Cron-Syntax (5-Field `croniter`) oder dynamischen Bedingungs-Triggern.
- **Scheduled Agent (`backend/app/academy/adk_scheduled_agent.py`)**: Agent nach Google ADK Architektur-Muster für selbstständig aufwachende Aufgaben und automatische Zyklus-Erfassung.

### 2.5 Frontend (React / Vite)
- **Moderne Benutzeroberfläche (`src/`)**: Responsives Dashboard für Signal-Routen, ONNX Neural Analytics, Chronos Backtesting, Academy Training Loops und Realtime Trading-Status.

---

## 3. Sicherheits- & Guardrail-Konfiguration

Neo Fabel verwendet ein mehrstufiges Sicherheitssystem gegen unerwünschte Transaktionen:

1. **Trade-Only Kraken Key**: Kraken API Schlüssel besitzt ausschließlich Handelsrechte (`Query Funds`, `Modify Orders`). Abhebungen/Transfers sind API-seitig gesperrt.
2. **Double Live Flag Requirement**: Live-Orders werden erst ausgeführt, wenn sowohl `KRAKEN_AUTONOMY_LEVEL=4` als auch `KRAKEN_LIVE_TRADING_ENABLED=true` in der `.env` gesetzt sind.
3. **Pair Allowlist**: Nur explizit freigegebene Handelspaare (`ADAUSD`, `XRPUSD`, `ADAEUR`, `XRPEUR`) dürfen gehandelt werden.
4. **Max Order & Notional Caps**:
   - `KRAKEN_MAX_NOTIONAL = 2.5` (€/$)
   - `KRAKEN_MAX_ORDER_SIZE = 10`
   - `KRAKEN_MAX_OPEN_POSITIONS = 20`

---

## 4. Wichtige API-Endpunkte

| Methode | Endpunkt | Beschreibung |
|---|---|---|
| `GET` | `/health/live` | Health Check des Servers |
| `GET` | `/api/v1/trading/autonomy` | Status der Autonomie-Stufe & Guardrails |
| `POST` | `/api/v1/trading/deadman` | Heartbeat / Deadman Switch auffrischen |
| `POST` | `/api/v1/trading/order/spot` | Live Spot Order Platzierung (Level 4 erforderlich) |
| `GET` | `/api/v1/trading/scheduler` | Status des ADK Task Schedulers & aktiver Aufgaben |
| `POST` | `/api/v1/webhooks/tradingview/{public_route_key}` | Ingress für TradingView Webhook Signale |
| `GET` | `/api/v1/signal-automation/status` | Status der Signal Pipeline & Lease-Worker |

---

## 5. Betrieb & Systemstart

### 5.1 Server starten (Powershell Host Script)
```powershell
.\scripts\start-server.ps1
```

### 5.2 Server stoppen
```powershell
.\scripts\stop-server.ps1
```

### 5.3 Webhook Tunnel für TradingView starten (Ngrok)
```powershell
ngrok http 8000 --domain=lesa-ionospheric-affably.ngrok-free.dev
```

### 5.4 Automated Test Suite ausführen
```powershell
pytest backend/tests/test_signal_routes_functional_smoke.py backend/tests/test_adk_scheduler.py
```

---

*Zuletzt aktualisiert: 2026-07-28*
