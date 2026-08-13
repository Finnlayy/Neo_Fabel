"""Validated API contracts for the advisory-only orchestrator."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _to_camel(value: str) -> str:
    head, *tail = value.split("_")
    return head + "".join(part.capitalize() for part in tail)


class CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=_to_camel,
        populate_by_name=True,
        serialize_by_alias=True,
        extra="ignore",
        allow_inf_nan=False,
    )


class MarketRegime(StrEnum):
    BULL_TRENDING = "BULL_TRENDING"
    BEAR_TRENDING = "BEAR_TRENDING"
    RANGING = "RANGING"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"
    CRYPTO_BOOM = "CRYPTO_BOOM"
    CRYPTO_BUST = "CRYPTO_BUST"


class SignalRecommendation(StrEnum):
    STRONG_BUY = "STRONG_BUY"
    BUY = "BUY"
    HOLD = "HOLD"
    AVOID = "AVOID"


class TickerSnapshot(CamelModel):
    symbol: str = Field(min_length=1, max_length=20, pattern=r"^[A-Za-z0-9.-]+$")
    price: float = Field(gt=0)
    change: float = Field(ge=-100, le=100_000)
    history: list[float] = Field(default_factory=list, max_length=120)

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        return value.strip().upper()


class TelegramSignalSnapshot(CamelModel):
    id: str = Field(min_length=1, max_length=128)
    timestamp: datetime
    channel: str = Field(default="", max_length=128)
    message: str = Field(default="", max_length=2_000)
    sentiment: Literal["BULLISH", "BEARISH", "NEUTRAL"]
    actionable: bool = False
    symbol: str | None = Field(default=None, max_length=20, pattern=r"^[A-Za-z0-9.-]+$")

    @field_validator("symbol")
    @classmethod
    def normalize_optional_symbol(cls, value: str | None) -> str | None:
        return value.strip().upper() if value else None


class NeuralStateSnapshot(CamelModel):
    prediction: float = 0.0
    direction: Literal["UP", "DOWN", "STABLE"]
    confidence: float = Field(ge=0, le=100)
    test_mae: float | None = Field(default=None, ge=0)
    onnx_model: str | None = Field(default=None, max_length=128)
    sync_status: str | None = Field(default=None, max_length=64)
    is_training: bool = False
    mean_val: float | None = None
    std_val: float | None = Field(default=None, ge=0)
    target_formula: str | None = Field(default=None, max_length=256)


class RnaPatternSnapshot(CamelModel):
    bias: Literal["bullish", "bearish", "neutral"]
    confidence: float = Field(ge=0, le=100)


class RecentTradeSnapshot(CamelModel):
    asset: str = Field(min_length=1, max_length=20)
    position_cost: float = Field(ge=0)
    price: float = Field(gt=0)


class MarketRegimeRequest(CamelModel):
    tickers: list[TickerSnapshot] = Field(min_length=1, max_length=25)
    signals: list[TelegramSignalSnapshot] = Field(default_factory=list, max_length=20)
    neural_states: dict[str, NeuralStateSnapshot] = Field(default_factory=dict)
    rna_patterns: dict[str, RnaPatternSnapshot] = Field(default_factory=dict)

    @field_validator("neural_states", "rna_patterns")
    @classmethod
    def bound_state_maps(cls, value: dict[str, Any]) -> dict[str, Any]:
        if len(value) > 25:
            raise ValueError("at most 25 state entries are allowed")
        return {str(key).strip().upper(): item for key, item in value.items()}


class SignalQualityRequest(CamelModel):
    signal: TelegramSignalSnapshot
    symbol: str = Field(min_length=1, max_length=20, pattern=r"^[A-Za-z0-9.-]+$")
    current_price: float = Field(gt=0)
    neural_prediction: NeuralStateSnapshot | None = None
    rna_pattern: RnaPatternSnapshot | None = None
    position_cost: float | None = Field(default=None, ge=0)
    market_regime: MarketRegime

    @field_validator("symbol")
    @classmethod
    def normalize_signal_symbol(cls, value: str) -> str:
        return value.strip().upper()


class FullDecisionRequest(MarketRegimeRequest):
    recent_trades: list[RecentTradeSnapshot] = Field(default_factory=list, max_length=50)


class SourceCoverage(CamelModel):
    market_data: bool
    telegram_signals: bool
    neural_states: bool
    rna_patterns: bool
    recent_trades: bool


class AdvisoryMetadata(CamelModel):
    mode: Literal["advisory"] = "advisory"
    execution_allowed: Literal[False] = False
    request_id: str
    provider: str
    model: str
    source_coverage: SourceCoverage
    audit_persisted: bool
    timestamp: datetime


class StrategyWeights(CamelModel):
    sentiment: float = Field(ge=0, le=1)
    neural: float = Field(ge=0, le=1)
    rna_pattern: float = Field(ge=0, le=1)
    technical_pattern: float = Field(ge=0, le=1)


class SignalFactors(CamelModel):
    sentiment_score: float = Field(ge=0, le=1)
    neural_prediction_score: float = Field(ge=0, le=1)
    pattern_score: float = Field(ge=0, le=1)
    rna_score: float = Field(ge=0, le=1)
    position_size_risk: float = Field(ge=0, le=1)


class MarketRegimePayload(CamelModel):
    regime: MarketRegime
    confidence: float = Field(ge=0, le=1)
    reasoning: str = Field(min_length=1, max_length=2_000)
    risk_level: Literal["LOW", "MEDIUM", "HIGH", "EXTREME"] = "MEDIUM"
    strategy_weights: StrategyWeights


class SignalQualityPayload(CamelModel):
    quality: float = Field(ge=0, le=1)
    recommendation: SignalRecommendation
    reasoning: str = Field(min_length=1, max_length=2_000)
    factors: SignalFactors


class ScoredSignal(SignalQualityPayload):
    symbol: str = Field(min_length=1, max_length=20)


class FullDecisionPayload(CamelModel):
    regime: MarketRegime
    regime_confidence: float = Field(ge=0, le=1)
    regime_reasoning: str = Field(min_length=1, max_length=2_000)
    risk_level: Literal["LOW", "MEDIUM", "HIGH", "EXTREME"] = "MEDIUM"
    signal_scores: list[ScoredSignal] = Field(default_factory=list, max_length=20)
    strategy_weights: StrategyWeights


class MarketRegimeResponse(AdvisoryMetadata, MarketRegimePayload):
    pass


class SignalQualityResponse(AdvisoryMetadata, SignalQualityPayload):
    pass


class FullDecisionResponse(AdvisoryMetadata, FullDecisionPayload):
    pass


class DecisionHistoryItem(CamelModel):
    id: str
    request_id: str
    decision_type: Literal["market_regime", "signal_quality", "full_decision"]
    provider: str
    model: str
    status: Literal["success", "error"]
    output_data: dict[str, Any] | None
    reasoning: str | None
    timestamp: datetime


class DecisionHistoryResponse(CamelModel):
    mode: Literal["advisory"] = "advisory"
    execution_allowed: Literal[False] = False
    request_id: str
    provider: Literal["database"] = "database"
    model: Literal["audit-log"] = "audit-log"
    source_coverage: SourceCoverage
    audit_persisted: bool = True
    timestamp: datetime
    decisions: list[DecisionHistoryItem]
