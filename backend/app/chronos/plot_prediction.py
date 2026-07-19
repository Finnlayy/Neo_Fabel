"""Kronos-style matplotlib prediction plots (Ground Truth blue / Prediction red)."""

from __future__ import annotations

from typing import Any, Sequence

from backend.app.chronos.charts import _fig_to_png_b64, _require_mpl, _style_axes, matplotlib_available


def _as_series(rows: Sequence[dict[str, float]], col: str) -> list[float]:
    return [float(r[col]) for r in rows]


def plot_prediction(
    history_rows: Sequence[dict[str, float]],
    pred_rows: Sequence[dict[str, float]],
    *,
    include_volume: bool = True,
    ground_truth_future: Sequence[dict[str, float]] | None = None,
) -> str:
    """Mirror Kronos examples/prediction_example.py plot_prediction.

    Ground Truth (blue) = history (+ optional held-out future GT).
    Prediction (red) = forecast aligned to the tail indices after lookback.
    """
    if not matplotlib_available():
        raise RuntimeError("matplotlib not installed")
    plt = _require_mpl()

    hist_close = _as_series(history_rows, "close")
    pred_close = _as_series(pred_rows, "close")
    lookback = len(hist_close)
    pred_len = len(pred_close)
    xs_hist = list(range(lookback))
    xs_pred = list(range(lookback, lookback + pred_len))

    # Optional GT continuation (evaluation / demo when future bars known).
    gt_future_close: list[float] | None = None
    if ground_truth_future:
        gt_future_close = _as_series(ground_truth_future[:pred_len], "close")

    if include_volume:
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(8, 6), sharex=True, facecolor="#090d16")
        axes = (ax1, ax2)
    else:
        fig, ax1 = plt.subplots(1, 1, figsize=(8, 4), facecolor="#090d16")
        axes = (ax1,)

    for ax in axes:
        _style_axes(ax)

    ax1.plot(xs_hist, hist_close, label="Ground Truth", color="blue", linewidth=1.5)
    if gt_future_close:
        ax1.plot(
            list(range(lookback, lookback + len(gt_future_close))),
            gt_future_close,
            color="blue",
            linewidth=1.5,
            alpha=0.85,
        )
    ax1.plot(xs_pred, pred_close, label="Prediction", color="red", linewidth=1.5)
    ax1.axvline(lookback - 0.5, color="#64748b", linewidth=0.8, linestyle="--", alpha=0.7)
    ax1.set_ylabel("Close Price", fontsize=12)
    ax1.legend(loc="lower left", fontsize=9, facecolor="#0f172a", edgecolor="#1e293b", labelcolor="#e2e8f0")
    ax1.set_title("Chronos prediction (Kronos-style)", fontsize=11, color="#e2e8f0", pad=8)
    ax1.grid(True)

    if include_volume:
        hist_vol = _as_series(history_rows, "volume")
        pred_vol = _as_series(pred_rows, "volume")
        ax2.plot(xs_hist, hist_vol, label="Ground Truth", color="blue", linewidth=1.5)
        if ground_truth_future:
            gt_vol = _as_series(ground_truth_future[:pred_len], "volume")
            ax2.plot(
                list(range(lookback, lookback + len(gt_vol))),
                gt_vol,
                color="blue",
                linewidth=1.5,
                alpha=0.85,
            )
        ax2.plot(xs_pred, pred_vol, label="Prediction", color="red", linewidth=1.5)
        ax2.axvline(lookback - 0.5, color="#64748b", linewidth=0.8, linestyle="--", alpha=0.7)
        ax2.set_ylabel("Volume", fontsize=12)
        ax2.legend(loc="upper left", fontsize=9, facecolor="#0f172a", edgecolor="#1e293b", labelcolor="#e2e8f0")
        ax2.set_xlabel("bar index")
        ax2.grid(True)
    else:
        ax1.set_xlabel("bar index")

    fig.tight_layout()
    return _fig_to_png_b64(fig, plt)


