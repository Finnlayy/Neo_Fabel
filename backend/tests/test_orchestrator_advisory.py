"""Contract and safety tests for the advisory-only orchestrator."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend.app.auth import require_user
from backend.app.main import app
from backend.app.orchestrator.schemas import FullDecisionRequest, MarketRegimeRequest
from backend.app.orchestrator.service import AdvisoryOrchestrator
from backend.app.routers import orchestrator as orchestrator_router
from backend.app.settings import Settings


class FakeRouter:
    configured = True

    def __init__(self, reply: str):
        self.reply = reply

    async def generate_text(self, **_kwargs: Any) -> dict[str, Any]:
        return {
            "reply": self.reply,
            "provider": "openrouter",
            "modelUsed": "test-model",
        }


def _settings(*, enabled: bool = True) -> Settings:
    return Settings(
        orchestrator_advisory_enabled=enabled,
        openrouter_api_key="test-key",
    )


def _market_body() -> MarketRegimeRequest:
    return MarketRegimeRequest.model_validate(
        {
            "tickers": [
                {"symbol": "BTC", "price": 50_000, "change": 2.5, "history": [49_000, 50_000]}
            ],
            "signals": [],
            "neuralStates": {},
            "rnaPatterns": {},
        }
    )


def _full_body() -> FullDecisionRequest:
    return FullDecisionRequest.model_validate(
        {
            "tickers": [
                {"symbol": "BTC", "price": 50_000, "change": 2.5, "history": [49_000, 50_000]}
            ],
            "signals": [
                {
                    "id": "sig-1",
                    "timestamp": "2026-07-23T12:00:00Z",
                    "channel": "test",
                    "message": "BTC momentum",
                    "sentiment": "BULLISH",
                    "actionable": True,
                    "symbol": "BTC",
                }
            ],
            "neuralStates": {},
            "rnaPatterns": {},
            "recentTrades": [],
        }
    )


@pytest.mark.asyncio
async def test_market_regime_validates_and_normalizes_weights() -> None:
    service = AdvisoryOrchestrator(_settings())
    service.router = FakeRouter(
        """{
          "regime":"BULL_TRENDING",
          "confidence":0.82,
          "reasoning":"Broad momentum is positive.",
          "riskLevel":"MEDIUM",
          "strategyWeights":{
            "sentiment":2,
            "neural":1,
            "rnaPattern":1,
            "technicalPattern":0
          }
        }"""
    )

    result = await service.analyze_market_regime(_market_body())

    assert result.payload.regime == "BULL_TRENDING"
    assert result.payload.confidence == pytest.approx(0.82)
    assert sum(result.payload.strategy_weights.model_dump().values()) == pytest.approx(1.0)
    assert result.coverage.market_data is True
    assert result.coverage.telegram_signals is False


@pytest.mark.asyncio
async def test_full_decision_filters_unknown_symbols_and_sorts_scores() -> None:
    service = AdvisoryOrchestrator(_settings())
    service.router = FakeRouter(
        """{
          "regime":"RANGING",
          "regimeConfidence":0.61,
          "regimeReasoning":"Mixed inputs.",
          "riskLevel":"HIGH",
          "signalScores":[
            {
              "symbol":"ETH","quality":0.99,"recommendation":"STRONG_BUY",
              "reasoning":"Invented symbol.",
              "factors":{"sentimentScore":1,"neuralPredictionScore":1,"patternScore":1,"rnaScore":1,"positionSizeRisk":0}
            },
            {
              "symbol":"BTC","quality":0.71,"recommendation":"BUY",
              "reasoning":"Input signal is constructive.",
              "factors":{"sentimentScore":0.8,"neuralPredictionScore":0.5,"patternScore":0.7,"rnaScore":0.5,"positionSizeRisk":0.2}
            }
          ],
          "strategyWeights":{"sentiment":0.4,"neural":0.2,"rnaPattern":0.2,"technicalPattern":0.2}
        }"""
    )

    result = await service.full_decision(_full_body())

    assert [item.symbol for item in result.payload.signal_scores] == ["BTC"]
    assert result.payload.signal_scores[0].quality == pytest.approx(0.71)


def test_disabled_advisory_returns_explicit_503(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_user() -> dict[str, str]:
        return {"uid": "test-user"}

    app.dependency_overrides[require_user] = fake_user
    app.dependency_overrides[orchestrator_router._service] = lambda: AdvisoryOrchestrator(
        _settings(enabled=False)
    )
    try:
        response = TestClient(app).post(
            "/api/v1/orchestrator/market-regime",
            headers={"Authorization": "Bearer test"},
            json=_market_body().model_dump(mode="json", by_alias=True),
        )
        assert response.status_code == 503
        assert response.json()["detail"]["code"] == "orchestrator_unavailable"
    finally:
        app.dependency_overrides.clear()


def test_full_decision_endpoint_exposes_advisory_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = AdvisoryOrchestrator(_settings())
    service.router = FakeRouter(
        """{
          "regime":"RANGING",
          "regimeConfidence":0.6,
          "regimeReasoning":"Inputs are mixed.",
          "riskLevel":"MEDIUM",
          "signalScores":[],
          "strategyWeights":{"sentiment":0.25,"neural":0.25,"rnaPattern":0.25,"technicalPattern":0.25}
        }"""
    )

    async def fake_user() -> dict[str, str]:
        return {"uid": "test-user"}

    async def fake_audit(**_kwargs: Any) -> bool:
        return True

    monkeypatch.setattr(orchestrator_router, "_audit", fake_audit)
    app.dependency_overrides[require_user] = fake_user
    app.dependency_overrides[orchestrator_router._service] = lambda: service
    try:
        response = TestClient(app).post(
            "/api/v1/orchestrator/full-decision",
            headers={"Authorization": "Bearer test"},
            json=_full_body().model_dump(mode="json", by_alias=True),
        )
        assert response.status_code == 200
        body = response.json()
        assert body["mode"] == "advisory"
        assert body["executionAllowed"] is False
        assert body["provider"] == "openrouter"
        assert body["model"] == "test-model"
        assert body["auditPersisted"] is True
    finally:
        app.dependency_overrides.clear()


def test_orchestrator_package_has_no_execution_imports() -> None:
    root = Path(__file__).resolve().parents[1] / "app" / "orchestrator"
    combined = "\n".join(path.read_text(encoding="utf-8") for path in root.glob("*.py"))
    forbidden = (
        "paper_orders",
        "kraken_cli",
        "trading.loops",
        "signals.worker",
        "place_order",
        "trade.execute",
    )
    assert not any(token in combined for token in forbidden)
