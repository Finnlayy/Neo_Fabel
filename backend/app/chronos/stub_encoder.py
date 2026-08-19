"""Deterministic linear stub encoder: OHLCVA_norm → R^20 until AE is trained.

Uses a fixed seeded projection (no torch). Not a substitute for the Kronos AE —
only unblocks tokenize API + Academy wiring.
"""

from __future__ import annotations

import hashlib
import struct
from collections.abc import Sequence

from backend.app.chronos.bsq import LATENT_DIM
from backend.app.chronos.normalize import OHLCVA_DIM

STUB_SEED = b"neo-fabel-chronos-stub-encoder-v1"


def _seeded_matrix(rows: int, cols: int) -> list[list[float]]:
    """Uniform[-1,1] matrix from SHA-256 stream — bit-stable across platforms."""
    out: list[list[float]] = []
    counter = 0
    buf = b""
    while len(out) < rows:
        row: list[float] = []
        while len(row) < cols:
            if len(buf) < 4:
                buf += hashlib.sha256(STUB_SEED + struct.pack(">I", counter)).digest()
                counter += 1
            chunk, buf = buf[:4], buf[4:]
            u = struct.unpack(">I", chunk)[0] / 0xFFFFFFFF
            row.append(u * 2.0 - 1.0)
        out.append(row)
    return out


_WEIGHTS = _seeded_matrix(LATENT_DIM, OHLCVA_DIM)  # 20 x 6
_BIAS = [row[0] * 0.01 for row in _seeded_matrix(LATENT_DIM, 1)]


def encode_bar(x_norm_row: Sequence[float]) -> list[float]:
    if len(x_norm_row) != OHLCVA_DIM:
        raise ValueError(f"expected {OHLCVA_DIM} features, got {len(x_norm_row)}")
    z: list[float] = []
    for i in range(LATENT_DIM):
        acc = _BIAS[i]
        w = _WEIGHTS[i]
        for j in range(OHLCVA_DIM):
            acc += w[j] * float(x_norm_row[j])
        z.append(acc)
    return z


def encode_window(x_norm: Sequence[Sequence[float]]) -> list[list[float]]:
    return [encode_bar(row) for row in x_norm]
