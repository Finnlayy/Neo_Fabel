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
    kraken_max_open_positions: int = Field(default=3, validation_alias="KRAKEN_MAX_OPEN_POSITIONS")
    kraken_max_trades_per_hour: int = Field(default=10, validation_alias="KRAKEN_MAX_TRADES_PER_HOUR")
    kraken_pair_allowlist: str = Field(default="BTCUSD,ETHUSD", validation_alias="KRAKEN_PAIR_ALLOWLIST")
    firebase_project_id: str | None = Field(default=None, validation_alias="FIREBASE_PROJECT_ID")
    firebase_credentials_path: str | None = Field(
        default=None, validation_alias=AliasChoices("GOOGLE_APPLICATION_CREDENTIALS", "FIREBASE_CREDENTIALS_PATH")
    )
    # Local-only: allow loopback API calls without Firebase when credentials are missing.
    # Forced off outside development. Never enable in production.
    auth_dev_bypass: bool = Field(default=True, validation_alias="AUTH_DEV_BYPASS")
    # Paper ledger without Kraken CLI (required on native Windows — CLI is Linux/macOS/WSL).
    paper_local_ledger: bool = Field(default=True, validation_alias="PAPER_LOCAL_LEDGER")
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

    # AI chat / orchestrate / vision (Gemini via Generative Language API).
    gemini_api_key: str | None = Field(default=None, validation_alias="GEMINI_API_KEY")
    ai_chat_enabled: bool = Field(default=True, validation_alias="AI_CHAT_ENABLED")
    ai_allow_deterministic_fallback: bool = Field(
        default=False, validation_alias="AI_ALLOW_DETERMINISTIC_FALLBACK"
    )
    gemini_timeout_seconds: float = Field(default=45.0, validation_alias="GEMINI_TIMEOUT_SECONDS")
    gemini_default_model: str = Field(default="gemini-2.0-flash", validation_alias="GEMINI_DEFAULT_MODEL")

    # TVAPI / chart optimize (RapidAPI optional; deterministic sweep always available).
    tradingview_rapidapi_key: str | None = Field(default=None, validation_alias="TRADINGVIEW_RAPIDAPI_KEY")
    tvapi_enabled: bool = Field(default=True, validation_alias="TVAPI_ENABLED")

    # Phase 1 — Qdrant vector index (paper/dev; no live trading).
    qdrant_enabled: bool = Field(default=True, validation_alias="QDRANT_ENABLED")
    qdrant_url: str = Field(default="http://localhost:6333", validation_alias="QDRANT_URL")
    qdrant_api_key: str | None = Field(default=None, validation_alias="QDRANT_API_KEY")
    qdrant_collection: str = Field(default="neo_fabel_vectors", validation_alias="QDRANT_COLLECTION")
    qdrant_vector_size: int = Field(default=8, validation_alias="QDRANT_VECTOR_SIZE")
    qdrant_timeout_seconds: float = Field(default=10.0, validation_alias="QDRANT_TIMEOUT_SECONDS")

    # Academy / training loop (synthetic drills only; never places live orders).
    training_loop_enabled: bool = Field(default=True, validation_alias="TRAINING_LOOP_ENABLED")
    training_loop_auto_start: bool = Field(default=False, validation_alias="TRAINING_LOOP_AUTO_START")
    training_loop_night_mode: bool = Field(default=True, validation_alias="TRAINING_LOOP_NIGHT_MODE")
    training_loop_night_start: str = Field(default="22:00", validation_alias="TRAINING_LOOP_NIGHT_START")
    training_loop_night_end: str = Field(default="06:00", validation_alias="TRAINING_LOOP_NIGHT_END")
    training_loop_drills_per_hour: float = Field(
        default=12.0, validation_alias="TRAINING_LOOP_DRILLS_PER_HOUR"
    )

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
    manus_telegram_chat_id: str | None = Field(default=None, validation_alias="MANUS_TELEGRAM_CHAT_ID")
    glint_telegram_chat_id: str | None = Field(default=None, validation_alias="GLINT_TELEGRAM_CHAT_ID")

    # Optional provider keys (stored for CLI/integrations; extra="ignore" alone would drop typing).
    openai_api_key: str | None = Field(default=None, validation_alias="OPENAI_API_KEY")
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
            max_open_positions=self.kraken_max_open_positions,
            max_trades_per_hour=self.kraken_max_trades_per_hour,
            pair_allowlist=pairs or frozenset({"BTCUSD"}),
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


@lru_cache(maxsize=1)
def get_trade_rate_limiter() -> TradeRateLimiter:
    settings = get_settings()
    return TradeRateLimiter(max_trades_per_hour=settings.kraken_max_trades_per_hour)
