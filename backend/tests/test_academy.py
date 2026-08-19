"""Academy training API + core services (paper/synthetic only)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.academy.agent_defs import (
    ACADEMY_TRAINABLE_NAMES,
    NEO_AGENT_NAMES,
    TRADING_AGENT_NAMES,
)
from backend.app.academy.blind_patterns import BlindCandle, make_pattern_scenario, scan_blind_patterns
from backend.app.academy.paths import ACADEMY_DATA_DIR
from backend.app.academy.training_drills import training_drills
from backend.app.academy.training_loop import training_loop
from backend.app.auth import require_user
from backend.app.main import app
from backend.app.settings import get_settings

client = TestClient(app)


@pytest.fixture
def authenticated_user() -> None:
    app.dependency_overrides[require_user] = lambda: {
        "uid": "academy-test-user",
        "email_verified": True,
        "firebase": {"sign_in_provider": "google.com"},
    }
    yield
    app.dependency_overrides.pop(require_user, None)


def test_neo_agents_mapped() -> None:
    from backend.app.academy.agent_defs import get_agent_definition

    assert "orchestrator" in NEO_AGENT_NAMES
    assert "rna_smart" in NEO_AGENT_NAMES
    assert "risk_gov" in NEO_AGENT_NAMES
    assert "kraken_broker" in NEO_AGENT_NAMES
    assert "chronos" in NEO_AGENT_NAMES
    orch = get_agent_definition("orchestrator")
    assert orch is not None
    assert orch.drill_type == "orchestration_teamwork"
    assert orch.trades is False
    assert orch.academy_train is False
    chronos = get_agent_definition("chronos")
    assert chronos is not None
    assert chronos.drill_type == "kline_language"
    assert chronos.trades is True
    assert chronos.academy_train is False  # self-taught — not Academy auto-drilled
    # Auto-train subset: trading path minus Chronos / meta / briefing.
    assert "orchestrator" not in TRADING_AGENT_NAMES
    assert "analytic" not in TRADING_AGENT_NAMES
    assert "chronos" in TRADING_AGENT_NAMES
    assert "chronos" not in ACADEMY_TRAINABLE_NAMES
    assert "kraken_broker" in ACADEMY_TRAINABLE_NAMES
    assert "rna_smart" in ACADEMY_TRAINABLE_NAMES
    assert set(ACADEMY_TRAINABLE_NAMES).issubset(set(TRADING_AGENT_NAMES))
    assert set(TRADING_AGENT_NAMES).issubset(set(NEO_AGENT_NAMES))


def test_chronos_kline_drill() -> None:
    drill = training_drills.generate_random_drill("chronos", difficulty=2)
    assert drill.drill_type == "kline_language"
    assert drill.scenario_data.get("mode") == "chronos_kline"
    assert "bars_ohlcva" in drill.scenario_data
    assert "hint_tokens" in drill.scenario_data
    assert "forecast" in drill.scenario_data
    assert drill.expected_outcome in {"PROCEED", "REJECT", "CHOP"}
    assert "actions" in drill.scenario_data


def test_kraken_broker_execution_drill() -> None:
    drill = training_drills.generate_random_drill("kraken_broker", difficulty=2)
    assert drill.drill_type == "paper_execution"
    assert drill.scenario_data.get("venue") == "local_paper"
    assert "metrics" in drill.scenario_data
    assert drill.expected_outcome in {"ACCEPT_FILL", "REJECT_FILL", "REQUOTE"}


def test_market_tape_and_risk_policy_drills() -> None:
    tape = training_drills.generate_random_drill("market_data", difficulty=1)
    assert tape.drill_type == "market_tape"
    assert tape.scenario_data.get("mode") == "market_tape"
    assert tape.expected_outcome in {"FRESH", "STALE", "INCOMPLETE", "REJECT"}
    assert tape.scenario_data.get("data_provenance", {}).get("primary") == "fixture"

    risk = training_drills.generate_random_drill("risk_gov", difficulty=2)
    assert risk.drill_type == "risk_policy"
    assert risk.expected_outcome in {"ALLOW_PAPER", "BLOCK", "REDUCE_SIZE", "FORCE_FLAT"}
    from backend.app.academy.drill_scenarios import resolve_risk_policy_expected

    computed = resolve_risk_policy_expected(risk.scenario_data["policy"], risk.scenario_data["state"])
    assert computed == str(risk.expected_outcome).upper()


def test_analytic_adaptive_regime_drills() -> None:
    brief = training_drills.generate_random_drill("analytic", difficulty=1)
    assert brief.drill_type == "market_brief"
    adapt = training_drills.generate_random_drill("adaptive", difficulty=2)
    assert adapt.drill_type == "param_adapt"
    regime = training_drills.generate_random_drill("predictive", difficulty=1)
    assert regime.drill_type == "regime_forecast"
    orch = training_drills.generate_random_drill("orchestrator", difficulty=1)
    assert orch.drill_type == "orchestration_teamwork"
    assert "ESCALATE" in (orch.scenario_data.get("actions") or [])


@pytest.mark.asyncio
async def test_chronos_drill_evaluate() -> None:
    drill = training_drills.generate_random_drill("chronos", difficulty=1)
    result = await training_drills.evaluate_drill(
        drill, str(drill.expected_outcome), 0.9, persist=True
    )
    assert result.is_correct is True
    assert result.scout_name == "chronos"


@pytest.mark.asyncio
async def test_evaluate_rejects_illegal_action() -> None:
    from fastapi import HTTPException

    drill = training_drills.generate_random_drill("market_data", difficulty=1)
    with pytest.raises(HTTPException) as excinfo:
        await training_drills.evaluate_drill(drill, "PROCEED", 0.9, persist=False)
    assert excinfo.value.status_code == 400


@pytest.mark.asyncio
async def test_drill_market_fixture_fallback() -> None:
    from backend.app.academy.drill_market import fetch_drill_candles, resolve_academy_source
    from backend.app.settings import get_settings

    assert resolve_academy_source(get_settings()) == "fixture"
    candles, prov = await fetch_drill_candles("BTCUSD", count=20)
    assert len(candles) == 20
    assert prov["primary"] == "fixture"

def test_blind_pattern_bullish_engulfing() -> None:
    candles, expected = make_pattern_scenario("bullish")
    assert expected == "PROCEED"
    assert len(candles) >= 2
    parsed = [BlindCandle(**c) for c in candles]
    hits = scan_blind_patterns(parsed)
    assert any(h.bias == "bullish" for h in hits)


@pytest.mark.asyncio
async def test_pattern_drill_for_rna() -> None:
    drill = training_drills.generate_random_drill("rna_smart", difficulty=1)
    assert drill.drill_type == "pattern_recognition"
    assert drill.scenario_data.get("mode") == "blind_geometry"
    assert "candles" in drill.scenario_data
    result = await training_drills.evaluate_drill(
        drill, str(drill.expected_outcome), 0.9, persist=True
    )
    assert result.is_correct is True


def test_academy_status_loopback_dev_bypass(monkeypatch: pytest.MonkeyPatch) -> None:
    """The loopback bypass is available only in an explicitly isolated dev configuration."""
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("AUTH_DEV_BYPASS", "true")
    get_settings.cache_clear()
    try:
        res = client.get("/api/v1/academy/status")
        assert res.status_code == 200
        assert res.json()["paper_only"] is True
    finally:
        get_settings.cache_clear()


def test_academy_status_rejects_loopback_without_dev_bypass(monkeypatch: pytest.MonkeyPatch) -> None:
    """Production must never accept an unauthenticated loopback request."""
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("AUTH_DEV_BYPASS", "false")
    get_settings.cache_clear()
    try:
        res = client.get("/api/v1/academy/status")
        assert res.status_code == 401
    finally:
        get_settings.cache_clear()


def test_agency_roster(authenticated_user: None) -> None:
    res = client.get("/api/v1/academy/agency/roster")
    assert res.status_code == 200
    body = res.json()
    assert body["paper_only"] is True
    assert body["agency"] == "Neo Fabel Agency"
    ids = {a["id"] for a in body["agents"]}
    assert "chronos" in ids
    assert "orchestrator" in ids
    chronos = next(a for a in body["agents"] if a["id"] == "chronos")
    assert chronos["profession"]
    assert chronos["agenda"]
    assert chronos["lifetask"]
    assert chronos["level"] >= 1
    assert chronos.get("trades") is True
    assert chronos.get("academy_train") is False
    orch = next(a for a in body["agents"] if a["id"] == "orchestrator")
    assert orch.get("trades") is False
    assert orch.get("academy_train") is False
    assert "confidence" in chronos
    assert "experience" in chronos


def test_academy_registry_and_cycle(authenticated_user: None) -> None:
    status = client.get("/api/v1/academy/status")
    assert status.status_code == 200
    body = status.json()
    assert body["paper_only"] is True
    assert body.get("train_trading_only") is True
    assert "kraken_broker" in body["agents"]
    assert "orchestrator" not in body["agents"]
    assert "chronos" not in body["agents"]  # self-taught
    assert "orchestrator" in body.get("agents_all", [])
    assert "chronos" in body.get("agents_all", [])

    registry = client.get("/api/v1/academy/agents/registry")
    assert registry.status_code == 200
    names = {a["name"] for a in registry.json()["agents"]}
    assert names >= set(NEO_AGENT_NAMES)

    before = training_loop.cycles_completed
    cycle = client.post("/api/v1/academy/train/cycle")
    assert cycle.status_code == 200
    assert cycle.json()["ok"] is True
    assert training_loop.cycles_completed == before + 1

    drills = client.get("/api/v1/academy/drills/available", params={"scout_name": "rna_smart", "count": 2})
    assert drills.status_code == 200
    payload = drills.json()["drills"]
    assert len(payload) == 2
    drill = payload[0]
    evaluate = client.post(
        "/api/v1/academy/drill/evaluate",
        json={
            "drill": drill,
            "scout_decision": drill["expected_outcome"],
            "confidence": 0.8,
        },
    )
    assert evaluate.status_code == 200
    assert evaluate.json()["is_correct"] is True

    board = client.get("/api/v1/academy/agents/leaderboard")
    assert board.status_code == 200
    assert len(board.json()["leaderboard"]) >= len(NEO_AGENT_NAMES)


def _file_size(path: Path) -> int:
    return path.stat().st_size if path.exists() else 0


def test_train_cycle_writes_drill_and_career_logs(authenticated_user: None) -> None:
    drills_path = ACADEMY_DATA_DIR / "drill_results.jsonl"
    careers_path = ACADEMY_DATA_DIR / "agent_careers.jsonl"
    before_drills = _file_size(drills_path)
    before_careers = _file_size(careers_path)

    res = client.post("/api/v1/academy/train/cycle")
    assert res.status_code == 200
    assert res.json()["ok"] is True

    assert _file_size(drills_path) > before_drills
    assert _file_size(careers_path) > before_careers
    # One prediction_result line per trading agent in the cycle (not meta roles).
    # Slice by bytes (st_size), not str indices — JSONL may contain multi-byte UTF-8.
    new_career_bytes = careers_path.read_bytes()[before_careers:].decode("utf-8", errors="replace")
    assert new_career_bytes.count('"prediction_result"') >= len(ACADEMY_TRAINABLE_NAMES)
