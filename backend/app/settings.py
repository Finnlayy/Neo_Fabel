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
    firebase_credentials_path: str | None = Field(default=None, validation_alias="GOOGLE_APPLICATION_CREDENTIALS")
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

    @field_validator("kraken_autonomy_level")
    @classmethod
    def autonomy_in_range(cls, value: int) -> int:
        if value < 1 or value > 5:
            raise ValueError("KRAKEN_AUTONOMY_LEVEL must be 1-5")
        return value

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]

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