def plot_prediction_monte_carlo(
    history_rows: Sequence[dict[str, float]],
    paths: Sequence[Sequence[Sequence[float]]],
    *,
    mean_pred_rows: Sequence[dict[str, float]] | None = None,
    q_low: float = 0.1,
    q_high: float = 0.9,
) -> str:
    """Probabilistic forecast: mean close (solid) + shaded uncertainty band."""
    if not matplotlib_available():
        raise RuntimeError("matplotlib not installed")
    if not paths:
        raise ValueError("paths required")
    plt = _require_mpl()

    hist_close = _as_series(history_rows, "close")
    lookback = len(hist_close)
    pred_len = len(paths[0])
    xs_hist = list(range(lookback))
    xs_pred = list(range(lookback, lookback + pred_len))

    # Gather close paths → quantiles.
    closes_by_t = [[float(path[t][3]) for path in paths] for t in range(pred_len)]
    mean_close: list[float] = []
    low_band: list[float] = []
    high_band: list[float] = []
    for vals in closes_by_t:
        ordered = sorted(vals)
        n = len(ordered)
        lo_i = max(0, min(n - 1, int(q_low * (n - 1))))
        hi_i = max(0, min(n - 1, int(q_high * (n - 1))))
        low_band.append(ordered[lo_i])
        high_band.append(ordered[hi_i])
        mean_close.append(sum(vals) / n)

    if mean_pred_rows and len(mean_pred_rows) == pred_len:
        mean_close = _as_series(mean_pred_rows, "close")

    fig, ax = plt.subplots(figsize=(8, 4.5), facecolor="#090d16")
    _style_axes(ax)
    ax.plot(xs_hist, hist_close, label="Ground Truth", color="blue", linewidth=1.5)
    ax.fill_between(
        xs_pred,
        low_band,
        high_band,
        color="red",
        alpha=0.18,
        label=f"P{int(q_low * 100)}–P{int(q_high * 100)}",
    )
    ax.plot(xs_pred, mean_close, label="Prediction (mean)", color="red", linewidth=1.8)
    # Faint individual paths (cap for readability).
    for path in list(paths)[:12]:
        ax.plot(
            xs_pred,
            [float(row[3]) for row in path],
            color="red",
            linewidth=0.4,
            alpha=0.25,
        )
    ax.axvline(lookback - 0.5, color="#64748b", linewidth=0.8, linestyle="--", alpha=0.7)
    ax.set_ylabel("Close Price", fontsize=12)
    ax.set_xlabel("bar index")
    ax.set_title("Chronos Monte Carlo forecast", fontsize=11, color="#e2e8f0", pad=8)
    ax.legend(loc="best", fontsize=8, facecolor="#0f172a", edgecolor="#1e293b", labelcolor="#e2e8f0")
    ax.grid(True)
    fig.tight_layout()
    return _fig_to_png_b64(fig, plt)


def build_prediction_charts(
    history_rows: Sequence[dict[str, float]],
    pred_rows: Sequence[dict[str, float]],
    *,
    paths: Sequence[Sequence[Sequence[float]]] | None = None,
    include_volume: bool = True,
    ground_truth_future: Sequence[dict[str, float]] | None = None,
) -> dict[str, str]:
    charts: dict[str, str] = {
        "prediction": f"data:image/png;base64,{plot_prediction(history_rows, pred_rows, include_volume=include_volume, ground_truth_future=ground_truth_future)}",
    }
    if not include_volume:
        charts["prediction_wo_vol"] = charts["prediction"]
    else:
        charts["prediction_wo_vol"] = (
            f"data:image/png;base64,{plot_prediction(history_rows, pred_rows, include_volume=False, ground_truth_future=ground_truth_future)}"
        )
    if paths:
        charts["monte_carlo"] = (
            f"data:image/png;base64,{plot_prediction_monte_carlo(history_rows, paths, mean_pred_rows=pred_rows)}"
        )
    return charts
