"""LTM Liquidity Trail Matrix analyzer (precision signal port)."""

from __future__ import annotations

from backend.app.integrations.backtest.ema_grid import run_candle_optimize, synthetic_candles
from backend.app.integrations.backtest.ltm_analyzer import analyze_ltm, is_ltm_strategy, optimize_ltm


def test_is_ltm_strategy_detection() -> None:
    assert is_ltm_strategy({"strategy": "ltm"})
    assert is_ltm_strategy({"scriptId": "ltm_willy_v130"})
    assert is_ltm_strategy({"pineName": "Liquidity Trail Matrix [WillyAlgoTrader]"})
    assert not is_ltm_strategy({"strategy": "ema_cross"})


def test_analyze_ltm_on_synthetic() -> None:
    candles = synthetic_candles("BTCUSD", n=320)
    result = analyze_ltm(
        candles,
        {
            "bandPreset": "Balanced",
            "flipBand": "Balanced (Band 3)",
            "minScore": 55,
            "riskPreset": "Balanced",
        },
    )
    assert result["success"] is True
    assert result["engine"] == "ltm_v1.3"
    assert "profitFactor" in result
    assert result["signalCount"] >= 0


def test_optimize_ltm_grid() -> None:
    candles = synthetic_candles("ETHUSD", n=280)
    opt = optimize_ltm(candles, min_trades=0, limit=24)
    assert opt["tested"] > 0
    assert opt["best"] is not None


def test_run_candle_optimize_dispatches_ltm() -> None:
    candles = synthetic_candles("SOLUSD", n=280)
    result = run_candle_optimize(
        {
            "strategy": "ltm",
            "symbol": "SOLUSD",
            "timeframe": "5m",
            "minTrades": 0,
            "primaryObjective": "profit_factor",
            "secondaryObjective": "percent_profitable",
            "parameters": {"bandPreset": "Scalping", "minScore": 55},
        },
        candles,
        candle_source="synthetic-ohlcv",
    )
    assert result["success"] is True
    assert "ltm" in result["source"]
    assert result["winner"] is not None
    assert "LTM" in result["bericht"]
