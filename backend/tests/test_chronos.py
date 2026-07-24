"""Chronos Phase-1 substrate tests (normalize + BSQ + API)."""

from __future__ import annotations

import math

import pytest
from fastapi.testclient import TestClient

from backend.app.auth import require_user
from backend.app.chronos.bsq import BinarySphericalQuantizer, pack_bits_lsb
from backend.app.chronos.normalize import ChronosNormalizer
from backend.app.chronos.pipeline import tokenize_ohlcva
from backend.app.main import app


client = TestClient(app)


@pytest.fixture
def authenticated_user() -> None:
    app.dependency_overrides[require_user] = lambda: {
        "uid": "chronos-test-user",
        "email_verified": True,
        "firebase": {"sign_in_provider": "google.com"},
    }
    yield
    app.dependency_overrides.pop(require_user, None)


def _synthetic_ohlcva(n: int = 32) -> list[list[float]]:
    bars: list[list[float]] = []
    price = 100.0
    for i in range(n):
        o = price
        c = price * (1.0 + 0.001 * math.sin(i / 3.0))
        h = max(o, c) * 1.002
        low = min(o, c) * 0.998
        v = 1000.0 + 10.0 * i
        a = v * ((o + c) / 2.0)
        bars.append([o, h, low, c, v, a])
        price = c
    return bars


def test_population_zscore_and_clip() -> None:
    bars = [[1.0, 2.0, 0.5, 1.5, 10.0, 15.0], [3.0, 4.0, 2.0, 3.5, 20.0, 70.0]]
    result = ChronosNormalizer().normalize_window(bars)
    assert result.lookback == 2
    assert len(result.mean) == 6
    # Population σ for opens: mean=2, values 1 and 3 → σ=1
    assert abs(result.mean[0] - 2.0) < 1e-9
    assert abs(result.std[0] - 1.0) < 1e-9
    assert abs(result.x_norm[0][0] - (-1.0)) < 1e-6
    assert abs(result.x_norm[1][0] - 1.0) < 1e-6


def test_denormalize_roundtrip() -> None:
    bars = _synthetic_ohlcva(16)
    normer = ChronosNormalizer()
    result = normer.normalize_window(bars)
    back = normer.denormalize(result.x_norm, result.mean, result.std)
    for i in range(len(bars)):
        for j in range(6):
            assert abs(back[i][j] - bars[i][j]) < 1e-6


def test_bsq_sign_shortcut_and_roundtrip() -> None:
    z = [0.1, -0.2, 0.3, -0.4, 0.5, -0.6, 0.7, -0.8, 0.9, -1.0, 1.1, -1.2, 1.3, -1.4, 1.5, -1.6, 1.7, -1.8, 1.9, 0.0]
    q = BinarySphericalQuantizer()
    enc = q.encode(z)
    assert 0 <= enc.s1_id <= 1023
    assert 0 <= enc.s2_id <= 1023
    # Zero maps to bit 1 (sign convention).
    assert enc.bits[-1] == 1
    recon = q.decode(enc.s1_id, enc.s2_id)
    assert len(recon) == 20
    scale = 1.0 / math.sqrt(20)
    for i, bit in enumerate(enc.bits):
        expected = (1.0 if bit else -1.0) * scale
        assert abs(recon[i] - expected) < 1e-9


def test_pack_bits_lsb() -> None:
    assert pack_bits_lsb([1, 0, 1]) == 0b101
    assert pack_bits_lsb([0] * 10) == 0
    assert pack_bits_lsb([1] * 10) == 1023


def test_tokenize_deterministic() -> None:
    bars = _synthetic_ohlcva(24)
    a = tokenize_ohlcva(bars)
    b = tokenize_ohlcva(bars)
    assert a.s1_ids == b.s1_ids
    assert a.s2_ids == b.s2_ids
    assert len(a.s1_ids) == 24
    assert all(0 <= x <= 1023 for x in a.s1_ids + a.s2_ids)


def test_chronos_agent_registered() -> None:
    from backend.app.academy.agent_defs import NEO_AGENT_NAMES, get_agent_definition

    assert "chronos" in NEO_AGENT_NAMES
    defn = get_agent_definition("chronos")
    assert defn is not None
    assert defn.drill_type == "kline_language"


def test_api_status_and_tokenize(authenticated_user: None) -> None:
    status = client.get("/api/v1/chronos/status")
    assert status.status_code == 200
    body = status.json()
    assert body["paper_only"] is True
    assert body["live_trading"] is False
    assert body["phase"] == 1
    assert "pipeline_status" in body
    assert "lookback tokenize" in body["pipeline_status"].lower()
    assert "deps" in body
    assert "numpy" in body["deps"]
    assert "torch" in body["deps"]
    assert "vectorbt" in body["deps"]
    assert "pinets_cli" in body["deps"]

    bars = _synthetic_ohlcva(8)
    tok = client.post("/api/v1/chronos/tokenize", json={"bars": bars})
    assert tok.status_code == 200
    payload = tok.json()
    assert payload["paper_only"] is True
    assert len(payload["s1_ids"]) == 8
    assert payload["vocab"]["coarse"] == 1024

    bad = client.post("/api/v1/chronos/tokenize", json={"bars": [[1.0, 2.0]]})
    assert bad.status_code in (400, 422)


def test_api_matplotlib_charts(authenticated_user: None) -> None:
    pytest.importorskip("matplotlib")
    bars = _synthetic_ohlcva(16)
    res = client.post(
        "/api/v1/chronos/charts",
        json={"bars": bars, "include_tokens": True},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["paper_only"] is True
    assert body["renderer"] == "matplotlib"
    assert body["charts"]["ohlc"].startswith("data:image/png;base64,")
    assert body["charts"]["zscore"].startswith("data:image/png;base64,")
    assert body["charts"]["tokens"].startswith("data:image/png;base64,")
    assert body["charts"]["token_hist"].startswith("data:image/png;base64,")

