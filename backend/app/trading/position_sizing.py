"""Session position-sizing policies for live (and paper) trading.

Modes:
  - half_kelly: classic Kelly × 0.5
  - full_kelly: classic Kelly × 1.0 (still capped)
  - ai_chronos: size from AI / Chronos confidence layer
  - manual: fixed notional in EUR set at session start
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal
from typing import Any, Literal

PositionSizingMode = Literal["half_kelly", "full_kelly", "ai_chronos", "manual"]

SIZING_MODES: tuple[PositionSizingMode, ...] = (
    "half_kelly",
    "full_kelly",
    "ai_chronos",
    "manual",
)

_MODE_ALIASES: dict[str, PositionSizingMode] = {
    "half_kelly": "half_kelly",
    "half-kelly": "half_kelly",
    "halfkelly": "half_kelly",
    "half": "half_kelly",
    "full_kelly": "full_kelly",
    "full-kelly": "full_kelly",
    "fullkelly": "full_kelly",
    "full": "full_kelly",
    "kelly": "full_kelly",
    "ai_chronos": "ai_chronos",
    "ai-chronos": "ai_chronos",
    "ai": "ai_chronos",
    "chronos": "ai_chronos",
    "from_ai": "ai_chronos",
    "from_ai_layer": "ai_chronos",
    "manual": "manual",
    "fixed": "manual",
}


def parse_sizing_mode(raw: str | None) -> PositionSizingMode:
    key = (raw or "").strip().lower().replace(" ", "_")
    if key not in _MODE_ALIASES:
        raise ValueError(
            f"unknown position_sizing_mode={raw!r}; "
            f"expected one of {', '.join(SIZING_MODES)}"
        )
    return _MODE_ALIASES[key]


@dataclass(frozen=True)
class PositionSizingPolicy:
    mode: PositionSizingMode
    manual_notional_eur: float | None = None
    # Kelly priors (overridable later via feedback / stats)
    win_rate: float = 0.55
    avg_win: float = 0.08
    avg_loss: float = 0.03
    max_fraction: float = 0.25
    min_notional_eur: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def validate_sizing_policy(
    *,
    mode: str | PositionSizingMode,
    manual_notional_eur: float | None = None,
    win_rate: float = 0.55,
    avg_win: float = 0.08,
    avg_loss: float = 0.03,
    max_fraction: float = 0.25,
) -> PositionSizingPolicy:
    resolved = parse_sizing_mode(str(mode))
    if not (0.0 < float(win_rate) < 1.0):
        raise ValueError("win_rate must be in (0, 1)")
    if float(avg_win) <= 0 or float(avg_loss) <= 0:
        raise ValueError("avg_win and avg_loss must be > 0")
    if not (0.0 < float(max_fraction) <= 1.0):
        raise ValueError("max_fraction must be in (0, 1]")
    manual: float | None = None
    if resolved == "manual":
        if manual_notional_eur is None or float(manual_notional_eur) <= 0:
            raise ValueError("manual mode requires manual_notional_eur > 0")
        manual = float(manual_notional_eur)
    elif manual_notional_eur is not None and float(manual_notional_eur) > 0:
        # Allowed as optional display/fallback, not used unless mode is manual
        manual = float(manual_notional_eur)
    return PositionSizingPolicy(
        mode=resolved,
        manual_notional_eur=manual,
        win_rate=float(win_rate),
        avg_win=float(avg_win),
        avg_loss=float(avg_loss),
        max_fraction=float(max_fraction),
    )


def kelly_fraction(
    *,
    win_prob: float,
    payoff_ratio: float,
    scale: float = 1.0,
) -> float:
    """f* = (p*b - q) / b, then multiplied by scale (0.5 = half Kelly)."""
    p = max(0.0, min(1.0, float(win_prob)))
    q = 1.0 - p
    b = float(payoff_ratio)
    if b <= 0:
        return 0.0
    raw = (p * b - q) / b
    return max(0.0, raw * float(scale))


def _payoff_ratio(policy: PositionSizingPolicy, stop_pct: float | None, take_pct: float | None) -> float:
    if stop_pct and take_pct and float(stop_pct) > 0:
        return float(take_pct) / float(stop_pct)
    return float(policy.avg_win) / float(policy.avg_loss)


def resolve_ai_chronos_confidence() -> float:
    """Best-effort confidence from Chronos / AI agent layer (0-1)."""
    try:
        from backend.app.academy.agency_roster import build_agency_roster

        roster = build_agency_roster()
        agents: list[Any]
        if isinstance(roster, dict):
            raw = roster.get("agents")
            agents = raw if isinstance(raw, list) else []
        elif isinstance(roster, list):
            agents = roster
        else:
            agents = []
        for agent in agents:
            if not isinstance(agent, dict):
                continue
            name = str(agent.get("id") or agent.get("name") or "").lower()
            if name in {"chronos", "risk_gov", "risk"}:
                conf = agent.get("confidence")
                if conf is None:
                    conf = agent.get("confidence_level")
                if conf is not None:
                    return max(0.05, min(0.95, float(conf)))
    except Exception:  # noqa: BLE001
        pass
    return 0.55


def compute_notional_eur(
    policy: PositionSizingPolicy,
    *,
    capital_eur: float,
    max_margin_eur: float | None = None,
    confidence: float | None = None,
    stop_pct: float | None = None,
    take_pct: float | None = None,
    ai_confidence: float | None = None,
) -> dict[str, Any]:
    """Resolve order notional (EUR) for the active sizing policy."""
    capital = max(0.0, float(capital_eur))
    cap = float(max_margin_eur) if max_margin_eur is not None else capital
    cap = max(0.0, min(capital, cap)) if capital > 0 else max(0.0, cap)

    mode = policy.mode
    fraction = 0.0
    detail: dict[str, Any] = {"mode": mode}

    if mode == "manual":
        notional = float(policy.manual_notional_eur or 0.0)
        detail["source"] = "manual_notional_eur"
    elif mode in {"half_kelly", "full_kelly"}:
        scale = 0.5 if mode == "half_kelly" else 1.0
        p = float(confidence) if confidence is not None else policy.win_rate
        # Blend signal confidence with historical win rate when both present
        if confidence is not None:
            p = max(0.05, min(0.95, 0.5 * policy.win_rate + 0.5 * float(confidence)))
        b = _payoff_ratio(policy, stop_pct, take_pct)
        fraction = kelly_fraction(win_prob=p, payoff_ratio=b, scale=scale)
        fraction = min(fraction, policy.max_fraction)
        notional = capital * fraction
        detail.update(
            {
                "source": mode,
                "win_prob": p,
                "payoff_ratio": b,
                "kelly_scale": scale,
                "fraction": fraction,
            }
        )
    else:  # ai_chronos
        conf = float(ai_confidence) if ai_confidence is not None else resolve_ai_chronos_confidence()
        if confidence is not None:
            conf = max(0.05, min(0.95, 0.5 * conf + 0.5 * float(confidence)))
        # Map confidence → fraction: 0.5 conf ≈ 8% of capital, capped
        fraction = min(policy.max_fraction, max(0.02, conf * 0.2))
        notional = capital * fraction
        detail.update(
            {
                "source": "ai_chronos",
                "ai_confidence": conf,
                "fraction": fraction,
            }
        )

    notional = max(0.0, float(notional))
    if cap > 0:
        notional = min(notional, cap)
    if notional > 0 and notional < policy.min_notional_eur and mode != "manual":
        # Skip dust unless user explicitly set a tiny manual size
        if notional < policy.min_notional_eur:
            detail["below_min_notional"] = True
    detail["notional_eur"] = notional
    detail["capital_eur"] = capital
    detail["max_margin_eur"] = cap
    return detail


def volume_from_notional(*, notional_eur: float, price: Decimal | float) -> Decimal:
    px = Decimal(str(price))
    if px <= 0:
        raise ValueError("price must be > 0")
    return (Decimal(str(notional_eur)) / px).quantize(Decimal("0.00000001"))
