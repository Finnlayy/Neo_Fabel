"""OHLCVA ↔ pandas/numpy — Chronos data frame helpers (paper only)."""

from __future__ import annotations

from typing import Any, Sequence

from backend.app.chronos.deps import require_numpy, require_pandas
from backend.app.chronos.normalize import OHLCVA_DIM
from backend.app.chronos.predictor import FEATURE_COLS


def bars_to_dataframe(bars: Sequence[Sequence[float]]) -> Any:
    """Return pandas DataFrame with OHLCVA columns."""
    require_pandas()
    import pandas as pd

    rows = [list(map(float, r)) for r in bars]
    for i, row in enumerate(rows):
        if len(row) != OHLCVA_DIM:
            raise ValueError(f"row {i}: expected {OHLCVA_DIM} cols, got {len(row)}")
    return pd.DataFrame(rows, columns=list(FEATURE_COLS))


def bars_to_numpy(bars: Sequence[Sequence[float]]) -> Any:
    """Return float64 ndarray shape (L, 6)."""
    require_numpy()
    import numpy as np

    rows = [list(map(float, r)) for r in bars]
    for i, row in enumerate(rows):
        if len(row) != OHLCVA_DIM:
            raise ValueError(f"row {i}: expected {OHLCVA_DIM} cols, got {len(row)}")
    return np.asarray(rows, dtype=np.float64)


def dataframe_to_bars(df: Any) -> list[list[float]]:
    """Serialize DataFrame back to OHLCVA row lists."""
    require_pandas()
    cols = list(FEATURE_COLS)
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise ValueError(f"dataframe missing columns: {missing}")
    out: list[list[float]] = []
    for _, row in df[cols].iterrows():
        out.append([float(row[c]) for c in cols])
    return out
