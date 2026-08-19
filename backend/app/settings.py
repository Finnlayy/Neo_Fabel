import urllib.parse
from decimal import Decimal
from functools import lru_cache

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from .trading.autonomy import AutonomyLevel
from .trading.guardrails import TradeRateLimiter, TradingGuardrails


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env.local", extra="ignore", populate_by_name=True)

    app_name: str = "neo-fabel-api"
    app_env: str = Field(default="development", validation_alias="APP_ENV")
    allowed_origins: str = Field(default="http://localhost:5173", validation_alias="ALLOWED_ORIGINS")
    database_url: str = Field(
        default="postgresql+asyncpg://fable:fable@localhost:5432/fable",
        validation_alias="DATABASE_URL",
    )
    kraken_binary: str = Field(default="kraken", validation_alias="KRAKEN_BINARY")
    kraken_timeout_seconds: float = Field(default=15.0, validation_alias="KRAKEN_TIMEOUT_SECONDS")
    # Autonomy: 1 read-only, 2 paper, 3 supervised, 4 autonomous, 5 fund management.
    # Live order placement also requires KRAKEN_LIVE_TRADING_ENABLED=true.
    kraken_autonomy_level: int = Field(default=2, validation_alias="KRAKEN_AUTONOMY_LEVEL")
    kraken_live_trading_enabled: bool = Field(default=False, validation_alias="KRAKEN_LIVE_TRADING_ENABLED")
    kraken_deadman_seconds: int = Field(default=600, validation_alias="KRAKEN_DEADMAN_SECONDS")
    kraken_max_order_size: Decimal = Field(default=Decimal("0.01"), validation_alias="KRAKEN_MAX_ORDER_SIZE")
    # Max quote notional per live trade (EUR/USD treated as account cash units). Tiny accounts: ~2.
    kraken_max_notional: Decimal = Field(default=Decimal(2), validation_alias="KRAKEN_MAX_NOTIONAL")
    kraken_max_open_positions: int = Field(default=3, validation_alias="KRAKEN_MAX_OPEN_POSITIONS")
    kraken_max_trades_per_hour: int = Field(default=10, validation_alias="KRAKEN_MAX_TRADES_PER_HOUR")
    kraken_min_trade_interval_seconds: float = Field(
        default=30.0, validation_alias="KRAKEN_MIN_TRADE_INTERVAL_SECONDS", ge=0.0
    )
    kraken_pair_allowlist: str = Field(
        default="ADAUSD,XRPUSD,ADAEUR,XRPEUR", validation_alias="KRAKEN_PAIR_ALLOWLIST"
    )
    # Paper trades ignore the live allowlist and accept any symbol (manual + signal routes).
    paper_allow_all_pairs: bool = Field(default=True, validation_alias="PAPER_ALLOW_ALL_PAIRS")
    # Unattended live algo loop (header switch). Manual live desk can work with live=true + autonomy>=3
    # while this stays false (supervised-first).
    kraken_live_algo_enabled: bool = Field(default=False, validation_alias="KRAKEN_LIVE_ALGO_ENABLED")
    firebase_project_id: str | None = Field(default=None, validation_alias="FIREBASE_PROJECT_ID")
    firebase_credentials_path: str | None = Field(
        default=None, validation_alias=AliasChoices("GOOGLE_APPLICATION_CREDENTIALS", "FIREBASE_CREDENTIALS_PATH")
    )
    # Local-only: allow loopback API calls without Firebase when credentials are missing.
    # Forced off outside development. Never enable in production.
    auth_dev_bypass: bool = Field(default=True, validation_alias="AUTH_DEV_BYPASS")
    # Paper ledger without Kraken CLI (False = direct to Kraken CLI).
    paper_local_ledger: bool = Field(default=False, validation_alias="PAPER_LOCAL_LEDGER")
    paper_max_open_positions: int = Field(
        default=20,
        ge=1,
        le=100,
        validation_alias="PAPER_MAX_OPEN_POSITIONS",
    )
    # Symbols the paper engine scans for opportunities (defaults to MARKET_STREAM_SYMBOLS).
    paper_opportunity_symbols: str = Field(
        default="",
        validation_alias="PAPER_OPPORTUNITY_SYMBOLS",
    )
    paper_starting_balance_usd: Decimal = Field(default=Decimal(10000), validation_alias="PAPER_STARTING_BALANCE_USD")
    paper_futures_starting_margin_usd: Decimal = Field(
        default=Decimal(10000), validation_alias="PAPER_FUTURES_STARTING_MARGIN_USD"
    )
    paper_default_market: str = Field(default="spot", validation_alias="PAPER_DEFAULT_MARKET")
    paper_maker_fee_rate: Decimal = Field(default=Decimal(0), validation_alias="PAPER_MAKER_FEE_RATE")
    paper_taker_fee_rate: Decimal = Field(default=Decimal("0.0005"), validation_alias="PAPER_TAKER_FEE_RATE")
    paper_kelly_sizing_enabled: bool = Field(default=True, validation_alias="PAPER_KELLY_SIZING_ENABLED")
    paper_kelly_mode: str = Field(default="half_kelly", validation_alias="PAPER_KELLY_MODE")
    # Dynamic paper-trade position sizing — risk-managed per-trade notional.
    # PAPER_SIZING_MODE: dynamic_kelly | half_kelly | full_kelly | ai_chronos | fixed_usd | manual
    paper_sizing_mode: str = Field(default="dynamic_kelly", validation_alias="PAPER_SIZING_MODE")
    # Max notional as a fraction of paper capital (1.5 % default = 0.015).
    # Replaces fixed PAPER_MAX_NOTIONAL_USD — cap now scales with account size.
    paper_max_notional_pct: float = Field(default=0.015, ge=0.001, le=0.25, validation_alias="PAPER_MAX_NOTIONAL_PCT")
    # Kelly risk fraction band per paper trade.
    paper_max_risk_fraction: float = Field(default=0.05, ge=0.005, le=0.25, validation_alias="PAPER_MAX_RISK_FRACTION")
    paper_min_risk_fraction: float = Field(default=0.015, ge=0.001, le=0.10, validation_alias="PAPER_MIN_RISK_FRACTION")
    alphavantage_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("ALPHAVANTAGE_API_KEY", "ALPHA_VANTAGE_API_KEY"),
    )
    alphavantage_base_url: str = Field(
        default="https://www.alphavantage.co/query", validation_alias="ALPHAVANTAGE_BASE_URL"
    )
    alphavantage_timeout_seconds: float = Field(default=15.0, validation_alias="ALPHAVANTAGE_TIMEOUT_SECONDS")
    alphavantage_bulk_quotes_enabled: bool = Field(
        default=False, validation_alias="ALPHAVANTAGE_BULK_QUOTES_ENABLED"
    )
    alphavantage_batch_concurrency: int = Field(default=2, validation_alias="ALPHAVANTAGE_BATCH_CONCURRENCY")

    # Signal Routes — all disabled by default (paper-only when enabled).
    signal_routes_enabled: bool = Field(default=False, validation_alias="SIGNAL_ROUTES_ENABLED")
    tradingview_ingress_enabled: bool = Field(default=False, validation_alias="TRADINGVIEW_INGRESS_ENABLED")
    mcp_signal_adapter_enabled: bool = Field(default=False, validation_alias="MCP_SIGNAL_ADAPTER_ENABLED")
    # Rust fable-mcp → LocalPaperLedger HTTP bridge (paper-only; never live).
    fable_mcp_bridge_enabled: bool = Field(default=False, validation_alias="FABLE_MCP_BRIDGE_ENABLED")
    fable_mcp_bridge_token: str = Field(default="", validation_alias="FABLE_MCP_BRIDGE_TOKEN")
    signal_worker_enabled: bool = Field(default=False, validation_alias="SIGNAL_WORKER_ENABLED")
    signal_execution_enabled: bool = Field(default=False, validation_alias="SIGNAL_EXECUTION_ENABLED")
    ai_advisory_enabled: bool = Field(default=False, validation_alias="AI_ADVISORY_ENABLED")
    signal_credential_pepper: str = Field(default="", validation_alias="SIGNAL_CREDENTIAL_PEPPER")
    signal_max_body_bytes: int = Field(default=16384, validation_alias="SIGNAL_MAX_BODY_BYTES")
    signal_max_age_seconds: int = Field(default=300, validation_alias="SIGNAL_MAX_AGE_SECONDS")
    signal_future_skew_seconds: int = Field(default=30, validation_alias="SIGNAL_FUTURE_SKEW_SECONDS")
    signal_worker_poll_seconds: float = Field(default=1.0, validation_alias="SIGNAL_WORKER_POLL_SECONDS")
    signal_worker_lease_seconds: int = Field(default=30, validation_alias="SIGNAL_WORKER_LEASE_SECONDS")
    signal_recent_auth_seconds: int = Field(default=300, validation_alias="SIGNAL_RECENT_AUTH_SECONDS")
    advisory_provider: str = Field(default="fake", validation_alias="ADVISORY_PROVIDER")
    advisory_model: str = Field(default="deterministic-fake-v1", validation_alias="ADVISORY_MODEL")
    advisory_timeout_seconds: float = Field(default=5.0, validation_alias="ADVISORY_TIMEOUT_SECONDS")
    advisory_prompt_version: str = Field(default="v1", validation_alias="ADVISORY_PROMPT_VERSION")
    signal_policy_version: str = Field(default="v1", validation_alias="SIGNAL_POLICY_VERSION")

    # AI chat / orchestrate / vision (multi-provider router; Gemini + OpenAI-compatible).
    gemini_api_key: str | None = Field(default=None, validation_alias="GEMINI_API_KEY")
    ai_chat_enabled: bool = Field(default=True, validation_alias="AI_CHAT_ENABLED")
    ai_allow_deterministic_fallback: bool = Field(
        default=False, validation_alias="AI_ALLOW_DETERMINISTIC_FALLBACK"
    )
    # Ordered failover: free/local first; aiprimetech is paid (€/day budget).
    ai_provider_order: str = Field(
        default="gemini,openrouter,groq,cerebras,aiprimetech",
        validation_alias="AI_PROVIDER_ORDER",
    )
    # When true, rotate the starting provider among the configured chain (still fail over in order).
    ai_provider_rotate: bool = Field(default=False, validation_alias="AI_PROVIDER_ROTATE")
    orchestrator_advisory_enabled: bool = Field(
        default=False,
        validation_alias="ORCHESTRATOR_ADVISORY_ENABLED",
    )
    gemini_timeout_seconds: float = Field(default=45.0, validation_alias="GEMINI_TIMEOUT_SECONDS")
    ai_llm_timeout_seconds: float = Field(default=45.0, validation_alias="AI_LLM_TIMEOUT_SECONDS")
    # gemini-2.0-* / 2.5-* are legacy; Interactions API current default is 3.5 Flash.
    gemini_default_model: str = Field(default="gemini-3.5-flash", validation_alias="GEMINI_DEFAULT_MODEL")
    # Free OpenRouter model ids from cheahjs/free-llm-api-resources (:free suffix).
    openrouter_default_model: str = Field(
        default="qwen/qwen3-coder:free",
        validation_alias="OPENROUTER_DEFAULT_MODEL",
    )
    groq_api_key: str | None = Field(default=None, validation_alias="GROQ_API_KEY")
    groq_default_model: str = Field(
        default="llama-3.1-8b-instant",
        validation_alias="GROQ_DEFAULT_MODEL",
    )
    cerebras_api_key: str | None = Field(default=None, validation_alias="CEREBRAS_API_KEY")
    cerebras_default_model: str = Field(
        default="llama3.1-8b",
        validation_alias="CEREBRAS_DEFAULT_MODEL",
    )
    # AIPrimeTech OpenAI-compatible gateway (https://aiprimetech.io/v1) — paid; €1/day default cap.
    aiprimetech_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("AIPRIMETECH_API_KEY", "OPENAI_API_KEY"),
    )
    aiprimetech_base_url: str = Field(
        default="https://aiprimetech.io/v1",
        validation_alias="AIPRIMETECH_BASE_URL",
    )
    aiprimetech_default_model: str = Field(
        default="gpt-5.4-mini",
        validation_alias="AIPRIMETECH_DEFAULT_MODEL",
    )
    aiprimetech_daily_budget_eur: float = Field(
        default=1.0,
        validation_alias="AIPRIMETECH_DAILY_BUDGET_EUR",
        ge=0.0,
        le=1000.0,
    )
    aiprimetech_eur_per_1m_input: float | None = Field(
        default=None,
        validation_alias="AIPRIMETECH_EUR_PER_1M_INPUT",
    )
    aiprimetech_eur_per_1m_output: float | None = Field(
        default=None,
        validation_alias="AIPRIMETECH_EUR_PER_1M_OUTPUT",
    )
    # OpenCode CLI config (opencode.json) — key always from env, never committed.
    opencode_config_write: bool = Field(default=False, validation_alias="OPENCODE_CONFIG_WRITE")
    opencode_config_path: str = Field(default="opencode.json", validation_alias="OPENCODE_CONFIG_PATH")
    # Chat wire budget (display history may be longer; server trims before LLM).
    ai_chat_max_messages: int = Field(default=12, validation_alias="AI_CHAT_MAX_MESSAGES")
    ai_chat_max_chars: int = Field(default=12_000, validation_alias="AI_CHAT_MAX_CHARS")
    ai_chat_max_content_chars: int = Field(default=4_000, validation_alias="AI_CHAT_MAX_CONTENT_CHARS")

    # TVAPI / chart optimize (RapidAPI optional; candle backtest + tvremix Pine read).
    tradingview_rapidapi_key: str | None = Field(default=None, validation_alias="TRADINGVIEW_RAPIDAPI_KEY")
    tvapi_enabled: bool = Field(default=True, validation_alias="TVAPI_ENABLED")
    tvremix_api_key: str | None = Field(default=None, validation_alias="TVREMIX_API_KEY")
    tvremix_mcp_url: str = Field(
        default="https://tvremix.xyz/api/mcp/v1",
        validation_alias="TVREMIX_MCP_URL",
    )
    tvremix_timeout_seconds: float = Field(default=45.0, validation_alias="TVREMIX_TIMEOUT_SECONDS")
    tvremix_enabled: bool = Field(default=True, validation_alias="TVREMIX_ENABLED")

    # Phase 1 — Qdrant vector index (paper/dev; no live trading).
    qdrant_enabled: bool = Field(default=True, validation_alias="QDRANT_ENABLED")
    qdrant_url: str = Field(default="http://localhost:6333", validation_alias="QDRANT_URL")
    qdrant_api_key: str | None = Field(default=None, validation_alias="QDRANT_API_KEY")
    qdrant_collection: str = Field(default="neo_fabel_vectors", validation_alias="QDRANT_COLLECTION")
    qdrant_vector_size: int = Field(default=8, validation_alias="QDRANT_VECTOR_SIZE")
    qdrant_timeout_seconds: float = Field(default=10.0, validation_alias="QDRANT_TIMEOUT_SECONDS")

    # Academy / training loop (synthetic drills only; never places live orders).
    # Default off: manual /train/cycle still works; background loop requires explicit enable.
    training_loop_enabled: bool = Field(default=False, validation_alias="TRAINING_LOOP_ENABLED")
    training_loop_auto_start: bool = Field(default=False, validation_alias="TRAINING_LOOP_AUTO_START")
    training_loop_night_mode: bool = Field(default=True, validation_alias="TRAINING_LOOP_NIGHT_MODE")
    training_loop_night_start: str = Field(default="22:00", validation_alias="TRAINING_LOOP_NIGHT_START")
    training_loop_night_end: str = Field(default="06:00", validation_alias="TRAINING_LOOP_NIGHT_END")
    training_loop_drills_per_hour: float = Field(
        default=12.0, validation_alias="TRAINING_LOOP_DRILLS_PER_HOUR"
    )
    # When false (default), Academy drills use offline fixtures — training loop never needs network.
    academy_drill_live_data: bool = Field(default=False, validation_alias="ACADEMY_DRILL_LIVE_DATA")
    # Auto-train only agents on the trading path (exclude orchestrator / briefing roles).
    academy_train_trading_only: bool = Field(default=True, validation_alias="ACADEMY_TRAIN_TRADING_ONLY")

    # Fable Engine — internal Grid/DCA signal generators (dry-run default; paper-only).
    fable_engine_enabled: bool = Field(default=False, validation_alias="FABLE_ENGINE_ENABLED")
    fable_engine_dry_run: bool = Field(default=True, validation_alias="FABLE_ENGINE_DRY_RUN")
    fable_engine_poll_seconds: float = Field(default=10.0, validation_alias="FABLE_ENGINE_POLL_SECONDS")
    fable_engine_market_rpm: float = Field(default=30.0, validation_alias="FABLE_ENGINE_MARKET_RPM")
    fable_engine_onnx_bias: str = Field(default="off", validation_alias="FABLE_ENGINE_ONNX_BIAS")
    # Candle source: auto = tvremix when TVREMIX_API_KEY is set, else ccxt.
    fable_engine_candle_source: str = Field(
        default="auto", validation_alias="FABLE_ENGINE_CANDLE_SOURCE"
    )
    fable_engine_interval: str = Field(default="5m", validation_alias="FABLE_ENGINE_INTERVAL")

    # Trade Agent — scheduled scans / labeling / optimizer (paper-first; from Fable5 TradeAgent).
    trade_agent_enabled: bool = Field(default=False, validation_alias="TRADE_AGENT_ENABLED")
    trade_agent_auto_start: bool = Field(default=False, validation_alias="TRADE_AGENT_AUTO_START")
    trade_agent_scheduled_market_source: str = Field(
        default="tvremix", validation_alias="TRADE_AGENT_SCHEDULED_MARKET_SOURCE"
    )
    trade_agent_watchdog_enabled: bool = Field(default=True, validation_alias="TRADE_AGENT_WATCHDOG_ENABLED")
    trade_agent_watchdog_seconds: int = Field(
        default=300, validation_alias="TRADE_AGENT_WATCHDOG_SECONDS", ge=60, le=3600
    )

    # Idle-market feedback / error guard (paper-first coaching + light param nudges).
    feedback_engine_enabled: bool = Field(default=True, validation_alias="FEEDBACK_ENGINE_ENABLED")

    # Genetic forward optimizer (paper research; no live orders).
    ga_optimizer_enabled: bool = Field(default=True, validation_alias="GA_OPTIMIZER_ENABLED")
    ga_data_dir: str | None = Field(default=None, validation_alias="GA_DATA_DIR")
    ga_cache_dir: str | None = Field(default=None, validation_alias="GA_CACHE_DIR")
    ga_default_population: int = Field(default=30, validation_alias="GA_DEFAULT_POPULATION", ge=2, le=200)
    ga_default_generations: int = Field(default=50, validation_alias="GA_DEFAULT_GENERATIONS", ge=1, le=500)
    ga_max_symbols: int = Field(default=40, validation_alias="GA_MAX_SYMBOLS", ge=0, le=500)
    ga_lookback_bars: int = Field(default=600, validation_alias="GA_LOOKBACK_BARS", ge=150, le=5000)
    ga_train_ratio: float = Field(default=0.70, validation_alias="GA_TRAIN_RATIO", gt=0.1, lt=0.95)
    ga_fee_r: float = Field(default=0.03, validation_alias="GA_FEE_R", ge=0.0, le=1.0)
    ga_max_concurrent_jobs: int = Field(default=1, validation_alias="GA_MAX_CONCURRENT_JOBS", ge=1, le=4)
    ga_market_source: str = Field(default="cache", validation_alias="GA_MARKET_SOURCE")

    # Phase 2 — CCXT + WebSocket market stream (read-only; no live trading).
    market_stream_enabled: bool = Field(default=True, validation_alias="MARKET_STREAM_ENABLED")
    market_ccxt_enabled: bool = Field(default=True, validation_alias="MARKET_CCXT_ENABLED")
    market_ccxt_exchange: str = Field(default="kraken", validation_alias="MARKET_CCXT_EXCHANGE")
    market_stream_interval_seconds: float = Field(
        default=5.0, validation_alias="MARKET_STREAM_INTERVAL_SECONDS"
    )
    market_stream_symbols: str = Field(
        default="BTC/USD,ETH/USD,SOL/USD,XRP/USD,ADA/USD,AVAX/USD,DOT/USD,POL/USD",
        validation_alias="MARKET_STREAM_SYMBOLS",
    )

    # Telegram bot feed — primary chat defaults to Manus (MANUS_TELEGRAM_CHAT_ID).
    telegram_bot_token: str | None = Field(default=None, validation_alias="TELEGRAM_BOT_TOKEN")
    telegram_chat_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices("TELEGRAM_CHAT_ID", "MANUS_TELEGRAM_CHAT_ID"),
    )
    telegram_channel: str = Field(default="manus", validation_alias="TELEGRAM_CHANNEL")
    telegram_enabled: bool = Field(default=True, validation_alias="TELEGRAM_ENABLED")
    telegram_timeout_seconds: float = Field(default=20.0, validation_alias="TELEGRAM_TIMEOUT_SECONDS")
    telegram_poll_limit: int = Field(default=50, validation_alias="TELEGRAM_POLL_LIMIT")
    telegram_daemon_enabled: bool = Field(default=True, validation_alias="TELEGRAM_DAEMON_ENABLED")
    telegram_daemon_interval_ms: int = Field(default=60_000, validation_alias="TELEGRAM_DAEMON_INTERVAL_MS")
    telegram_daemon_throttle_ms: int = Field(default=1_800_000, validation_alias="TELEGRAM_DAEMON_THROTTLE_MS")
    telegram_daemon_idle_threshold_sec: int = Field(default=300, validation_alias="TELEGRAM_DAEMON_IDLE_SEC")
    telegram_auto_respond: bool = Field(default=True, validation_alias="TELEGRAM_AUTO_RESPOND")
    manus_telegram_chat_id: str | None = Field(default=None, validation_alias="MANUS_TELEGRAM_CHAT_ID")
    glint_telegram_chat_id: str | None = Field(default=None, validation_alias="GLINT_TELEGRAM_CHAT_ID")
    live_session_telegram_heartbeat_enabled: bool = Field(
        default=True,
        validation_alias="LIVE_SESSION_TELEGRAM_HEARTBEAT_ENABLED",
    )
    live_session_telegram_heartbeat_seconds: int = Field(
        default=3600,
        ge=60,
        le=86_400,
        validation_alias="LIVE_SESSION_TELEGRAM_HEARTBEAT_SECONDS",
    )
    # Outbound: Signal Routes / paper fills → Telegram (+ UI feed mirror).
    telegram_trade_signals_enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices(
            "TELEGRAM_TRADE_SIGNALS_ENABLED",
            "TELEGRAM_NOTIFICATIONS_ENABLED",
        ),
    )
    # API-online heartbeat (independent of live trading sessions).
    telegram_system_heartbeat_enabled: bool = Field(
        default=True,
        validation_alias="TELEGRAM_SYSTEM_HEARTBEAT_ENABLED",
    )
    telegram_system_heartbeat_seconds: int = Field(
        default=1800,
        ge=60,
        le=86_400,
        validation_alias="TELEGRAM_SYSTEM_HEARTBEAT_SECONDS",
    )

    # Optional provider keys (stored for CLI/integrations; extra="ignore" alone would drop typing).
    # NOTE: OPENAI_API_KEY also feeds aiprimetech via AliasChoices when AIPRIMETECH_API_KEY is unset.
    openrouter_api_key: str | None = Field(default=None, validation_alias="OPENROUTER_API_KEY")
    xai_api_key: str | None = Field(default=None, validation_alias="XAI_API_KEY")
    finnhub_api_key: str | None = Field(default=None, validation_alias="FINNHUB_API_KEY")
    kraken_api_key: str | None = Field(default=None, validation_alias="KRAKEN_API_KEY")
    kraken_api_secret: str | None = Field(default=None, validation_alias="KRAKEN_API_SECRET")
    bybit_api_key: str | None = Field(default=None, validation_alias="BYBIT_API_KEY")
    bybit_api_secret: str | None = Field(default=None, validation_alias="BYBIT_API_SECRET")
    pionex_api_key: str | None = Field(default=None, validation_alias="PIONEX_API_KEY")
    pionex_api_secret: str | None = Field(default=None, validation_alias="PIONEX_API_SECRET")
    pionex_signal_webhook_token: str | None = Field(
        default=None, validation_alias="PIONEX_SIGNAL_WEBHOOK_TOKEN"
    )

    @field_validator("kraken_autonomy_level")
    @classmethod
    def autonomy_in_range(cls, value: int) -> int:
        if value < 1 or value > 5:
            raise ValueError("KRAKEN_AUTONOMY_LEVEL must be 1-5")
        return value

    @property
    def cors_origins(self) -> list[str]:
        origins = []
        for origin in self.allowed_origins.split(","):
            origin = origin.strip()
            if not origin:
                continue
            if origin == "*":
                origins.append(origin)
                continue

            parsed = urllib.parse.urlparse(origin)
            if parsed.scheme not in ("http", "https") or not parsed.netloc:
                raise ValueError(f"Invalid CORS origin: {origin}. Must have http/https scheme and a valid domain/IP.")
            if parsed.path not in ("", "/") or parsed.query or parsed.fragment:
                raise ValueError(f"Invalid CORS origin: {origin}. Must not contain path, query, or fragment.")

            origins.append(f"{parsed.scheme}://{parsed.netloc}")

        return origins

    @property
    def autonomy(self) -> AutonomyLevel:
        return AutonomyLevel(self.kraken_autonomy_level)

    @property
    def trade_commands_enabled(self) -> bool:
        return self.kraken_live_trading_enabled and self.autonomy >= AutonomyLevel.SUPERVISED

    def trading_guardrails(self) -> TradingGuardrails:
        pairs = frozenset(
            part.strip().upper().replace("/", "").replace("-", "")
            for part in self.kraken_pair_allowlist.split(",")
            if part.strip()
        )
        return TradingGuardrails(
            max_order_size=self.kraken_max_order_size,
            max_notional=self.kraken_max_notional,
            max_open_positions=self.kraken_max_open_positions,
            max_trades_per_hour=self.kraken_max_trades_per_hour,
            min_trade_interval_seconds=self.kraken_min_trade_interval_seconds,
            pair_allowlist=pairs or frozenset({"ADAUSD"}),
        )

    def paper_sizing_context(self, capital_usd: float | None = None):
        """Build a PaperSizingContext from env settings.

        The max notional ceiling is computed as ``paper_max_notional_pct * capital``
        (default 1.5 %), so the cap scales automatically with the simulated balance.

        Args:
            capital_usd: Override simulated balance. Defaults to PAPER_STARTING_BALANCE_USD.
        """
        from .trading.position_sizing import PaperSizingContext, parse_sizing_mode

        mode = parse_sizing_mode(self.paper_sizing_mode)
        balance = float(capital_usd if capital_usd is not None else self.paper_starting_balance_usd)
        # Dynamic ceiling: 1.5 % of balance = $150 on $10k, $75 on $5k, etc.
        max_notional_usd = balance * self.paper_max_notional_pct
        return PaperSizingContext(
            capital_usd=balance,
            mode=mode,
            max_notional_usd=max_notional_usd,
            min_risk_fraction=self.paper_min_risk_fraction,
            max_risk_fraction=self.paper_max_risk_fraction,
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    # Operator vault (App Settings) overlays env before pydantic reads it.
    try:
        from backend.app.integrations.secrets_store import apply_secrets_to_environ

        apply_secrets_to_environ(overwrite_existing=True)
    except Exception:  # noqa: BLE001 — settings must still boot if vault missing/corrupt
        pass
    return Settings()


@lru_cache(maxsize=1)
def get_trade_rate_limiter() -> TradeRateLimiter:
    settings = get_settings()
    return TradeRateLimiter(
        max_trades_per_hour=settings.kraken_max_trades_per_hour,
        min_interval_seconds=settings.kraken_min_trade_interval_seconds,
    )
