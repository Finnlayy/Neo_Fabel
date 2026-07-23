"""LLM-backed advisory analysis with strict output validation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from backend.app.integrations.gemini_client import AiNotConfigured, _parse_json_object
from backend.app.integrations.llm_router import LlmRouter
from backend.app.settings import Settings

from .prompts import (
    FULL_DECISION_PROMPT,
    MARKET_REGIME_PROMPT,
    SIGNAL_QUALITY_PROMPT,
    SYSTEM_PROMPT,
)
from .schemas import (
    FullDecisionPayload,
    FullDecisionRequest,
    MarketRegimePayload,
    MarketRegimeRequest,
    SignalQualityPayload,
    SignalQualityRequest,
    SourceCoverage,
    StrategyWeights,
)

PayloadT = TypeVar("PayloadT", bound=BaseModel)


class AdvisoryOutputError(RuntimeError):
    """Raised when a provider returns malformed or unsafe advisory output."""


@dataclass(frozen=True)
class AdvisoryResult:
    payload: BaseModel
    provider: str
    model: str
    coverage: SourceCoverage


def source_coverage(
    body: MarketRegimeRequest | FullDecisionRequest | SignalQualityRequest,
) -> SourceCoverage:
    if isinstance(body, SignalQualityRequest):
        return SourceCoverage(
            market_data=True,
            telegram_signals=True,
            neural_states=body.neural_prediction is not None,
            rna_patterns=body.rna_pattern is not None,
            recent_trades=body.position_cost is not None,
        )
    return SourceCoverage(
        market_data=bool(body.tickers),
        telegram_signals=bool(body.signals),
        neural_states=bool(body.neural_states),
        rna_patterns=bool(body.rna_patterns),
        recent_trades=bool(getattr(body, "recent_trades", [])),
    )


def _normalized_confidence(value: float) -> float:
    return max(0.0, min(1.0, value / 100.0 if value > 1.0 else value))


def _normalize_input(value: Any) -> Any:
    if isinstance(value, dict):
        normalized: dict[str, Any] = {}
        for key, item in value.items():
            if key == "confidence" and isinstance(item, (int, float)):
                normalized[key] = _normalized_confidence(float(item))
            else:
                normalized[key] = _normalize_input(item)
        return normalized
    if isinstance(value, list):
        return [_normalize_input(item) for item in value]
    return value


def _normalize_weights(payload: PayloadT) -> PayloadT:
    weights = getattr(payload, "strategy_weights", None)
    if not isinstance(weights, StrategyWeights):
        return payload
    raw = weights.model_dump()
    total = sum(raw.values())
    if total <= 0:
        raise AdvisoryOutputError("strategy weights must have a positive sum")
    normalized = {key: value / total for key, value in raw.items()}
    return payload.model_copy(update={"strategy_weights": StrategyWeights(**normalized)})


def _normalize_raw_weights(raw: dict[str, Any]) -> dict[str, Any]:
    weights = raw.get("strategyWeights")
    key = "strategyWeights"
    if not isinstance(weights, dict):
        weights = raw.get("strategy_weights")
        key = "strategy_weights"
    if not isinstance(weights, dict):
        return raw
    expected = ("sentiment", "neural", "rnaPattern", "technicalPattern")
    if key == "strategy_weights":
        expected = ("sentiment", "neural", "rna_pattern", "technical_pattern")
    try:
        numeric = {name: float(weights[name]) for name in expected}
    except (KeyError, TypeError, ValueError) as exc:
        raise AdvisoryOutputError("strategy weights are incomplete or non-numeric") from exc
    if any(value < 0 for value in numeric.values()):
        raise AdvisoryOutputError("strategy weights must be non-negative")
    total = sum(numeric.values())
    if total <= 0:
        raise AdvisoryOutputError("strategy weights must have a positive sum")
    return {**raw, key: {name: value / total for name, value in numeric.items()}}


class AdvisoryOrchestrator:
    """Generate validated analysis and expose no execution capability."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.router = LlmRouter(settings)

    def _assert_available(self) -> None:
        if not self.settings.orchestrator_advisory_enabled:
            raise AiNotConfigured("ORCHESTRATOR_ADVISORY_ENABLED=false")
        if not self.router.configured:
            raise AiNotConfigured("No configured LLM provider for advisory analysis")

    async def _generate(
        self,
        *,
        prompt: str,
        body: BaseModel,
        payload_type: type[PayloadT],
    ) -> tuple[PayloadT, str, str]:
        self._assert_available()
        input_data = body.model_dump(mode="json", by_alias=True)
        wire = json.dumps(_normalize_input(input_data), separators=(",", ":"), ensure_ascii=True)
        result = await self.router.generate_text(
            messages=[{"role": "user", "content": f"{prompt}\n{wire}"}],
            model_selection="flash",
            system=SYSTEM_PROMPT,
        )
        try:
            raw = _parse_json_object(str(result.get("reply") or ""))
            raw = _normalize_raw_weights(raw)
            payload = payload_type.model_validate(raw)
            payload = _normalize_weights(payload)
        except (ValueError, TypeError, ValidationError) as exc:
            raise AdvisoryOutputError("provider returned invalid advisory JSON") from exc
        return (
            payload,
            str(result.get("provider") or "unknown"),
            str(result.get("modelUsed") or "unknown"),
        )

    async def analyze_market_regime(self, body: MarketRegimeRequest) -> AdvisoryResult:
        payload, provider, model = await self._generate(
            prompt=MARKET_REGIME_PROMPT,
            body=body,
            payload_type=MarketRegimePayload,
        )
        return AdvisoryResult(payload, provider, model, source_coverage(body))

    async def score_signal_quality(self, body: SignalQualityRequest) -> AdvisoryResult:
        payload, provider, model = await self._generate(
            prompt=SIGNAL_QUALITY_PROMPT,
            body=body,
            payload_type=SignalQualityPayload,
        )
        return AdvisoryResult(payload, provider, model, source_coverage(body))

    async def full_decision(self, body: FullDecisionRequest) -> AdvisoryResult:
        payload, provider, model = await self._generate(
            prompt=FULL_DECISION_PROMPT,
            body=body,
            payload_type=FullDecisionPayload,
        )
        allowed_symbols = {signal.symbol for signal in body.signals if signal.symbol}
        filtered_scores = [
            score for score in payload.signal_scores if score.symbol.upper() in allowed_symbols
        ][:20]
        filtered_scores.sort(key=lambda item: item.quality, reverse=True)
        payload = payload.model_copy(update={"signal_scores": filtered_scores})
        return AdvisoryResult(payload, provider, model, source_coverage(body))
