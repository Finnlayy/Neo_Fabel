"""Chronos optional stack — deps, frame, indicators (no vectorbt/torch required)."""

from __future__ import annotations

import math

import pytest

from backend.app.chronos.deps import chronos_deps_status, pinets_cli_available
from backend.app.chronos.indicators import compute_indicator_context, indicators_available


def _synthetic_ohlcva(n: int = 48) -> list[list[float]]:
    bars: list[list[float]] = []
    price = 100.0
    for i in range(n):
        o = price
        c = price * (1.0 + 0.002 * math.sin(i / 4.0))
        h = max(o, c) * 1.003
        low = min(o, c) * 0.997
        v = 1000.0 + 10.0 * i
        a = v * ((o + c) / 2.0)
        bars.append([o, h, low, c, v, a])
        price = c
    return bars


def test_chronos_deps_status_shape() -> None:
    st = chronos_deps_status()
    for key in ("numpy", "pandas", "matplotlib", "torch", "vectorbt", "pinets_cli", "research_ready"):
        assert key in st
    assert isinstance(st["install_hint"], str)
    assert isinstance(st["pinets_hint"], str)


def test_pinets_cli_is_path_check() -> None:
    # Boolean only — CI may or may not have npm pinets-cli installed.
    assert isinstance(pinets_cli_available(), bool)


def test_bars_to_dataframe_roundtrip() -> None:
    pytest.importorskip("pandas")
    pytest.importorskip("numpy")
    from backend.app.chronos.frame import bars_to_dataframe, bars_to_numpy, dataframe_to_bars

    bars = _synthetic_ohlcva(12)
    df = bars_to_dataframe(bars)
    assert len(df) == 12
    assert list(df.columns) == ["open", "high", "low", "close", "volume", "amount"]

    arr = bars_to_numpy(bars)
    assert arr.shape == (12, 6)

    back = dataframe_to_bars(df)
    for i, row in enumerate(bars):
        for j, val in enumerate(row):
            assert abs(back[i][j] - val) < 1e-9


def test_indicator_context() -> None:
    if not indicators_available():
        pytest.skip("numpy/pandas not installed")
    ctx = compute_indicator_context(_synthetic_ohlcva(64))
    assert ctx["rsi"] is not None
    assert 0 <= ctx["rsi"] <= 100
    assert ctx["ema_distance_pct"] is not None
    assert ctx["atr_pct"] is not None


def test_vectorbt_backtest_optional() -> None:
    pytest.importorskip("vectorbt")
    from backend.app.chronos.vectorbt_eval import simple_momentum_backtest_summary

    summary = simple_momentum_backtest_summary(_synthetic_ohlcva(80))
    assert summary["paper_only"] is True
    assert "total_return_pct" in summary
    assert summary["trades"] >= 0
