"""Causal Z-score normalization for OHLCVA windows.

Caller must pass lookback-only windows — never mix prediction targets into μ/σ
(normalization leakage). Stats use population σ (ddof=0) and clip ±5.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from math import sqrt

OHLCVA_DIM = 6
DEFAULT_EPS = 1e-6
DEFAULT_CLIP = 5.0


@dataclass(frozen=True)
class NormalizeResult:
    """Normalized window plus denorm metadata (μ, σ per column)."""

    x_norm: list[list[float]]
    mean: list[float]
    std: list[float]
    lookback: int
    feature_order: tuple[str, ...] = ("open", "high", "low", "close", "volume", "amount")


class ChronosNormalizer:
    def __init__(self, eps: float = DEFAULT_EPS, clip_val: float = DEFAULT_CLIP) -> None:
        self.eps = eps
        self.clip = clip_val

    def normalize_window(self, x_raw: Sequence[Sequence[float]]) -> NormalizeResult:
        """Z-score over the provided lookback window only (causal if caller excludes future)."""
        rows = [list(map(float, row)) for row in x_raw]
        if not rows:
            raise ValueError("empty OHLCVA window")
        width = len(rows[0])
        if width != OHLCVA_DIM:
            raise ValueError(f"expected {OHLCVA_DIM} features (OHLCVA), got {width}")
        for i, row in enumerate(rows):
            if len(row) != OHLCVA_DIM:
                raise ValueError(f"row {i} has {len(row)} cols, expected {OHLCVA_DIM}")

        n = len(rows)
        mean = [0.0] * OHLCVA_DIM
        for row in rows:
            for j in range(OHLCVA_DIM):
                mean[j] += row[j]
        mean = [m / n for m in mean]

        # Population standard deviation (ddof=0).
        var = [0.0] * OHLCVA_DIM
        for row in rows:
            for j in range(OHLCVA_DIM):
                d = row[j] - mean[j]
                var[j] += d * d
        std = [sqrt(v / n) for v in var]

        x_norm: list[list[float]] = []
        for row in rows:
            out: list[float] = []
            for j in range(OHLCVA_DIM):
                v = (row[j] - mean[j]) / (std[j] + self.eps)
                if v > self.clip:
                    v = self.clip
                elif v < -self.clip:
                    v = -self.clip
                out.append(v)
            x_norm.append(out)

        return NormalizeResult(x_norm=x_norm, mean=mean, std=std, lookback=n)

    def denormalize(self, x_norm: Sequence[Sequence[float]], mean: Sequence[float], std: Sequence[float]) -> list[list[float]]:
        """Map normalized values back to raw scale using stored μ/σ."""
        if len(mean) != OHLCVA_DIM or len(std) != OHLCVA_DIM:
            raise ValueError("mean/std must be length 6 (OHLCVA)")
        out: list[list[float]] = []
        for row in x_norm:
            if len(row) != OHLCVA_DIM:
                raise ValueError(f"expected {OHLCVA_DIM} features, got {len(row)}")
            out.append([float(row[j]) * (float(std[j]) + self.eps) + float(mean[j]) for j in range(OHLCVA_DIM)])
        return out
