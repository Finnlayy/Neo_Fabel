"""Technical context for Chronos prompts — numpy/pandas (PineTS optional via pinets_bridge)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from backend.app.chronos.deps import require_pandas
from backend.app.chronos.frame import bars_to_dataframe


def _rsi_series(closes: Any, period: int = 14) -> Any:
    require_pandas()
    import pandas as pd

    delta = closes.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, pd.NA)
    return 100 - (100 / (1 + rs))


def _ema_series(values: Any, period: int) -> Any:
    return values.ewm(span=period, adjust=False).mean()


def _atr_series(high: Any, low: Any, close: Any, period: int = 14) -> Any:
    require_pandas()
    import pandas as pd

    prev_close = close.shift(1)
    tr = pd.concat(
        [
            (high - low).abs(),
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()


def compute_indicator_context(
    bars: Sequence[Sequence[float]],
    *,
    rsi_period: int = 14,
    ema_period: int = 21,
    atr_period: int = 14,
) -> dict[str, float | None]:
    """Latest RSI, EMA distance %, ATR % for Chronos / prompt snapshots."""
    if len(bars) < max(rsi_period, ema_period, atr_period) + 2:
        return {"rsi": None, "ema_distance_pct": None, "atr_pct": None}

    df = bars_to_dataframe(bars)
    close = df["close"]
    rsi = _rsi_series(close, rsi_period)
    ema = _ema_series(close, ema_period)
    atr = _atr_series(df["high"], df["low"], close, atr_period)

    last_close = float(close.iloc[-1])
    last_rsi = float(rsi.iloc[-1]) if rsi.iloc[-1] == rsi.iloc[-1] else None
    last_ema = float(ema.iloc[-1]) if ema.iloc[-1] == ema.iloc[-1] else None
    last_atr = float(atr.iloc[-1]) if atr.iloc[-1] == atr.iloc[-1] else None

    ema_dist = None
    if last_ema and last_ema != 0:
        ema_dist = round((last_close - last_ema) / last_ema * 100.0, 4)

    atr_pct = None
    if last_atr is not None and last_close > 0:
        atr_pct = round(last_atr / last_close * 100.0, 4)

    out_rsi = round(last_rsi, 2) if last_rsi is not None else None
    return {
        "rsi": out_rsi,
        "ema_distance_pct": ema_dist,
        "atr_pct": atr_pct,
    }


def indicators_available() -> bool:
    from backend.app.chronos.deps import chronos_deps_status

    st = chronos_deps_status()
    return bool(st["numpy"] and st["pandas"])
