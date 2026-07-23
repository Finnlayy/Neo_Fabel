"""Persistence helpers for user-scoped advisory decisions."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import Select, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models import OrchestratorDecisionLog


async def append_decision(
    session: AsyncSession,
    *,
    user_uid: str,
    request_id: str,
    decision_type: str,
    provider: str,
    model: str,
    input_summary: dict[str, Any],
    output_data: dict[str, Any],
    reasoning: str | None,
) -> OrchestratorDecisionLog:
    row = OrchestratorDecisionLog(
        id=str(uuid4()),
        user_uid=user_uid,
        request_id=request_id,
        decision_type=decision_type,
        provider=provider,
        model=model,
        status="success",
        input_summary=input_summary,
        output_data=output_data,
        reasoning=reasoning,
        created_at=datetime.now(UTC),
    )
    session.add(row)
    await session.commit()
    return row


async def list_decisions(
    session: AsyncSession,
    *,
    user_uid: str,
    limit: int,
    decision_type: str | None,
) -> list[OrchestratorDecisionLog]:
    statement: Select[tuple[OrchestratorDecisionLog]] = select(OrchestratorDecisionLog).where(
        OrchestratorDecisionLog.user_uid == user_uid
    )
    if decision_type:
        statement = statement.where(OrchestratorDecisionLog.decision_type == decision_type)
    statement = statement.order_by(desc(OrchestratorDecisionLog.created_at)).limit(limit)
    result = await session.execute(statement)
    return list(result.scalars().all())
