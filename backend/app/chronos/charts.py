"""Matplotlib chart renderers for Chronos (Agg → PNG base64). Paper / research only."""

from __future__ import annotations

import base64
import io
from collections.abc import Sequence
from typing import Any

FEATURE_ORDER = ("open", "high", "low", "close", "volume", "amount")


def matplotlib_available() -> bool:
    try:
        import matplotlib  # noqa: F401

        return True
    except ImportError:
        return False


def _require_mpl():
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise RuntimeError(
            "matplotlib is required for Chronos charts. Install: pip install matplotlib"
        ) from exc
    return plt


def _fig_to_png_b64(fig: Any, plt: Any) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _style_axes(ax: Any) -> None:
    ax.set_facecolor("#0b1220")
    ax.tick_params(colors="#94a3b8", labelsize=8)
    for spine in ax.spines.values():
        spine.set_color("#1e293b")
    ax.yaxis.label.set_color("#94a3b8")
    ax.xaxis.label.set_color("#94a3b8")
    ax.title.set_color("#e2e8f0")
    ax.grid(True, color="#1e293b", linewidth=0.6, alpha=0.8)


def render_ohlc_chart(bars: Sequence[Sequence[float]], title: str = "OHLC lookback") -> str:
    """Close line with high/low band (no absolute labels beyond index)."""
    plt = _require_mpl()
    opens = [float(r[0]) for r in bars]
    highs = [float(r[1]) for r in bars]
    lows = [float(r[2]) for r in bars]
    closes = [float(r[3]) for r in bars]
    xs = list(range(len(bars)))

    fig, ax = plt.subplots(figsize=(9.5, 3.2), facecolor="#090d16")
    _style_axes(ax)
    ax.fill_between(xs, lows, highs, color="#22d3ee", alpha=0.12, linewidth=0)
    ax.plot(xs, closes, color="#22d3ee", linewidth=1.4, label="close")
    ax.plot(xs, opens, color="#64748b", linewidth=0.8, alpha=0.7, label="open")
    ax.set_title(title, fontsize=10, pad=8)
    ax.set_xlabel("bar index (lookback)")
    ax.legend(facecolor="#0f172a", edgecolor="#1e293b", labelcolor="#cbd5e1", fontsize=7)
    return _fig_to_png_b64(fig, plt)


def render_zscore_chart(x_norm: Sequence[Sequence[float]], title: str = "Causal Z-score (clipped)") -> str:
    plt = _require_mpl()
    fig, ax = plt.subplots(figsize=(9.5, 3.4), facecolor="#090d16")
    _style_axes(ax)
    xs = list(range(len(x_norm)))
    colors = ("#22d3ee", "#34d399", "#fbbf24", "#f472b6", "#a78bfa", "#94a3b8")
    # Plot OHLC only for clarity; volume/amount are often different scale even after z-score.
    for j, name in enumerate(FEATURE_ORDER[:4]):
        series = [float(row[j]) for row in x_norm]
        ax.plot(xs, series, color=colors[j], linewidth=1.1, label=name)
    ax.axhline(5.0, color="#f87171", linewidth=0.7, linestyle="--", alpha=0.5)
    ax.axhline(-5.0, color="#f87171", linewidth=0.7, linestyle="--", alpha=0.5)
    ax.set_ylim(-5.5, 5.5)
    ax.set_title(title, fontsize=10, pad=8)
    ax.set_xlabel("bar index")
    ax.set_ylabel("z")
    ax.legend(facecolor="#0f172a", edgecolor="#1e293b", labelcolor="#cbd5e1", fontsize=7, ncol=4)
    return _fig_to_png_b64(fig, plt)


def render_token_chart(
    s1_ids: Sequence[int],
    s2_ids: Sequence[int],
    title: str = "Coarse / fine token ids",
) -> str:
    plt = _require_mpl()
    fig, axes = plt.subplots(2, 1, figsize=(9.5, 4.2), facecolor="#090d16", sharex=True)
    xs = list(range(len(s1_ids)))
    for ax, series, color, label in (
        (axes[0], list(s1_ids), "#22d3ee", "s1 (coarse)"),
        (axes[1], list(s2_ids), "#a78bfa", "s2 (fine)"),
    ):
        _style_axes(ax)
        ax.step(xs, series, where="mid", color=color, linewidth=1.0)
        ax.set_ylabel(label, fontsize=8)
        ax.set_ylim(-20, 1044)
    axes[0].set_title(title, fontsize=10, pad=8)
    axes[1].set_xlabel("bar index")
    fig.tight_layout()
    return _fig_to_png_b64(fig, plt)


def render_token_hist(
    s1_ids: Sequence[int],
    s2_ids: Sequence[int],
    title: str = "Token id histograms",
) -> str:
    plt = _require_mpl()
    fig, axes = plt.subplots(1, 2, figsize=(9.5, 3.0), facecolor="#090d16")
    for ax, series, color, label in (
        (axes[0], list(s1_ids), "#22d3ee", "s1 coarse"),
        (axes[1], list(s2_ids), "#a78bfa", "s2 fine"),
    ):
        _style_axes(ax)
        ax.hist(series, bins=32, range=(0, 1023), color=color, alpha=0.85, edgecolor="#0b1220")
        ax.set_title(label, fontsize=9, color="#e2e8f0")
        ax.set_xlabel("token id")
        ax.set_ylabel("count")
    fig.suptitle(title, fontsize=10, color="#e2e8f0", y=1.02)
    fig.tight_layout()
    return _fig_to_png_b64(fig, plt)


def build_chronos_charts(
    bars: Sequence[Sequence[float]],
    *,
    eps: float = 1e-6,
    clip_val: float = 5.0,
    include_tokens: bool = True,
) -> dict[str, Any]:
    """Run normalize (+ optional tokenize) and return PNG charts as data-URLs."""
    from backend.app.chronos.normalize import ChronosNormalizer
    from backend.app.chronos.pipeline import tokenize_ohlcva

    if not matplotlib_available():
        raise RuntimeError("matplotlib not installed")

    norm = ChronosNormalizer(eps=eps, clip_val=clip_val).normalize_window(bars)
    charts: dict[str, str] = {
        "ohlc": f"data:image/png;base64,{render_ohlc_chart(bars)}",
        "zscore": f"data:image/png;base64,{render_zscore_chart(norm.x_norm)}",
    }
    meta: dict[str, Any] = {
        "lookback": norm.lookback,
        "paper_only": True,
        "renderer": "matplotlib",
    }

    if include_tokens:
        tok = tokenize_ohlcva(bars, eps=eps, clip_val=clip_val)
        charts["tokens"] = f"data:image/png;base64,{render_token_chart(tok.s1_ids, tok.s2_ids)}"
        charts["token_hist"] = f"data:image/png;base64,{render_token_hist(tok.s1_ids, tok.s2_ids)}"
        meta["entropy_mean"] = tok.entropy_mean
        meta["encoder"] = tok.encoder

    return {"charts": charts, **meta}
