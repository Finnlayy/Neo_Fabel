"""PaperExecutionPort — only this adapter reaches PaperOrderService for signals."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Literal, Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from ..paper_orders import PaperOrderService


class PaperExecutionPort(Protocol):
    async def submit_paper(
        self,
        *,
        session: AsyncSession,
        user_uid: str,
        event_id: str,
        pair: str,
        side: Literal["buy", "sell"],
        volume: Decimal,
        order_type: Literal["market", "limit"],
        price: Decimal | None,
        request_id: str,
    ) -> dict[str, Any]: ...


@dataclass
class PaperOrderExecutionAdapter:
    service: PaperOrderService

    async def submit_paper(
        self,
        *,
        session: AsyncSession,
        user_uid: str,
        event_id: str,
        pair: str,
        side: Literal["buy", "sell"],
        volume: Decimal,
        order_type: Literal["market", "limit"],
        price: Decimal | None,
        request_id: str,
    ) -> dict[str, Any]:
        return await self.service.place_signal(
            session=session,
            user_uid=user_uid,
            event_id=event_id,
            pair=pair,
            side=side,
            volume=volume,
            order_type=order_type,
            price=price,
            request_id=request_id,
        )


@dataclass
class FakePaperExecutionPort:
    """Test sink that records calls without invoking Kraken."""

    calls: list[dict[str, Any]]
    fail_with: Exception | None = None
    hang_after_claim: bool = False

    async def submit_paper(
        self,
        *,
        session: AsyncSession,
        user_uid: str,
        event_id: str,
        pair: str,
        side: Literal["buy", "sell"],
        volume: Decimal,
        order_type: Literal["market", "limit"],
        price: Decimal | None,
        request_id: str,
    ) -> dict[str, Any]:
        call = {
            "user_uid": user_uid,
            "event_id": event_id,
            "pair": pair,
            "side": side,
            "volume": str(volume),
            "order_type": order_type,
            "price": str(price) if price is not None else None,
            "request_id": request_id,
        }
        self.calls.append(call)
        if self.hang_after_claim:
            raise TimeoutError("simulated post-dispatch uncertainty")
        if self.fail_with is not None:
            raise self.fail_with
        return {"status": "ACCEPTED", "result": {"fake": True}, "intent_id": f"fake-{event_id}"}
