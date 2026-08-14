"""tvremix Pine list/read integration for TVAPI optimizer."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.app.auth import require_user
from backend.app.integrations.tvremix_client import parse_pine_inputs, scripts_to_strategies
from backend.app.main import app
from backend.app.settings import get_settings

client = TestClient(app)


def _fake_user() -> dict:
    return {"uid": "tvremix-test", "email_verified": True, "firebase": {"sign_in_provider": "google.com"}}


def test_parse_pine_inputs() -> None:
    src = """
//@version=5
strategy("Demo")
len = input.int(14, "RSI Length")
mult = input.float(2.5, title="BB Mult")
useTrail = input.bool(true, "Use Trail")
"""
    inputs = parse_pine_inputs(src)
    assert inputs.get("RSI Length") == 14
    assert inputs.get("BB Mult") == 2.5
    assert inputs.get("Use Trail") is True


def test_scripts_to_strategies_maps_origin() -> None:
    rows = scripts_to_strategies(
        [{"id": "USER;abc", "name": "My EMA Cross", "source": 'x = input.int(8, "emaFast")'}]
    )
    assert len(rows) == 1
    assert rows[0]["origin"] == "tvremix"
    assert rows[0]["kind"] == "ema_cross"
    assert rows[0]["inputs"].get("emaFast") == 8


@pytest.mark.asyncio
async def test_list_chart_strategies_merges_tvremix(monkeypatch) -> None:
    monkeypatch.setenv("TVREMIX_API_KEY", "tvr_test_key")
    monkeypatch.setenv("TVREMIX_ENABLED", "true")
    get_settings.cache_clear()

    class _Fake:
        configured = True

        async def list_pine_scripts(self):
            return [
                {"id": "sess-1", "name": "Active Scalper", "origin": "session"},
                {"id": "saved-2", "name": "Swing SMC", "source": 'a = input.int(5, "swingLength")'},
            ]

    monkeypatch.setattr(
        "backend.app.integrations.tvapi_optimizer.TvremixClient",
        lambda settings=None: _Fake(),
    )

    from backend.app.integrations.tvapi_optimizer import list_chart_strategies

    result = await list_chart_strategies("BTCUSD")
    assert result["success"] is True
    assert result["tvremixCount"] == 2
    assert "tvremix" in result["source"]
    ids = {s["id"] for s in result["strategies"]}
    assert "sess-1" in ids
    assert "ema_cross_grid" in ids  # probe still present


def test_chart_strategies_endpoint_with_mock(monkeypatch) -> None:
    app.dependency_overrides[require_user] = _fake_user
    try:
        monkeypatch.setenv("TVAPI_ENABLED", "true")
        monkeypatch.setenv("TVREMIX_API_KEY", "tvr_test_key")
        get_settings.cache_clear()

        class _Fake:
            async def list_pine_scripts(self):
                return [{"id": "p1", "name": "Pine One"}]

        monkeypatch.setattr(
            "backend.app.integrations.tvapi_optimizer.TvremixClient",
            lambda settings=None: _Fake(),
        )

        response = client.post(
            "/api/tvapi/chart-strategies",
            headers={"Authorization": "Bearer test"},
            json={"symbol": "BTCUSD"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert any(s.get("id") == "p1" for s in body["strategies"])
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()


def test_optimize_with_inline_pine_source(monkeypatch) -> None:
    app.dependency_overrides[require_user] = _fake_user
    try:
        monkeypatch.setenv("TVAPI_ENABLED", "true")
        get_settings.cache_clear()

        from backend.app.integrations.backtest.ema_grid import synthetic_candles

        async def _synth(symbol: str, timeframe: str, *, limit: int = 300):
            return synthetic_candles(symbol, n=limit), "synthetic-ohlcv"

        monkeypatch.setattr(
            "backend.app.integrations.tvapi_optimizer.fetch_optimize_candles",
            _synth,
        )

        pine = 'emaFast = input.int(5, "emaFast")\nemaSlow = input.int(20, "emaSlow")'
        response = client.post(
            "/api/tvapi/optimize",
            headers={"Authorization": "Bearer test"},
            json={
                "strategy": "ema_cross",
                "symbol": "BTCUSD",
                "timeframe": "5m",
                "minTrades": 1,
                "primaryObjective": "profit_factor",
                "secondaryObjective": "percent_profitable",
                "parameters": {},
                "pineName": "Inline EMA",
                "pineSource": pine,
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert "Inline EMA" in body["bericht"] or body.get("pine", {}).get("name") == "Inline EMA"
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()
