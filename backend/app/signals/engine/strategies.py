"""Pure Grid / DCA strategies — candles in, SignalIntent out (no IO, no clock)."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Literal, Protocol

from backend.app.signals.engine.config import StrategyConfig

Side = Literal["buy", "sell"]


@dataclass(frozen=True)
class SignalIntent:
    strategy_id: str
    kind: Literal["grid", "dca"]
    pair: str
    side: Side
    volume: Decimal
    reason: str
    zone: int | None = None
    price: float | None = None
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class StrategyState:
    """In-memory inventory / step flags for one engine run (not persisted in P1/P2)."""

    grid_inventory: dict[int, int] = field(default_factory=dict)  # zone -> units held
    dca_steps_filled: set[int] = field(default_factory=set)
    dca_entry_avg: float | None = None
    dca_units: Decimal = Decimal(0)
    adaptive_zones: list[tuple[float, float]] | None = None


class Strategy(Protocol):
    config: StrategyConfig

    def evaluate(self, candles: list[dict[str, Any]], state: StrategyState) -> list[SignalIntent]:
        ...


def _closes(candles: list[dict[str, Any]]) -> list[float]:
    out: list[float] = []
    for c in candles:
        try:
            out.append(float(c["close"]))
        except (KeyError, TypeError, ValueError):
            continue
    return out


class GridStrategy:
    """Price-grid: buy below empty zones, sell above held zones (within range)."""

    def __init__(self, config: StrategyConfig) -> None:
        if config.kind != "grid":
            raise ValueError("GridStrategy requires kind=grid")
        self.config = config
        self._zones: list[tuple[float, float]] | None = None
        if not config.adaptive_range:
            lo = float(config.range_low)  # type: ignore[arg-type]
            hi = float(config.range_high)  # type: ignore[arg-type]
            n = int(config.grid_count)
            step = (hi - lo) / n
            self._zones = [(lo + i * step, lo + (i + 1) * step) for i in range(n)]

    def _resolve_zones(
        self, candles: list[dict[str, Any]], state: StrategyState
    ) -> list[tuple[float, float]]:
        if self._zones is not None:
            return self._zones
        if state.adaptive_zones is not None:
            return state.adaptive_zones
        closes = _closes(candles)
        if len(closes) < 5:
            return []
        window = closes[-min(len(closes), 80) :]
        lo = min(window) * 0.995
        hi = max(window) * 1.005
        if hi <= lo:
            mid = closes[-1]
            lo, hi = mid * 0.99, mid * 1.01
        n = int(self.config.grid_count)
        step = (hi - lo) / n
        zones = [(lo + i * step, lo + (i + 1) * step) for i in range(n)]
        state.adaptive_zones = zones
        return zones

    def evaluate(self, candles: list[dict[str, Any]], state: StrategyState) -> list[SignalIntent]:
        closes = _closes(candles)
        if not closes:
            return []
        price = closes[-1]
        zones = self._resolve_zones(candles, state)
        if not zones:
            return []
        # Act only on the zone that contains price (last zone is closed on the high edge).
        zone_i: int | None = None
        for i, (z_lo, z_hi) in enumerate(zones):
            last = i == len(zones) - 1
            if (z_lo <= price < z_hi) or (last and z_lo <= price <= z_hi):
                zone_i = i
                break
        if zone_i is None:
            return []
        z_lo, z_hi = zones[zone_i]
        mid = (z_lo + z_hi) / 2.0
        held = state.grid_inventory.get(zone_i, 0)
        if price <= mid and held == 0:
            state.grid_inventory[zone_i] = 1
            # Dynamic volume: target ~$100 notional per zone (or config.volume_per_zone if > 0.01)
            target_notional = Decimal("100.0")
            vol = (target_notional / Decimal(str(price))).quantize(Decimal("0.00000001"))
            return [
                SignalIntent(
                    strategy_id=self.config.strategy_id,
                    kind="grid",
                    pair=self.config.pair,
                    side="buy",
                    volume=vol,
                    reason=f"grid_buy_zone_{zone_i}",
                    zone=zone_i,
                    price=price,
                    meta={"zone_low": z_lo, "zone_high": z_hi, "mid": mid, "adaptive": self.config.adaptive_range},
                )
            ]
        if price >= mid and held > 0:
            state.grid_inventory[zone_i] = 0
            target_notional = Decimal("100.0")
            vol = (target_notional / Decimal(str(price))).quantize(Decimal("0.00000001"))
            return [
                SignalIntent(
                    strategy_id=self.config.strategy_id,
                    kind="grid",
                    pair=self.config.pair,
                    side="sell",
                    volume=vol,
                    reason=f"grid_sell_zone_{zone_i}",
                    zone=zone_i,
                    price=price,
                    meta={"zone_low": z_lo, "zone_high": z_hi, "mid": mid, "adaptive": self.config.adaptive_range},
                )
            ]
        return []


class DcaStrategy:
    """Drawdown-ladder buys vs reference; take-profit sell when up from avg entry."""

    def __init__(self, config: StrategyConfig) -> None:
        if config.kind != "dca":
            raise ValueError("DcaStrategy requires kind=dca")
        self.config = config

    def evaluate(self, candles: list[dict[str, Any]], state: StrategyState) -> list[SignalIntent]:
        closes = _closes(candles)
        if not closes:
            return []
        price = closes[-1]
        ref = float(self.config.reference_price) if self.config.reference_price is not None else closes[0]
        intents: list[SignalIntent] = []

        for idx, step_pct in enumerate(self.config.drawdown_steps_pct):
            if idx in state.dca_steps_filled:
                continue
            trigger = ref * (1.0 - float(step_pct) / 100.0)
            if price <= trigger:
                target_notional = Decimal("100.0")
                add = (target_notional / Decimal(str(price))).quantize(Decimal("0.00000001"))
                intents.append(
                    SignalIntent(
                        strategy_id=self.config.strategy_id,
                        kind="dca",
                        pair=self.config.pair,
                        side="buy",
                        volume=add,
                        reason=f"dca_step_{idx}_{step_pct}pct",
                        zone=idx,
                        price=price,
                        meta={"reference": ref, "trigger": trigger, "step_pct": step_pct},
                    )
                )
                state.dca_steps_filled.add(idx)
                prev_units = state.dca_units
                if prev_units <= 0:
                    state.dca_entry_avg = price
                    state.dca_units = add
                else:
                    avg = state.dca_entry_avg or price
                    state.dca_entry_avg = float(
                        (Decimal(str(avg)) * prev_units + Decimal(str(price)) * add) / (prev_units + add)
                    )
                    state.dca_units = prev_units + add

        if state.dca_units > 0 and state.dca_entry_avg is not None:
            tp = state.dca_entry_avg * (1.0 + float(self.config.take_profit_pct) / 100.0)
            if price >= tp:
                intents.append(
                    SignalIntent(
                        strategy_id=self.config.strategy_id,
                        kind="dca",
                        pair=self.config.pair,
                        side="sell",
                        volume=state.dca_units,
                        reason="dca_take_profit",
                        zone=None,
                        price=price,
                        meta={"entry_avg": state.dca_entry_avg, "tp": tp},
                    )
                )
                state.dca_units = Decimal(0)
                state.dca_entry_avg = None
                state.dca_steps_filled.clear()

        return intents


def build_strategy(config: StrategyConfig) -> Strategy:
    if config.kind == "grid":
        return GridStrategy(config)
    if config.kind == "dca":
        return DcaStrategy(config)
    raise ValueError(f"unknown strategy kind: {config.kind}")
