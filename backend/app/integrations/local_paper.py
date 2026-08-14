"""In-process paper ledger — spot + futures books (v2), disk-backed, paper-only."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Awaitable, Callable, Literal
from uuid import uuid4

from backend.app.integrations.paper_paths import ledger_path
from backend.app.integrations.paper_performance import build_combined_performance
from backend.app.market.instruments import MarketType, resolve_instrument
from backend.app.trading.position_sizing import (
    PositionSizingPolicy,
    compute_notional_eur,
    parse_sizing_mode,
    volume_from_notional,
)

PriceResolver = Callable[[MarketType, str], Awaitable[Decimal]]

LEDGER_VERSION = 2


def _normalize_pair(pair: str) -> str:
    return pair.strip().upper().replace("/", "").replace("-", "")


def _d(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value or "0"))


def _fmt(value: Decimal) -> str:
    return format(value, "f")


def _empty_spot_book(starting: Decimal) -> dict[str, Any]:
    s = _fmt(starting)
    return {
        "starting_balance_usd": s,
        "usd_balance": s,
        "lots": {},
        "fills": [],
    }


def _empty_futures_book(starting_margin: Decimal) -> dict[str, Any]:
    s = _fmt(starting_margin)
    return {
        "starting_margin_usd": s,
        "margin_balance_usd": s,
        "positions": {},
        "fills": [],
    }


def _migrate_v1(data: dict[str, Any], starting_spot: Decimal, starting_futures: Decimal) -> dict[str, Any]:
    spot = _empty_spot_book(starting_spot)
    spot["starting_balance_usd"] = str(data.get("starting_balance_usd", _fmt(starting_spot)))
    spot["usd_balance"] = str(data.get("usd_balance", spot["starting_balance_usd"]))
    spot["lots"] = dict(data.get("lots") or {})
    spot["fills"] = list(data.get("fills") or [])
    return {
        "version": LEDGER_VERSION,
        "spot": spot,
        "futures": _empty_futures_book(starting_futures),
    }


@dataclass
class LocalPaperLedger:
    """Thread-safe disk-backed paper book with separate spot cash and futures margin."""

    starting_balance_usd: Decimal = Decimal("10000")
    starting_margin_usd: Decimal = Decimal("10000")
    maker_fee_rate: Decimal = Decimal("0")
    taker_fee_rate: Decimal = Decimal("0.0005")
    fee_model: str = "kraken_pro_tier5"
    max_open_positions: int = 20
    kelly_sizing_enabled: bool = True
    kelly_mode: str = "half_kelly"
    _path: Any = field(default_factory=ledger_path, repr=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False)
    _price_resolver: PriceResolver | None = field(default=None, repr=False)
    _state: dict[str, Any] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        if not self._state:
            self._state = self._load_or_init()

    def set_price_resolver(self, resolver: PriceResolver) -> None:
        self._price_resolver = resolver

    def open_position_count(self) -> int:
        """Distinct open spot lots + futures positions."""
        lots = self._spot.get("lots") or {}
        spot_n = sum(1 for rows in lots.values() if rows)
        fut_n = len(self._futures.get("positions") or {})
        return int(spot_n + fut_n)

    def _assert_open_capacity(self, *, pair: str, market_type: MarketType, side: str) -> None:
        """Block opening a *new* concurrent position beyond max_open_positions."""
        if market_type == "spot":
            if side != "buy":
                return
            lots = (self._spot.get("lots") or {}).get(pair) or []
            if lots:
                return  # adding to existing spot position
        else:
            if pair in (self._futures.get("positions") or {}):
                return  # existing futures symbol
        if self.open_position_count() >= int(self.max_open_positions):
            raise ValueError(
                f"paper max open positions reached ({self.max_open_positions})"
            )

    def _load_or_init(self) -> dict[str, Any]:
        path = self._path
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    version = int(data.get("version", 1))
                    if version >= LEDGER_VERSION:
                        data.setdefault("spot", _empty_spot_book(self.starting_balance_usd))
                        data.setdefault("futures", _empty_futures_book(self.starting_margin_usd))
                        return data
                    return _migrate_v1(data, self.starting_balance_usd, self.starting_margin_usd)
            except (json.JSONDecodeError, OSError, ValueError):
                pass
        return {
            "version": LEDGER_VERSION,
            "spot": _empty_spot_book(self.starting_balance_usd),
            "futures": _empty_futures_book(self.starting_margin_usd),
        }

    def _save(self) -> None:
        path = self._path
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(self._state, indent=2), encoding="utf-8")
        tmp.replace(path)

    @property
    def _spot(self) -> dict[str, Any]:
        return self._state.setdefault("spot", _empty_spot_book(self.starting_balance_usd))

    @property
    def _futures(self) -> dict[str, Any]:
        return self._state.setdefault("futures", _empty_futures_book(self.starting_margin_usd))

    async def _resolve_price(
        self,
        market_type: MarketType,
        pair: str,
        order_type: Literal["market", "limit"],
        price: Decimal | None,
    ) -> Decimal:
        if price is not None and price > 0:
            return price
        if self._price_resolver is None:
            raise ValueError("market order requires price or ticker resolver")
        resolved = await self._price_resolver(market_type, pair)
        if resolved <= 0:
            raise ValueError(f"could not resolve {market_type} price for {pair}")
        return resolved

    def _fee_rate(self, order_type: Literal["market", "limit"]) -> Decimal:
        return self.maker_fee_rate if order_type == "limit" else self.taker_fee_rate

    def _kelly_volume(
        self,
        *,
        bankroll: Decimal,
        price: Decimal,
    ) -> tuple[Decimal, dict[str, Any]]:
        """Size a new paper exposure from the active paper bankroll."""
        mode = parse_sizing_mode(self.kelly_mode)
        if mode not in {"half_kelly", "full_kelly"}:
            raise ValueError("paper Kelly mode must be half_kelly or full_kelly")
        policy = PositionSizingPolicy(mode=mode)
        detail = compute_notional_eur(
            policy,
            capital_eur=float(bankroll),
            max_margin_eur=float(bankroll),
        )
        notional = float(detail.get("notional_eur") or 0)
        if notional <= 0:
            raise ValueError("paper Kelly sizing resolved to zero notional")
        sized = volume_from_notional(notional_eur=notional, price=price)
        if sized <= 0:
            raise ValueError("paper Kelly sizing resolved to zero volume")
        detail["volume"] = _fmt(sized)
        detail["bankroll_usd"] = _fmt(bankroll)
        return sized, detail

    def _consume_lots_fifo(
        self,
        book: dict[str, Any],
        pair: str,
        sell_volume: Decimal,
        sell_price: Decimal,
        total_fee: Decimal,
    ) -> Decimal:
        lots: list[dict[str, Any]] = list((book.get("lots") or {}).get(pair) or [])
        remaining = sell_volume
        realized = Decimal("0")

        while remaining > 0 and lots:
            lot = lots[0]
            lot_vol = _d(lot.get("volume"))
            if lot_vol <= 0:
                lots.pop(0)
                continue
            take = min(lot_vol, remaining)
            unit_cost = _d(lot.get("unit_cost"))
            cost = take * unit_cost
            proceeds = take * sell_price - (total_fee * (take / sell_volume))
            realized += proceeds - cost
            lot_vol -= take
            remaining -= take
            if lot_vol <= 0:
                lots.pop(0)
            else:
                lot["volume"] = _fmt(lot_vol)

        if remaining > 0:
            raise ValueError(f"insufficient {pair} spot position for sell")

        lots_dict = dict(book.get("lots") or {})
        if lots:
            lots_dict[pair] = lots
        else:
            lots_dict.pop(pair, None)
        book["lots"] = lots_dict
        return realized

    async def _spot_order(
        self,
        side: Literal["buy", "sell"],
        pair: str,
        volume: Decimal,
        order_type: Literal["market", "limit"],
        price: Decimal | None,
        *,
        rationale: str | None = None,
    ) -> dict[str, Any]:
        book = self._spot
        fill_price = await self._resolve_price("spot", pair, order_type, price)
        fee_rate = self._fee_rate(order_type)
        requested_volume = volume
        sizing_detail: dict[str, Any] | None = None
        cash = _d(book.get("usd_balance"))
        if side == "buy" and self.kelly_sizing_enabled:
            volume, sizing_detail = self._kelly_volume(bankroll=cash, price=fill_price)
        notional = volume * fill_price
        fee = notional * fee_rate
        realized_pnl = Decimal("0")

        if side == "buy":
            cost = notional + fee
            if cost > cash:
                raise ValueError("insufficient USD balance for paper spot buy")
            cash -= cost
            unit_cost = cost / volume
            lots = dict(book.get("lots") or {})
            rows = list(lots.get(pair) or [])
            rows.append({"volume": _fmt(volume), "unit_cost": _fmt(unit_cost)})
            lots[pair] = rows
            book["lots"] = lots
        else:
            realized_pnl = self._consume_lots_fifo(book, pair, volume, fill_price, fee)
            proceeds = notional - fee
            cash += proceeds

        book["usd_balance"] = _fmt(cash)
        return self._append_fill(
            book,
            market_type="spot",
            pair=pair,
            side=side,
            volume=volume,
            order_type=order_type,
            fill_price=fill_price,
            fee=fee,
            fee_rate=fee_rate,
            realized_pnl=realized_pnl,
            leverage=1,
            rationale=rationale,
            requested_volume=requested_volume,
            sizing_detail=sizing_detail,
        )

    async def _futures_order(
        self,
        side: Literal["buy", "sell"],
        pair: str,
        volume: Decimal,
        order_type: Literal["market", "limit"],
        price: Decimal | None,
        leverage: int,
        *,
        rationale: str | None = None,
    ) -> dict[str, Any]:
        book = self._futures
        lev = max(1, min(int(leverage), 50))
        fill_price = await self._resolve_price("futures", pair, order_type, price)
        fee_rate = self._fee_rate(order_type)
        requested_volume = volume
        sizing_detail: dict[str, Any] | None = None
        positions: dict[str, Any] = dict(book.get("positions") or {})
        margin = _d(book.get("margin_balance_usd"))
        if pair not in positions and self.kelly_sizing_enabled:
            volume, sizing_detail = self._kelly_volume(bankroll=margin, price=fill_price)
        notional = volume * fill_price
        fee = notional * fee_rate
        pos = positions.get(pair) or {
            "side": "flat",
            "contracts": "0",
            "entry_price": "0",
            "leverage": lev,
            "initial_margin": "0",
        }
        contracts = _d(pos.get("contracts"))
        entry = _d(pos.get("entry_price"))
        side_sign = Decimal("1") if side == "buy" else Decimal("-1")
        delta = volume * side_sign
        new_contracts = contracts + delta
        realized_pnl = Decimal("0")

        if contracts == 0:
            required_margin = notional / Decimal(lev) + fee
            if required_margin > margin:
                raise ValueError("insufficient futures margin for new position")
            margin -= required_margin
            positions[pair] = {
                "side": "long" if side == "buy" else "short",
                "contracts": _fmt(abs(new_contracts)),
                "entry_price": _fmt(fill_price),
                "leverage": lev,
                "initial_margin": _fmt(notional / Decimal(lev)),
            }
        elif (contracts > 0 and delta > 0) or (contracts < 0 and delta < 0):
            # Add to same direction
            add_notional = abs(delta) * fill_price
            add_margin = add_notional / Decimal(lev) + fee
            if add_margin > margin:
                raise ValueError("insufficient futures margin to add")
            margin -= add_margin
            total = abs(contracts) + abs(delta)
            new_entry = (abs(contracts) * entry + abs(delta) * fill_price) / total
            prev_margin = _d(pos.get("initial_margin"))
            positions[pair] = {
                "side": "long" if new_contracts > 0 else "short",
                "contracts": _fmt(abs(new_contracts)),
                "entry_price": _fmt(new_entry),
                "leverage": lev,
                "initial_margin": _fmt(prev_margin + add_notional / Decimal(lev)),
            }
        else:
            # Reduce or flip — close portion
            close_vol = min(abs(contracts), abs(delta))
            if contracts > 0:
                realized_pnl = (fill_price - entry) * close_vol - fee
            else:
                realized_pnl = (entry - fill_price) * close_vol - fee
            released = _d(pos.get("initial_margin")) * (close_vol / abs(contracts)) if contracts else Decimal("0")
            margin += released + realized_pnl

            remaining = abs(contracts) - close_vol
            flip_vol = abs(delta) - close_vol
            if remaining > 0:
                positions[pair] = {
                    "side": "long" if contracts > 0 else "short",
                    "contracts": _fmt(remaining),
                    "entry_price": _fmt(entry),
                    "leverage": lev,
                    "initial_margin": _fmt(_d(pos.get("initial_margin")) - released),
                }
            elif flip_vol > 0:
                flip_notional = flip_vol * fill_price
                flip_margin = flip_notional / Decimal(lev) + fee
                if flip_margin > margin:
                    raise ValueError("insufficient margin to flip futures position")
                margin -= flip_margin
                positions[pair] = {
                    "side": "long" if delta > 0 else "short",
                    "contracts": _fmt(flip_vol),
                    "entry_price": _fmt(fill_price),
                    "leverage": lev,
                    "initial_margin": _fmt(flip_notional / Decimal(lev)),
                }
            else:
                positions.pop(pair, None)

        book["margin_balance_usd"] = _fmt(margin)
        book["positions"] = positions
        return self._append_fill(
            book,
            market_type="futures",
            pair=pair,
            side=side,
            volume=volume,
            order_type=order_type,
            fill_price=fill_price,
            fee=fee,
            fee_rate=fee_rate,
            realized_pnl=realized_pnl,
            leverage=lev,
            rationale=rationale,
            requested_volume=requested_volume,
            sizing_detail=sizing_detail,
        )

    def _append_fill(
        self,
        book: dict[str, Any],
        *,
        market_type: MarketType,
        pair: str,
        side: str,
        volume: Decimal,
        order_type: str,
        fill_price: Decimal,
        fee: Decimal,
        fee_rate: Decimal,
        realized_pnl: Decimal,
        leverage: int,
        rationale: str | None = None,
        requested_volume: Decimal | None = None,
        sizing_detail: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        order_id = f"LOCAL-{uuid4().hex[:12].upper()}"
        now = datetime.now(UTC).isoformat()
        fill: dict[str, Any] = {
            "txid": order_id,
            "id": order_id,
            "market_type": market_type,
            "pair": pair,
            "side": side,
            "type": side,
            "ordertype": order_type,
            "vol": _fmt(volume),
            "volume": _fmt(volume),
            "price": _fmt(fill_price),
            "fee": _fmt(fee),
            "fee_rate": _fmt(fee_rate),
            "leverage": leverage,
            "realized_pnl": _fmt(realized_pnl),
            "status": "closed",
            "state": "CLOSED",
            "time": now,
            "opentm": now,
            "closetm": now,
            "source": "local-paper-ledger",
            "pnl": _fmt(realized_pnl),
        }
        if rationale:
            fill["rationale"] = str(rationale).strip()[:180]
        if sizing_detail is not None:
            fill["requested_volume"] = _fmt(requested_volume or volume)
            fill["position_sizing"] = sizing_detail
        fills = list(book.get("fills") or [])
        fills.append(fill)
        book["fills"] = fills[-2000:]
        self._save()
        return {
            "ok": True,
            "source": "local-paper-ledger",
            "market_type": market_type,
            "txid": [order_id],
            "descr": {"order": f"{side} {market_type}:{pair} {_fmt(volume)} {order_type}"},
            "order": dict(fill),
        }

    async def paper_order(
        self,
        side: Literal["buy", "sell"],
        pair: str,
        volume: Decimal,
        order_type: Literal["market", "limit"],
        price: Decimal | None,
        *,
        market_type: MarketType = "spot",
        leverage: int = 1,
        rationale: str | None = None,
    ) -> dict[str, Any]:
        if side not in {"buy", "sell"} or order_type not in {"market", "limit"}:
            raise ValueError("unsupported paper order")
        if volume <= 0 or (order_type == "limit" and (price is None or price <= 0)):
            raise ValueError("invalid paper order values")
        clipped = str(rationale).strip()[:180] if rationale else None

        inst = resolve_instrument(market_type, pair, leverage=leverage)
        async with self._lock:
            self._assert_open_capacity(pair=inst.symbol, market_type=inst.market_type, side=side)
            if inst.market_type == "futures":
                return await self._futures_order(
                    side, inst.symbol, volume, order_type, price, leverage, rationale=clipped
                )
            return await self._spot_order(
                side, inst.symbol, volume, order_type, price, rationale=clipped
            )

    async def paper_status(self) -> dict[str, Any]:
        async with self._lock:
            spot_fills = list(reversed(self._spot.get("fills") or []))
            fut_fills = list(reversed(self._futures.get("fills") or []))
            all_fills = sorted(
                spot_fills + fut_fills,
                key=lambda f: str(f.get("time") or ""),
                reverse=True,
            )
            orders = [self._fill_to_order_row(f) for f in all_fills]
        return {
            "mode": "paper",
            "source": "local-paper-ledger",
            "version": LEDGER_VERSION,
            "spot": {
                "usd_balance": self._spot.get("usd_balance"),
                "starting_balance_usd": self._spot.get("starting_balance_usd"),
                "open_positions": sum(1 for rows in (self._spot.get("lots") or {}).values() if rows),
            },
            "futures": {
                "margin_balance_usd": self._futures.get("margin_balance_usd"),
                "starting_margin_usd": self._futures.get("starting_margin_usd"),
                "open_positions": len(self._futures.get("positions") or {}),
            },
            "open_positions_total": self.open_position_count(),
            "max_open_positions": int(self.max_open_positions),
            "position_sizing": {
                "enabled": bool(self.kelly_sizing_enabled),
                "mode": self.kelly_mode if self.kelly_sizing_enabled else "explicit_volume",
            },
            "usd_balance": self._spot.get("usd_balance"),
            "starting_balance_usd": self._spot.get("starting_balance_usd"),
            "orders": orders,
            "open_orders": [],
            "closed_orders": orders,
            "fills": all_fills,
            "note": "Local paper ledger v2 (spot cash + futures margin)",
        }

    def _fill_to_order_row(self, fill: dict[str, Any]) -> dict[str, Any]:
        return {
            "txid": fill.get("txid"),
            "id": fill.get("id"),
            "market_type": fill.get("market_type", "spot"),
            "pair": fill.get("pair"),
            "side": fill.get("side"),
            "type": fill.get("side"),
            "ordertype": fill.get("ordertype"),
            "vol": fill.get("volume"),
            "volume": fill.get("volume"),
            "price": fill.get("price"),
            "fee": fill.get("fee"),
            "leverage": fill.get("leverage"),
            "realized_pnl": fill.get("realized_pnl"),
            "status": "closed",
            "state": "CLOSED",
            "time": fill.get("time"),
            "opentm": fill.get("time"),
            "closetm": fill.get("time"),
            "source": fill.get("source"),
            "pnl": fill.get("realized_pnl"),
        }

    async def performance(self, mark_prices: dict[str, Decimal] | None = None) -> dict[str, Any]:
        async with self._lock:
            state = json.loads(json.dumps(self._state))
        return build_combined_performance(
            state=state,
            mark_prices=mark_prices or {},
            source="local-paper-ledger",
            fee_model=self.fee_model,
        )

    def snapshot_state(self) -> dict[str, Any]:
        return json.loads(json.dumps(self._state))

    def open_volume(self, pair: str, *, market_type: MarketType = "spot") -> Decimal:
        inst = resolve_instrument(market_type, pair)
        if inst.market_type == "futures":
            pos = (self._futures.get("positions") or {}).get(inst.symbol)
            if not pos:
                return Decimal("0")
            return _d(pos.get("contracts"))
        rows = (self._spot.get("lots") or {}).get(inst.symbol) or []
        return sum((_d(r.get("volume")) for r in rows), start=Decimal("0"))


_LEDGER: LocalPaperLedger | None = None


def get_local_paper_ledger(
    *,
    starting_balance_usd: Decimal | None = None,
    starting_margin_usd: Decimal | None = None,
    maker_fee_rate: Decimal | None = None,
    taker_fee_rate: Decimal | None = None,
    max_open_positions: int | None = None,
    kelly_sizing_enabled: bool | None = None,
    kelly_mode: str | None = None,
) -> LocalPaperLedger:
    global _LEDGER
    if _LEDGER is None:
        _LEDGER = LocalPaperLedger(
            starting_balance_usd=starting_balance_usd or Decimal("10000"),
            starting_margin_usd=starting_margin_usd or Decimal("10000"),
            maker_fee_rate=maker_fee_rate if maker_fee_rate is not None else Decimal("0"),
            taker_fee_rate=taker_fee_rate if taker_fee_rate is not None else Decimal("0.0005"),
            max_open_positions=int(max_open_positions) if max_open_positions is not None else 20,
            kelly_sizing_enabled=True if kelly_sizing_enabled is None else bool(kelly_sizing_enabled),
            kelly_mode=kelly_mode or "half_kelly",
        )
    else:
        if max_open_positions is not None:
            _LEDGER.max_open_positions = int(max_open_positions)
        if kelly_sizing_enabled is not None:
            _LEDGER.kelly_sizing_enabled = bool(kelly_sizing_enabled)
        if kelly_mode is not None:
            _LEDGER.kelly_mode = kelly_mode
    return _LEDGER


def reset_local_paper_ledger_for_tests() -> None:
    global _LEDGER
    _LEDGER = None
