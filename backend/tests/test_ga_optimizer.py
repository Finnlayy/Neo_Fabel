"""Unit tests for genetic forward optimizer (no live network)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.auth import require_user
from backend.app.integrations.ga_optimizer.engine import (
    Candle,
    build_symbol_pack,
    fitness,
    run_ga_optimize,
)
from backend.app.integrations.ga_optimizer.pine_export import (
    enforce_trading_invariants,
    export_pines_from_payload,
    normalize_candidates,
)
from backend.app.main import app

FIXTURES = Path(__file__).resolve().parent / "fixtures"
RESULTS_JSON = FIXTURES / "ga_forward_results.json"
ETH_SAMPLE = FIXTURES / "ETHUSDT_15m_sample.json"


@pytest.fixture
def authenticated_user() -> None:
    app.dependency_overrides[require_user] = lambda: {
        "uid": "ga-test-user",
        "email_verified": True,
        "firebase": {"sign_in_provider": "google.com"},
    }
    yield
    app.dependency_overrides.pop(require_user, None)


def test_fitness_few_trades_is_penalty() -> None:
    assert fitness({"trades": 0, "net": 10, "pf": 2, "wr": 60, "dd": 1, "sharpe": 1, "consistency": 1, "streak": 0}) == -100.0
    assert fitness({"trades": 9, "net": 50, "pf": 3, "wr": 70, "dd": 2, "sharpe": 2, "consistency": 1, "streak": 1}) == -100.0


def test_fitness_enough_trades_finite() -> None:
    score = fitness(
        {
            "trades": 20,
            "net": 10.0,
            "pf": 1.5,
            "wr": 55.0,
            "dd": 5.0,
            "sharpe": 1.0,
            "consistency": 0.5,
            "streak": 2.0,
        }
    )
    assert score > -100.0
    assert isinstance(score, float)


def test_normalize_candidates_top3_schema() -> None:
    payload = json.loads(RESULTS_JSON.read_text(encoding="utf-8"))
    rows = normalize_candidates(payload, "ETH/USDT")
    assert len(rows) == 3
    assert rows[0].source == "top3"
    assert "min_conf" in rows[0].params
    assert "sl_atr_mul" in rows[0].params


def test_normalize_candidates_per_symbol() -> None:
    payload = {
        "per_symbol": {
            "ETHUSDT": {
                "top3": [
                    {
                        "fitness": 1.2,
                        "genes": {"min_conf": 40, "risk_pct": 0.01, "allow_shorts": True},
                    }
                ]
            }
        }
    }
    rows = normalize_candidates(payload, "BTC/USDT")
    assert len(rows) == 1
    assert rows[0].symbol == "ETHUSDT"
    assert rows[0].params["min_conf"] == 40


def test_pine_export_smoke(tmp_path: Path) -> None:
    payload = json.loads(RESULTS_JSON.read_text(encoding="utf-8"))
    written = export_pines_from_payload(
        payload,
        tmp_path,
        template_id="eth_glintnews_pionex_v6",
        limit=1,
        target_symbol="ETH/USDT",
    )
    assert len(written) == 1
    body = Path(written[0]["path"]).read_text(encoding="utf-8")
    assert "strategy(" in body
    assert "initial_capital = 100" in body
    assert "percent_of_equity" in body
    assert "pyramiding = 1" in body
    assert "min_conf = input.int(35," in body
    assert "GA #" in body


def test_enforce_trading_invariants() -> None:
    stub = 'strategy(initial_capital = 10000, default_qty_type = strategy.fixed, pyramiding = 5)'
    out = enforce_trading_invariants(stub)
    assert "initial_capital = 100" in out
    assert "percent_of_equity" in out
    assert "pyramiding = 1" in out


def test_tiny_ga_on_eth_fixture() -> None:
    if not ETH_SAMPLE.exists():
        pytest.skip("ETH sample fixture missing")
    rows = json.loads(ETH_SAMPLE.read_text(encoding="utf-8"))
    candles = [
        Candle(
            int(r["timestamp"]),
            float(r["open"]),
            float(r["high"]),
            float(r["low"]),
            float(r["close"]),
            float(r["volume"]),
        )
        for r in rows
    ]
    # Need enough bars for EMA200 + split; pad by repeating if sample is short.
    while len(candles) < 300:
        base_ts = candles[-1].ts + 15 * 60_000
        for i, c in enumerate(candles[:50]):
            candles.append(Candle(base_ts + i * 15 * 60_000, c.o, c.h, c.low, c.c, c.v))
    pack = build_symbol_pack("ETHUSDT", candles[:400], 1_000_000.0)
    result = run_ga_optimize(
        {"ETHUSDT": pack},
        [("ETHUSDT", 1_000_000.0)],
        population=4,
        generations=2,
        elite=1,
        train_ratio=0.7,
        lookback_bars=400,
        max_symbols=1,
        seed=7,
    )
    assert "top3" in result
    assert len(result["top3"]) >= 1
    assert "genome" in result["top3"][0]
    assert "settings" in result
    g = result["top3"][0]["genome"]
    assert set(g) >= {
        "min_conf",
        "risk_pct",
        "sl_atr_mul",
        "tp_atr_mul",
        "vol_mult",
        "max_daily_move_pct",
        "ob_body_mult",
        "cisd_len",
        "w_trend",
        "w_cisd",
        "w_ob",
        "w_fvg",
        "w_vol",
        "allow_shorts",
    }


def test_ga_templates_endpoint(authenticated_user: None) -> None:
    client = TestClient(app)
    resp = client.get("/api/ga/templates")
    assert resp.status_code == 200
    data = resp.json()
    ids = {t["id"] for t in data["templates"]}
    assert "eth_glintnews_pionex_v6" in ids


def test_ga_export_pine_endpoint(authenticated_user: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.app.integrations.ga_optimizer import jobs as jobs_mod

    monkeypatch.setattr(jobs_mod, "default_ga_runs_dir", lambda settings=None: tmp_path)
    client = TestClient(app)
    payload = json.loads(RESULTS_JSON.read_text(encoding="utf-8"))
    resp = client.post(
        "/api/ga/export-pine",
        json={"results": payload, "template_id": "eth_glintnews_pionex_v6", "limit": 1},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["files"]
    assert Path(data["files"][0]["path"]).exists()


def test_app_imports_ga_router() -> None:
    from backend.app.main import app as fastapi_app
    from backend.app.routers import ga as ga_mod

    schema = fastapi_app.openapi()
    paths = schema.get("paths") or {}
    assert "/api/ga/optimize" in paths
    assert "/api/ga/templates" in paths
    assert ga_mod.router is not None
    assert len(ga_mod.router.routes) >= 5
