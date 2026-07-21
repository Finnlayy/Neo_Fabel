"""One-liner trade rationales for every intent / fill."""

from __future__ import annotations

from typing import Any

from backend.app.signals.engine.strategies import SignalIntent


def format_trade_rationale(intent: SignalIntent) -> str:
    """Human one-liner explaining why this trade was proposed (≤180 chars)."""
    pair = intent.pair.upper()
    side = intent.side.upper()
    kind = intent.kind.upper()
    px = f" @ {intent.price:.4g}" if intent.price is not None else ""
    meta = intent.meta or {}

    if intent.kind == "grid":
        zone = intent.zone if intent.zone is not None else "?"
        mid = meta.get("mid")
        mid_s = f", mid={float(mid):.4g}" if mid is not None else ""
        base = f"{kind} {side} {pair}{px}: zone {zone}{mid_s} — {intent.reason}"
    elif intent.kind == "dca":
        step = meta.get("step_pct")
        step_s = f" step={step}%" if step is not None else ""
        base = f"{kind} {side} {pair}{px}{step_s} — {intent.reason}"
    else:
        base = f"{kind} {side} {pair}{px} — {intent.reason}"

    return base[:180]


def rationale_from_fill_row(row: dict[str, Any]) -> str:
    """Fallback one-liner for ledger fills that lack an engine rationale."""
    if isinstance(row.get("rationale"), str) and row["rationale"].strip():
        return str(row["rationale"]).strip()[:180]
    pair = str(row.get("pair") or row.get("symbol") or "?").upper()
    side = str(row.get("side") or row.get("type") or "?").upper()
    pnl = row.get("pnl") or row.get("realized_pnl")
    px = row.get("price")
    px_s = f" @ {px}" if px is not None else ""
    pnl_s = f", pnl={pnl}" if pnl is not None else ""
    return f"PAPER {side} {pair}{px_s}{pnl_s}"[:180]
