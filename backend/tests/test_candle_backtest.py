"""tv-extension-mvp candle EMA grid backtest (not vision)."""

from __future__ import annotations

from backend.app.integrations.backtest.ema_grid import (
    evaluate_ema_cross,
    optimize_ema_cross,
    run_candle_optimize,
    synthetic_candles,
)


def test_evaluate_ema_cross_on_synthetic() -> None:
    candles = synthetic_candles("ETHUSD", n=200)
    metrics = evaluate_ema_cross(
        candles,
        {"emaFast": 5, "emaSlow": 20, "takeProfitPct": 2.0, "stopLossPct": 1.0},
    )
    assert "profitFactor" in metrics
    assert "maxDrawdown" in metrics
    assert metrics["trades"] >= 0
    assert 0.0 <= metrics["winRate"] <= 100.0


def test_optimize_grid_finds_best() -> None:
    candles = synthetic_candles("BTCUSD", n=240)
    opt = optimize_ema_cross(candles, limit=80, min_trades=1)
    assert opt["tested"] > 0
    assert opt["best"] is not None
    assert "params" in opt["best"]


def test_run_candle_optimize_ui_shape() -> None:
    candles = synthetic_candles("SOLUSD", n=200)
    result = run_candle_optimize(
        {
            "strategy": "ema_cross",
            "symbol": "SOLUSD",
            "timeframe": "5m",
            "minTrades": 1,
            "primaryObjective": "profit_factor",
            "secondaryObjective": "percent_profitable",
        },
        candles,
        candle_source="synthetic-ohlcv",
    )
    assert result["success"] is True
    assert result["winner"]["trades"] >= 0
    assert "candle-backtest" in result["source"]
    assert "vision" not in result["bericht"].lower() or "not vision" in result["bericht"].lower()
