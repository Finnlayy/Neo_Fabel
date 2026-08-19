"""End-to-end Chronos tokenize: causal Z-score → stub AE → BSQ coarse/fine."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from backend.app.chronos.bsq import BinarySphericalQuantizer
from backend.app.chronos.normalize import ChronosNormalizer, NormalizeResult
from backend.app.chronos.stub_encoder import encode_window


@dataclass(frozen=True)
class TokenizeResult:
    normalize: NormalizeResult
    s1_ids: list[int]
    s2_ids: list[int]
    entropy_mean: float
    encoder: str = "stub_linear_v1"
    paper_only: bool = True


def tokenize_ohlcva(
    x_raw: Sequence[Sequence[float]],
    *,
    eps: float = 1e-6,
    clip_val: float = 5.0,
) -> TokenizeResult:
    normalizer = ChronosNormalizer(eps=eps, clip_val=clip_val)
    norm = normalizer.normalize_window(x_raw)
    z_seq = encode_window(norm.x_norm)
    quantizer = BinarySphericalQuantizer()
    encoded = quantizer.encode_sequence(z_seq)
    s1 = [e.s1_id for e in encoded]
    s2 = [e.s2_id for e in encoded]
    entropy_mean = sum(e.entropy_loss for e in encoded) / max(len(encoded), 1)
    return TokenizeResult(
        normalize=norm,
        s1_ids=s1,
        s2_ids=s2,
        entropy_mean=entropy_mean,
    )


def tokenize_result_to_dict(result: TokenizeResult) -> dict[str, Any]:
    n = result.normalize
    return {
        "paper_only": True,
        "encoder": result.encoder,
        "lookback": n.lookback,
        "feature_order": list(n.feature_order),
        "mean": n.mean,
        "std": n.std,
        "x_norm": n.x_norm,
        "s1_ids": result.s1_ids,
        "s2_ids": result.s2_ids,
        "vocab": {"coarse": 1024, "fine": 1024, "full_bits": 20},
        "entropy_mean": result.entropy_mean,
        "live_trading": False,
    }
