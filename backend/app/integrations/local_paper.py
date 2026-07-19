"""In-process paper ledger for hosts without Kraken CLI (Windows) or as CLI fallback.

Still paper-only — never touches live exchange APIs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from threading import Lock
from typing import Any, Literal
from uuid import uuid4


def _normalize_pair(pair: str) -> str:
    return pair.strip().upper().replace("/", "").replace("-", "")


@dataclass
class LocalPaperLedger:
    """Thread-safe memory book of accepted paper fills."""

    _lock: Lock = field(default_factory=Lock, repr=False)
    _orders: list[dict[str, Any]] = field(default_factory=list)

    async def paper_order(
        self,
        side: Literal["buy", "sell"],
        pair: str,
        volume: Decimal,
        order_type: Literal["market", "limit"],
        price: Decimal | None,
    ) -> dict[str, Any]:
        if side not in {"buy", "sell"} or order_type not in {"market", "limit"}:
            raise ValueError("unsupported paper order")
        if volume <= 0 or (order_type == "limit" and (price is None or price <= 0)):
            raise ValueError("invalid paper order values")

        fill_price = price if price is not None else Decimal("0")
        order_id = f"LOCAL-{uuid4().hex[:12].upper()}"
        now = datetime.now(UTC).isoformat()
        row = {
            "txid": order_id,
            "id": order_id,
            "pair": _normalize_pair(pair),
            "side": side,
            "type": side,
            "ordertype": order_type,
            "vol": format(volume, "f"),
            "volume": format(volume, "f"),
            "price": format(fill_price, "f") if fill_price > 0 else "0",
            "status": "closed",
            "state": "CLOSED",
            "time": now,
            "opentm": now,
            "closetm": now,
            "source": "local-paper-ledger",
            "pnl": "0",
        }
        with self._lock:
            self._orders.insert(0, row)
            # Cap history
            del self._orders[500:]
        return {
            "ok": True,
            "source": "local-paper-ledger",
            "txid": [order_id],
            "descr": {"order": f"{side} {_normalize_pair(pair)} {format(volume, 'f')} {order_type}"},
            "order": row,
        }

    async def paper_status(self) -> dict[str, Any]:
        with self._lock:
            orders = list(self._orders)
        return {
            "mode": "paper",
            "source": "local-paper-ledger",
            "orders": orders,
            "open_orders": [],
            "closed_orders": orders,
            "note": "Local paper ledger (Kraken CLI unavailable on this host)",
        }


_LEDGER = LocalPaperLedger()


def get_local_paper_ledger() -> LocalPaperLedger:
    return _LEDGER
