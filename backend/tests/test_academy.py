"""Academy training API + core services (paper/synthetic only)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.app.academy.agent_defs import NEO_AGENT_NAMES
from backend.app.academy.blind_patterns import make_pattern_scenario, scan_blind_patterns, BlindCandle
from backend.app.academy.training_drills import training_drills
from backend.app.academy.training_loop import training_loop
from backend.app.auth import require_user
from backend.app.main import app


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
    assert "orchestrator" in NEO_AGENT_NAMES
    assert "rna_smart" in NEO_AGENT_NAMES
    assert "risk_gov" in NEO_AGENT_NAMES
    assert "kraken_broker" in NEO_AGENT_NAMES


def test_kraken_broker_execution_drill() -> None:
    drill = training_drills.generate_random_drill("kraken_broker", difficulty=2)
    assert drill.drill_type == "execution_quality"
    assert drill.scenario_data.get("venue") == "kraken_broker"
    assert "slippage_bps" in drill.scenario_data


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


def test_academy_status_loopback_dev_bypass() -> None:
    # AUTH_DEV_BYPASS allows loopback TestClient without Bearer.
    res = client.get("/api/v1/academy/status")
    assert res.status_code == 200
    assert res.json()["paper_only"] is True


def test_academy_registry_and_cycle(authenticated_user: None) -> None:
    status = client.get("/api/v1/academy/status")
    assert status.status_code == 200
    body = status.json()
    assert body["paper_only"] is True
    assert "orchestrator" in body["agents"]

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
