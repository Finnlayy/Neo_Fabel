"""ChronosPredictor — Kronos-style OHLCVA forecast → DataFrame (paper stub until decoder).

Mirrors KronosPredictor.predict: returns Open/High/Low/Close/Volume/Amount rows
in the original price scale (after denormalizing from causal Z-score space).
No live trading wiring.
"""

from __future__ import annotations

import hashlib
import math
import random
from dataclasses import dataclass
from typing import Any, Sequence

from backend.app.chronos.normalize import ChronosNormalizer, OHLCVA_DIM

FEATURE_COLS = ("open", "high", "low", "close", "volume", "amount")


@dataclass(frozen=True)
class PredictResult:
    """Forecast payload — DataFrame when pandas is installed, else list of row dicts."""

    pred_rows: list[dict[str, float]]
    history_rows: list[dict[str, float]]
    pred_len: int
    lookback: int
    sample_count: int
    temperature: float
    top_p: float
    encoder: str = "stub_momentum_v1"
    paper_only: bool = True

    def to_dataframe(self) -> Any:
        try:
            import pandas as pd
        except ImportError as exc:
            raise RuntimeError("pandas required for DataFrame export: pip install pandas") from exc
        return pd.DataFrame(self.pred_rows, columns=list(FEATURE_COLS))

    def history_dataframe(self) -> Any:
        try:
            import pandas as pd
        except ImportError as exc:
            raise RuntimeError("pandas required for DataFrame export: pip install pandas") from exc
        return pd.DataFrame(self.history_rows, columns=list(FEATURE_COLS))

    def to_dict(self) -> dict[str, Any]:
        return {
            "paper_only": True,
            "live_trading": False,
            "encoder": self.encoder,
            "lookback": self.lookback,
            "pred_len": self.pred_len,
            "sample_count": self.sample_count,
            "T": self.temperature,
            "top_p": self.top_p,
            "columns": list(FEATURE_COLS),
            "pred": self.pred_rows,
            "history": self.history_rows,
        }


def _rows_from_bars(bars: Sequence[Sequence[float]]) -> list[dict[str, float]]:
    out: list[dict[str, float]] = []
    for row in bars:
        if len(row) != OHLCVA_DIM:
            raise ValueError(f"expected {OHLCVA_DIM} OHLCVA cols, got {len(row)}")
        out.append({FEATURE_COLS[i]: float(row[i]) for i in range(OHLCVA_DIM)})
    return out


def _seed_from_bars(bars: Sequence[Sequence[float]], salt: int = 0) -> int:
    h = hashlib.sha256()
    h.update(str(salt).encode())
    for row in bars[-32:]:
        for v in row:
            h.update(f"{float(v):.8f}".encode())
    return int.from_bytes(h.digest()[:8], "big")


def _enforce_ohlc(o: float, h: float, l: float, c: float) -> tuple[float, float, float, float]:
    body_hi = max(o, c)
    body_lo = min(o, c)
    h = max(h, body_hi)
    l = min(l, body_lo)
    if h < l:
        h, l = l, h
    return o, h, l, c


