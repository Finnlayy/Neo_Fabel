"""Strict webhook, admin, receipt, and history DTOs."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def _forbid_exponent(value: Decimal) -> Decimal:
    if value.is_nan() or value.is_infinite():
        raise ValueError("decimal must be finite")
    text = format(value, "f")
    if "e" in text.lower():
        raise ValueError("exponent notation is not allowed")
    return value


def _reject_exponent_literal(value: object) -> object:
    """Reject scientific notation before Decimal coercion (e.g. '1e-3')."""
    if isinstance(value, str) and any(ch in value.lower() for ch in ("e",)):
        # Allow plain decimals / signs / dots only — 'e' always means exponent here.
        raise ValueError("exponent notation is not allowed")
    return value


class TradingViewWebhookBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    credential: str = Field(min_length=16, max_length=256)
    signal_id: str = Field(min_length=1, max_length=128)
    occurred_at: str = Field(min_length=10, max_length=40)
    strategy_id: str = Field(min_length=1, max_length=64)
    pair: str = Field(min_length=2, max_length=20)
    side: Literal["buy", "sell"]
    volume: Decimal = Field(gt=Decimal(0), max_digits=24, decimal_places=12)
    order_type: Literal["market", "limit"]
    price: Decimal | None = Field(default=None, gt=Decimal(0), max_digits=24, decimal_places=12)
    order_id: str | None = Field(default=None, max_length=64)
    raw_symbol: str | None = Field(default=None, max_length=64)
    observed_price: Decimal | None = Field(default=None, gt=Decimal(0), max_digits=24, decimal_places=12)
    pattern_bias: Literal["bullish", "bearish", "neutral"] | None = Field(
        default=None,
        description="Optional blind-pattern bias from RNA.",
    )
    pattern_confidence: Decimal | None = Field(
        default=None,
        gt=Decimal(0),
        le=Decimal(100),
        max_digits=6,
        decimal_places=2,
        description="Optional blind-pattern confidence from RNA (0..100).",
    )

    @field_validator("pair")
    @classmethod
    def normalize_pair(cls, value: str) -> str:
        normalized = value.strip().upper().replace("/", "").replace("-", "")
        if not normalized.isalnum():
            raise ValueError("pair contains unsupported characters")
        return normalized

    @field_validator("volume", "price", "observed_price", "pattern_confidence", mode="before")
    @classmethod
    def no_exponent_literal(cls, value: object) -> object:
        return _reject_exponent_literal(value)

    @field_validator("volume", "price", "observed_price", "pattern_confidence")
    @classmethod
    def strict_decimal(cls, value: Decimal | None) -> Decimal | None:
        if value is None:
            return None
        return _forbid_exponent(value)

    @field_validator("signal_id", "strategy_id", "credential")
    @classmethod
    def no_control_chars(cls, value: str) -> str:
        if any(ord(ch) < 32 for ch in value):
            raise ValueError("control characters are not allowed")
        return value

    @model_validator(mode="after")
    def require_price_for_limit(self) -> TradingViewWebhookBody:
        if self.order_type == "limit" and self.price is None:
            raise ValueError("price is required for limit orders")
        return self


class SignalReceipt(BaseModel):
    submission_id: UUID
    receipt_status: Literal["accepted_for_processing"] = "accepted_for_processing"
    replayed: bool = False
    execution_target: Literal["kraken_paper"] = "kraken_paper"
    request_id: str


class SignalRouteCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=128)
    strategy_id: str = Field(min_length=1, max_length=64)
    pair_allowlist: str = Field(default="ADAUSD,XRPUSD,ADAEUR,XRPEUR", max_length=512)
    max_volume: Decimal = Field(default=Decimal("0.01"), gt=Decimal(0), max_digits=24, decimal_places=12)
    max_notional: Decimal | None = Field(default=None, gt=Decimal(0), max_digits=24, decimal_places=12)
    allowed_order_types: str = Field(default="market,limit", max_length=64)
    max_event_age_seconds: int = Field(default=300, ge=1, le=3600)
    max_rate_per_minute: int = Field(default=10, ge=1, le=1000)
    max_backlog: int = Field(default=100, ge=1, le=10000)


class SignalRoutePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_version: int = Field(ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=128)
    mode: Literal["bypass_ai", "advisory"] | None = None
    enabled: bool | None = None
    pair_allowlist: str | None = Field(default=None, max_length=512)
    max_volume: Decimal | None = Field(default=None, gt=Decimal(0), max_digits=24, decimal_places=12)
    max_notional: Decimal | None = Field(default=None, gt=Decimal(0), max_digits=24, decimal_places=12)
    allowed_order_types: str | None = Field(default=None, max_length=64)
    max_event_age_seconds: int | None = Field(default=None, ge=1, le=3600)
    max_rate_per_minute: int | None = Field(default=None, ge=1, le=1000)
    max_backlog: int | None = Field(default=None, ge=1, le=10000)


class SignalRouteView(BaseModel):
    id: str
    public_route_key: str
    name: str
    strategy_id: str
    mode: Literal["bypass_ai", "advisory"]
    enabled: bool
    execution_target: Literal["kraken_paper"]
    pair_allowlist: str
    max_volume: str
    max_notional: str | None
    allowed_order_types: str
    max_event_age_seconds: int
    max_rate_per_minute: int
    max_backlog: int
    policy_version: str
    version: int
    created_at: str
    updated_at: str
    webhook_url_path: str
    has_tradingview_credential: bool
    has_mcp_credential: bool


class CredentialReveal(BaseModel):
    credential_id: str
    kind: Literal["tradingview_secret", "mcp_bearer"]
    plaintext: str
    display_prefix: str
    activated_at: str


class RnaContextUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bias: Literal["bullish", "bearish", "neutral"]
    confidence: Decimal = Field(ge=Decimal(0), le=Decimal(100))
    symbol: str | None = Field(default=None, max_length=20)

    @field_validator("confidence", mode="before")
    @classmethod
    def normalize_confidence(cls, value: object) -> Decimal:
        return _forbid_exponent(Decimal(str(value)))


class SignalAutomationStatus(BaseModel):
    signal_routes_enabled: bool
    tradingview_ingress_enabled: bool
    mcp_signal_adapter_enabled: bool
    signal_worker_enabled: bool
    signal_execution_enabled: bool
    ai_advisory_enabled: bool
    execution_target: Literal["kraken_paper"] = "kraken_paper"
    paper_only: Literal[True] = True
    queue_depth: int
    oldest_ready_age_seconds: float | None
    worker_heartbeat_ok: bool
    advisory_ready: bool


class SignalSubmissionView(BaseModel):
    id: str
    route_id: str
    source: Literal["tradingview", "mcp", "fable_engine"]
    signal_id: str
    pair: str
    side: str
    volume: str
    order_type: str
    mode_snapshot: str
    status: str
    reason_code: str | None
    request_id: str
    paper_intent_id: str | None
    occurred_at: str
    created_at: str
    updated_at: str
    advisory_decision: str | None = None


class McpSubmitArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    idempotency_key: str = Field(min_length=1, max_length=128)
    occurred_at: str = Field(min_length=10, max_length=40)
    strategy_id: str = Field(min_length=1, max_length=64)
    pair: str = Field(min_length=2, max_length=20)
    side: Literal["buy", "sell"]
    volume: str = Field(min_length=1, max_length=40)
    order_type: Literal["market", "limit"]
    price: str | None = Field(default=None, max_length=40)
    observed_price: str | None = Field(default=None, max_length=40)
    pattern_bias: Literal["bullish", "bearish", "neutral"] | None = Field(default=None)
    pattern_confidence: str | None = Field(default=None, max_length=40)

    @field_validator("pair")
    @classmethod
    def normalize_pair(cls, value: str) -> str:
        normalized = value.strip().upper().replace("/", "").replace("-", "")
        if not normalized.isalnum():
            raise ValueError("pair contains unsupported characters")
        return normalized

    @field_validator("volume", "price", "observed_price", "pattern_confidence", mode="before")
    @classmethod
    def no_exponent_literal(cls, value: object) -> object:
        return _reject_exponent_literal(value)

    @field_validator("idempotency_key", "strategy_id")
    @classmethod
    def no_control_chars(cls, value: str) -> str:
        if any(ord(ch) < 32 for ch in value):
            raise ValueError("control characters are not allowed")
        return value

    def volume_decimal(self) -> Decimal:
        try:
            value = Decimal(self.volume)
        except InvalidOperation as exc:
            raise ValueError("invalid volume") from exc
        if value <= 0:
            raise ValueError("volume must be positive")
        return _forbid_exponent(value)

    def price_decimal(self) -> Decimal | None:
        if self.price is None:
            return None
        try:
            value = Decimal(self.price)
        except InvalidOperation as exc:
            raise ValueError("invalid price") from exc
        if value <= 0:
            raise ValueError("price must be positive")
        return _forbid_exponent(value)

    def observed_price_decimal(self) -> Decimal | None:
        if self.observed_price is None:
            return None
        try:
            value = Decimal(self.observed_price)
        except InvalidOperation as exc:
            raise ValueError("invalid observed_price") from exc
        if value <= 0:
            raise ValueError("observed_price must be positive")
        return _forbid_exponent(value)

    def pattern_confidence_decimal(self) -> Decimal | None:
        if self.pattern_confidence is None:
            return None
        try:
            value = Decimal(self.pattern_confidence)
        except InvalidOperation as exc:
            raise ValueError("invalid pattern_confidence") from exc
        return _forbid_exponent(value)
