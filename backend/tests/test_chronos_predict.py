"""ChronosPredictor + Kronos-style matplotlib prediction plots."""

from __future__ import annotations

import math

import pytest
from fastapi.testclient import TestClient

from backend.app.auth import require_user
from backend.app.chronos.plot_prediction import plot_prediction, plot_prediction_monte_carlo
from backend.app.chronos.predictor import ChronosPredictor, FEATURE_COLS
from backend.app.main import app

client = TestClient(app)


@pytest.fixture
def authenticated_user() -> None:
    app.dependency_overrides[require_user] = lambda: {
        "uid": "chronos-pred-test",
        "email_verified": True,
        "firebase": {"sign_in_provider": "google.com"},
    }
    yield
    app.dependency_overrides.pop(require_user, None)


def _synthetic_ohlcva(n: int = 48) -> list[list[float]]:
    bars: list[list[float]] = []
    price = 100.0
    for i in range(n):
        o = price
        c = price * (1.0 + 0.001 * math.sin(i / 3.0))
        h = max(o, c) * 1.002
        l = min(o, c) * 0.998
        v = 1000.0 + 10.0 * i
        a = v * ((o + c) / 2.0)
        bars.append([o, h, l, c, v, a])
        price = c
    return bars


def test_predictor_returns_ohlcva_rows() -> None:
    bars = _synthetic_ohlcva(40)
    result = ChronosPredictor().predict(bars, pred_len=12, sample_count=3)
    assert result.pred_len == 12
    assert len(result.pred_rows) == 12
    assert set(result.pred_rows[0]) == set(FEATURE_COLS)
    # OHLC inequality
    row = result.pred_rows[0]
    assert row["low"] <= min(row["open"], row["close"])
    assert row["high"] >= max(row["open"], row["close"])


def test_predictor_dataframe_optional() -> None:
    pytest.importorskip("pandas")
    bars = _synthetic_ohlcva(20)
    df = ChronosPredictor().predict(bars, pred_len=5).to_dataframe()
    assert list(df.columns) == list(FEATURE_COLS)
    assert len(df) == 5


def test_plot_prediction_png() -> None:
    pytest.importorskip("matplotlib")
    bars = _synthetic_ohlcva(30)
    pred = ChronosPredictor().predict(bars, pred_len=8)
    png = plot_prediction(pred.history_rows, pred.pred_rows, include_volume=True)
    assert isinstance(png, str)
    assert len(png) > 100


def test_plot_monte_carlo_png() -> None:
    pytest.importorskip("matplotlib")
    bars = _synthetic_ohlcva(30)
    pred, paths = ChronosPredictor().predict_paths(bars, pred_len=8, sample_count=10)
    png = plot_prediction_monte_carlo(pred.history_rows, paths, mean_pred_rows=pred.pred_rows)
    assert len(png) > 100


def test_api_predict(authenticated_user: None) -> None:
    pytest.importorskip("matplotlib")
    bars = _synthetic_ohlcva(24)
    res = client.post(
        "/api/v1/chronos/predict",
        json={
            "bars": bars,
            "pred_len": 10,
            "T": 1.0,
            "top_p": 0.9,
            "monte_carlo": True,
            "mc_samples": 8,
            "include_volume": True,
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["paper_only"] is True
    assert body["live_trading"] is False
    assert len(body["pred"]) == 10
    assert body["columns"] == list(FEATURE_COLS)
    assert body["charts"]["prediction"].startswith("data:image/png;base64,")
    assert body["charts"]["monte_carlo"].startswith("data:image/png;base64,")
