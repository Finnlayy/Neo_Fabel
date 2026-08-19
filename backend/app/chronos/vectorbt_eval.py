"""Optional vectorbt research helpers — paper backtest on close series (no live orders)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from backend.app.chronos.deps import require_vectorbt
from backend.app.chronos.frame import bars_to_dataframe


def vectorbt_available() -> bool:
    from backend.app.chronos.deps import chronos_deps_status

    return bool(chronos_deps_status()["vectorbt"])


def simple_momentum_backtest_summary(
    bars: Sequence[Sequence[float]],
    *,
    fast: int = 8,
    slow: int = 21,
) -> dict[str, Any]:
    """EMA-cross long-only sanity check on Chronos lookback (research metric only)."""
    require_vectorbt()
    import vectorbt as vbt

    df = bars_to_dataframe(bars)
    close = df["close"]
    if len(close) < slow + 2:
        raise ValueError("insufficient bars for vectorbt eval")

    fast_ma = close.rolling(fast).mean()
    slow_ma = close.rolling(slow).mean()
    entries = fast_ma > slow_ma
    exits = fast_ma < slow_ma

    pf = vbt.Portfolio.from_signals(close, entries, exits, init_cash=10_000.0, freq="1h")
    stats = pf.stats()
    return {
        "paper_only": True,
        "strategy": f"ema_cross_{fast}_{slow}",
        "total_return_pct": float(stats.get("Total Return [%]", 0) or 0),
        "sharpe": float(stats.get("Sharpe Ratio", 0) or 0),
        "max_drawdown_pct": float(stats.get("Max Drawdown [%]", 0) or 0),
        "trades": int(stats.get("Total Trades", 0) or 0),
    }
