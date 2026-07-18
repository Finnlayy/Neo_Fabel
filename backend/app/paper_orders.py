"""Reusable paper-order application service for manual and signal paths."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Literal, Protocol
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from .integrations.kraken_cli import KrakenCli, KrakenCliError
from .models import PaperOrderIntent
from .schemas import PaperOrderRequest, PaperOrderResponse


class PaperOrderSink(Protocol):
    async def paper_order(
        self,
        side: Literal["buy", "sell"],
        pair: str,
        volume: Decimal,
        order_type: Literal["market", "limit"],
        price: Decimal | None,
    ) -> dict[str, Any]: ...


@dataclass(frozen=True)
class PaperOrderService:
    """Shared manual/signal paper-order ledger + dispatch."""

    sink: PaperOrderSink

    async def place_manual(
        self,
        *,
        session: AsyncSession,
        user_uid: str,
        payload: PaperOrderRequest,
        request_id: str,
    ) -> PaperOrderResponse:
        key = str(payload.idempotency_key)
        try:
            existing = await session.scalar(
                select(PaperOrderIntent).where(
                    PaperOrderIntent.user_uid == user_uid,
                    PaperOrderIntent.idempotency_key == key,
                )
            )
            if existing is not None:
                if existing.status == "ACCEPTED" and existing.result is not None:
                    return PaperOrderResponse(
                        idempotency_key=payload.idempotency_key,
                        status="REPLAYED",
                        result=existing.result,
                        request_id=request_id,
                    )
                raise HTTPException(
                    status_code=409,
                    detail={
                        "code": "intent_in_progress",
                        "message": "idempotency key is already in progress",
                        "request_id": request_id,
                    },
                )
            intent = PaperOrderIntent(
                id=str(uuid4()),
                user_uid=user_uid,
                idempotency_key=key,
                pair=payload.pair,
                side=payload.side,
                volume=str(payload.volume),
                order_type=payload.order_type,
                price=str(payload.price) if payload.price is not None else None,
                status="PENDING",
                source="manual",
                source_ref=None,
            )
            session.add(intent)
            await session.commit()
        except HTTPException:
            raise
        except SQLAlchemyError as exc:
            await session.rollback()
            raise HTTPException(
                status_code=503,
                detail={
                    "code": "database_unavailable",
                    "message": "order ledger unavailable",
                    "request_id": request_id,
                },
            ) from exc

        return await self._dispatch(session, intent, payload, request_id)

    async def place_signal(
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
        """Place a paper order for a signal event. event_id is the idempotency key."""
        existing = await session.scalar(
            select(PaperOrderIntent).where(
                PaperOrderIntent.source == "signal",
                PaperOrderIntent.source_ref == event_id,
            )
        )
        if existing is not None:
            if existing.status == "ACCEPTED" and existing.result is not None:
                return {"status": "REPLAYED", "result": existing.result, "intent_id": existing.id}
            if existing.status == "REJECTED":
                raise KrakenCliError(existing.error_code or "api", "prior signal paper order rejected")
            raise KrakenCliError("intent_in_progress", "signal paper intent already in progress", retryable=True)

        intent = PaperOrderIntent(
            id=str(uuid4()),
            user_uid=user_uid,
            idempotency_key=event_id,
            pair=pair,
            side=side,
            volume=str(volume),
            order_type=order_type,
            price=str(price) if price is not None else None,
            status="PENDING",
            source="signal",
            source_ref=event_id,
        )
        session.add(intent)
        await session.commit()

        try:
            result = await self.sink.paper_order(side, pair, volume, order_type, price)
        except KrakenCliError as exc:
            intent.status = "REJECTED"
            intent.error_code = exc.category
            await session.commit()
            raise
        intent.status = "ACCEPTED"
        intent.result = result
        intent.completed_at = datetime.now(UTC)
        await session.commit()
        return {"status": "ACCEPTED", "result": result, "intent_id": intent.id}

    async def _dispatch(
        self,
        session: AsyncSession,
        intent: PaperOrderIntent,
        payload: PaperOrderRequest,
        request_id: str,
    ) -> PaperOrderResponse:
        try:
            result = await self.sink.paper_order(
                payload.side,
                payload.pair,
                payload.volume,
                payload.order_type,
                payload.price,
            )
        except KrakenCliError as exc:
            intent.status = "REJECTED"
            intent.error_code = exc.category
            await session.commit()
            status = 503 if exc.retryable else 422
            raise HTTPException(
                status_code=status,
                detail={"code": exc.category, "message": str(exc), "request_id": request_id},
            ) from exc
        intent.status = "ACCEPTED"
        intent.result = result
        intent.completed_at = datetime.now(UTC)
        await session.commit()
        return PaperOrderResponse(
            idempotency_key=payload.idempotency_key,
            status="ACCEPTED",
            result=result,
            request_id=request_id,
        )


def kraken_paper_sink(cli: KrakenCli) -> PaperOrderSink:
    return cli