class ChronosPredictor:
    """Phase-1 stub predictor (momentum + MC noise). Replace with decoder in Phase 3."""

    def __init__(
        self,
        *,
        max_context: int = 512,
        eps: float = 1e-6,
        clip_val: float = 5.0,
    ) -> None:
        self.max_context = max_context
        self.eps = eps
        self.clip_val = clip_val
        self.normalizer = ChronosNormalizer(eps=eps, clip_val=clip_val)

    def predict(
        self,
        bars: Sequence[Sequence[float]],
        *,
        pred_len: int = 32,
        temperature: float = 1.0,
        top_p: float = 0.9,
        sample_count: int = 1,
    ) -> PredictResult:
        if pred_len < 1 or pred_len > 512:
            raise ValueError("pred_len must be in [1, 512]")
        if sample_count < 1 or sample_count > 64:
            raise ValueError("sample_count must be in [1, 64]")
        if not (0.0 < top_p <= 1.0):
            raise ValueError("top_p must be in (0, 1]")
        if temperature <= 0:
            raise ValueError("temperature must be > 0")

        history = [list(map(float, r)) for r in bars]
        if len(history) < 2:
            raise ValueError("need at least 2 lookback bars")
        if len(history) > self.max_context:
            history = history[-self.max_context :]

        # Causal stats from lookback only (no leakage into forecast horizon).
        self.normalizer.normalize_window(history)

        paths = [
            self._sample_path(history, pred_len, temperature, top_p, path_i)
            for path_i in range(sample_count)
        ]
        # Kronos averages sample_count paths for the point forecast DataFrame.
        pred_bars = self._mean_path(paths)
        return PredictResult(
            pred_rows=_rows_from_bars(pred_bars),
            history_rows=_rows_from_bars(history),
            pred_len=pred_len,
            lookback=len(history),
            sample_count=sample_count,
            temperature=temperature,
            top_p=top_p,
        )

    def predict_paths(
        self,
        bars: Sequence[Sequence[float]],
        *,
        pred_len: int = 32,
        temperature: float = 1.0,
        top_p: float = 0.9,
        sample_count: int = 30,
    ) -> tuple[PredictResult, list[list[list[float]]]]:
        """Return mean forecast + raw Monte Carlo OHLCVA paths for band plots."""
        result = self.predict(
            bars,
            pred_len=pred_len,
            temperature=temperature,
            top_p=top_p,
            sample_count=sample_count,
        )
        history = [list(map(float, r)) for r in bars]
        if len(history) > self.max_context:
            history = history[-self.max_context :]
        paths = [
            self._sample_path(history, pred_len, temperature, top_p, path_i)
            for path_i in range(sample_count)
        ]
        return result, paths

    def _sample_path(
        self,
        history: list[list[float]],
        pred_len: int,
        temperature: float,
        top_p: float,
        path_i: int,
    ) -> list[list[float]]:
        rng = random.Random(_seed_from_bars(history, salt=path_i + 1))
        closes = [r[3] for r in history]
        vols = [max(r[4], 0.0) for r in history]
        # Recent log-return mean / vol (clipped window).
        rets: list[float] = []
        for i in range(1, len(closes)):
            if closes[i - 1] > 0:
                rets.append(math.log(max(closes[i], 1e-12) / closes[i - 1]))
        window = rets[-min(64, len(rets)) :] or [0.0]
        mu = sum(window) / len(window)
        var = sum((x - mu) ** 2 for x in window) / len(window)
        sigma = math.sqrt(max(var, 1e-12))
        # Nucleus-style temperature scaling on noise.
        noise_scale = sigma * temperature * (0.5 + 0.5 * top_p)

        last = history[-1][:]
        path: list[list[float]] = []
        price = last[3]
        vol = max(last[4], 1.0)
        amt = max(last[5], vol * price)

        for _ in range(pred_len):
            shock = rng.gauss(mu, noise_scale)
            # Occasional larger jump (leptokurtic stub).
            if rng.random() > top_p:
                shock += rng.gauss(0.0, noise_scale * 2.5)
            nxt = price * math.exp(shock)
            o = price
            c = nxt
            wick = abs(c - o) * (0.15 + 0.85 * rng.random())
            h = max(o, c) + wick * rng.random()
            l = min(o, c) - wick * rng.random()
            o, h, l, c = _enforce_ohlc(o, h, l, c)
            vol_shock = math.exp(rng.gauss(0.0, 0.08 * temperature))
            vol = max(vol * vol_shock, 0.0)
            typical = (o + h + l + c) / 4.0
            amt = vol * typical
            path.append([o, h, l, c, vol, amt])
            price = c
        return path

    @staticmethod
    def _mean_path(paths: list[list[list[float]]]) -> list[list[float]]:
        n = len(paths[0])
        out: list[list[float]] = []
        for t in range(n):
            cols = [0.0] * OHLCVA_DIM
            for path in paths:
                for j in range(OHLCVA_DIM):
                    cols[j] += path[t][j]
            cols = [v / len(paths) for v in cols]
            o, h, l, c = _enforce_ohlc(cols[0], cols[1], cols[2], cols[3])
            out.append([o, h, l, c, cols[4], cols[5]])
        return out
