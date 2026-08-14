"""Binary Spherical Quantization (BSQ) — sign shortcut + coarse/fine factorisation.

Inference uses sign(z) directly (L2-norm is redundant for signs). Training-time
entropy uses factorised Bernoulli soft probs; STE is applied by callers that
own continuous latents.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import exp, log, sqrt
from typing import Sequence

LATENT_DIM = 20
COARSE_BITS = 10
FINE_BITS = 10
VOCAB_PER_HALF = 1 << COARSE_BITS  # 1024
FULL_VOCAB = 1 << LATENT_DIM  # 1_048_576


def pack_bits_lsb(bits: Sequence[int]) -> int:
    """Pack bits LSB-first into an integer index."""
    value = 0
    for i, bit in enumerate(bits):
        if bit:
            value |= 1 << i
    return value


def unpack_bits_lsb(index: int, n_bits: int) -> list[int]:
    return [((index >> i) & 1) for i in range(n_bits)]


def _sigmoid(x: float) -> float:
    if x >= 0:
        z = exp(-x)
        return 1.0 / (1.0 + z)
    z = exp(x)
    return z / (1.0 + z)


@dataclass(frozen=True)
class BsqEncodeResult:
    s1_id: int
    s2_id: int
    bits: tuple[int, ...]
    entropy_loss: float


class BinarySphericalQuantizer:
    def __init__(self, latent_dim: int = LATENT_DIM, inv_temperature: float = 10.0) -> None:
        if latent_dim != LATENT_DIM:
            raise ValueError(f"Chronos Phase-1 BSQ is fixed at {LATENT_DIM}-D")
        self.latent_dim = latent_dim
        self.inv_temp = inv_temperature
        self.scale = 1.0 / sqrt(latent_dim)

    def encode(self, z: Sequence[float]) -> BsqEncodeResult:
        if len(z) != self.latent_dim:
            raise ValueError(f"expected latent dim {self.latent_dim}, got {len(z)}")

        # Sign shortcut: sign(z_d / ||z||) == sign(z_d); zero → bit 1.
        bits = tuple(1 if float(z[d]) >= 0.0 else 0 for d in range(self.latent_dim))

        soft_probs = [_sigmoid(float(z[d]) * self.inv_temp) for d in range(self.latent_dim)]
        entropy_terms: list[float] = []
        for p in soft_probs:
            p = min(max(p, 1e-8), 1.0 - 1e-8)
            entropy_terms.append(-(p * log(p) + (1.0 - p) * log(1.0 - p)))
        entropy_loss = sum(entropy_terms) / len(entropy_terms)

        s1_id = pack_bits_lsb(bits[:COARSE_BITS])
        s2_id = pack_bits_lsb(bits[COARSE_BITS:])
        return BsqEncodeResult(s1_id=s1_id, s2_id=s2_id, bits=bits, entropy_loss=entropy_loss)

    def decode(self, s1_id: int, s2_id: int) -> list[float]:
        if not (0 <= s1_id < VOCAB_PER_HALF and 0 <= s2_id < VOCAB_PER_HALF):
            raise ValueError("s1/s2 must be in [0, 1023]")
        z_recon = [0.0] * self.latent_dim
        for i, bit in enumerate(unpack_bits_lsb(s1_id, COARSE_BITS)):
            z_recon[i] = (bit * 2.0 - 1.0) * self.scale
        for i, bit in enumerate(unpack_bits_lsb(s2_id, FINE_BITS)):
            z_recon[COARSE_BITS + i] = (bit * 2.0 - 1.0) * self.scale
        return z_recon

    def encode_sequence(self, z_seq: Sequence[Sequence[float]]) -> list[BsqEncodeResult]:
        return [self.encode(z) for z in z_seq]
