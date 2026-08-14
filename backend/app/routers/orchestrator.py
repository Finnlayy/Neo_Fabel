"""Authenticated, advisory-only orchestrator API."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any, Literal, cast
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.app.auth import require_user
from backend.app.database import SessionFactory
from backend.app.integrations.gemini_client import AiNotConfigured
from backend.app.orchestrator.repository import append_decision, list_decisions
from backend.app.orchestrator.schemas import (
    DecisionHistoryItem,
    DecisionHistoryResponse,
    FullDecisionRequest,
    FullDecisionResponse,
    MarketRegimeRequest,
    MarketRegimeResponse,
    SignalQualityRequest,
    SignalQualityResponse,
    SourceCoverage,
)
from backend.app.orchestrator.service import (
    AdvisoryOrchestrator,
    AdvisoryOutputError,
    AdvisoryResult,
)
from backend.app.settings import Settings, get_settings

logger = logging.getLogger("neo_fabel.orchestrator")
router = APIRouter(prefix="/api/v1/orchestrator", tags=["orchestrator"])
DecisionType = Literal["market_regime", "signal_quality", "full_decision"]


def _service(settings: Settings = Depends(get_settings)) -> AdvisoryOrchestrator:
    return AdvisoryOrchestrator(settings)


def _summary(body: MarketRegimeRequest | SignalQualityRequest | FullDecisionRequest) -> dict[str, Any]:
    if isinstance(body, SignalQualityRequest):
        return {
            "symbol": body.symbol,
            "signal_id": body.signal.id,
            "sentiment": body.signal.sentiment,
            "has_neural": body.neural_prediction is not None,
            "has_rna": body.rna_pattern is not None,
            "has_position_cost": body.position_cost is not None,
        }
    return {
        "ticker_count": len(body.tickers),
        "symbols": [ticker.symbol for ticker in body.tickers],
        "signal_count": len(body.signals),
        "resolved_signal_symbols": [
            signal.symbol for signal in body.signals if signal.symbol
        ],
        "neural_symbol_count": len(body.neural_states),
        "rna_symbol_count": len(body.rna_patterns),
        "recent_trade_count": len(getattr(body, "recent_trades", [])),
    }


async def _audit(
    *,
    user_uid: str,
    request_id: str,
    decision_type: DecisionType,
    body: MarketRegimeRequest | SignalQualityRequest | FullDecisionRequest,
    result: AdvisoryResult,
) -> bool:
    payload = {
        **result.payload.model_dump(mode="json", by_alias=True),
        "sourceCoverage": result.coverage.model_dump(mode="json", by_alias=True),
    }
    reasoning = payload.get("reasoning") or payload.get("regimeReasoning")
    try:
        async with SessionFactory() as session:
            await append_decision(
                session,
                user_uid=user_uid,
                request_id=request_id,
                decision_type=decision_type,
                provider=result.provider,
                model=result.model,
                input_summary=_summary(body),
                output_data=payload,
                reasoning=str(reasoning)[:2_000] if reasoning else None,
            )
        return True
    except Exception:  # noqa: BLE001 - advisory remains usable when audit DB is down
        logger.exception("orchestrator audit persistence failed request_id=%s", request_id)
        return False


def _error(exc: Exception, request_id: str) -> HTTPException:
    if isinstance(exc, AiNotConfigured):
        return HTTPException(
            status_code=503,
            detail={
                "code": "orchestrator_unavailable",
                "message": str(exc),
                "request_id": request_id,
            },
        )
    if isinstance(exc, AdvisoryOutputError):
        return HTTPException(
            status_code=502,
            detail={
                "code": "invalid_advisory_output",
                "message": str(exc),
                "request_id": request_id,
            },
        )
    logger.exception("orchestrator provider failure request_id=%s", request_id)
    return HTTPException(
        status_code=502,
        detail={
            "code": "orchestrator_provider_error",
            "message": "Advisory provider failed",
            "request_id": request_id,
        },
    )


def _response_values(
    result: AdvisoryResult,
    *,
    request_id: str,
    audit_persisted: bool,
    timestamp: datetime,
) -> dict[str, Any]:
    return {
        **result.payload.model_dump(),
        "request_id": request_id,
        "provider": result.provider,
        "model": result.model,
        "source_coverage": result.coverage,
        "audit_persisted": audit_persisted,
        "timestamp": timestamp,
    }


@router.post("/market-regime", response_model=MarketRegimeResponse)
async def market_regime(
    body: MarketRegimeRequest,
    user: dict[str, Any] = Depends(require_user),
    service: AdvisoryOrchestrator = Depends(_service),
) -> MarketRegimeResponse:
    request_id = str(uuid4())
    timestamp = datetime.now(UTC)
    try:
        result = await service.analyze_market_regime(body)
    except Exception as exc:  # noqa: BLE001
        raise _error(exc, request_id) from exc
    persisted = await _audit(
        user_uid=str(user["uid"]),
        request_id=request_id,
        decision_type="market_regime",
        body=body,
        result=result,
    )
    return MarketRegimeResponse.model_validate(
        _response_values(result, request_id=request_id, audit_persisted=persisted, timestamp=timestamp)
    )


@router.post("/signal-quality", response_model=SignalQualityResponse)
async def signal_quality(
    body: SignalQualityRequest,
    user: dict[str, Any] = Depends(require_user),
    service: AdvisoryOrchestrator = Depends(_service),
) -> SignalQualityResponse:
    request_id = str(uuid4())
    timestamp = datetime.now(UTC)
    try:
        result = await service.score_signal_quality(body)
    except Exception as exc:  # noqa: BLE001
        raise _error(exc, request_id) from exc
    persisted = await _audit(
        user_uid=str(user["uid"]),
        request_id=request_id,
        decision_type="signal_quality",
        body=body,
        result=result,
    )
    return SignalQualityResponse.model_validate(
        _response_values(result, request_id=request_id, audit_persisted=persisted, timestamp=timestamp)
    )


@router.post("/full-decision", response_model=FullDecisionResponse)
async def full_decision(
    body: FullDecisionRequest,
    user: dict[str, Any] = Depends(require_user),
    service: AdvisoryOrchestrator = Depends(_service),
) -> FullDecisionResponse:
    request_id = str(uuid4())
    timestamp = datetime.now(UTC)
    try:
        result = await service.full_decision(body)
    except Exception as exc:  # noqa: BLE001
        raise _error(exc, request_id) from exc
    persisted = await _audit(
        user_uid=str(user["uid"]),
        request_id=request_id,
        decision_type="full_decision",
        body=body,
        result=result,
    )
    return FullDecisionResponse.model_validate(
        _response_values(result, request_id=request_id, audit_persisted=persisted, timestamp=timestamp)
    )


@router.get("/decisions", response_model=DecisionHistoryResponse)
async def decisions(
    limit: int = Query(default=20, ge=1, le=100),
    decision_type: DecisionType | None = Query(default=None, alias="type"),
    user: dict[str, Any] = Depends(require_user),
) -> DecisionHistoryResponse:
    request_id = str(uuid4())
    timestamp = datetime.now(UTC)
    try:
        async with SessionFactory() as session:
            rows = await list_decisions(
                session,
                user_uid=str(user["uid"]),
                limit=limit,
                decision_type=decision_type,
            )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=503,
            detail={
                "code": "orchestrator_history_unavailable",
                "message": "Decision history is unavailable",
                "request_id": request_id,
            },
        ) from exc
    return DecisionHistoryResponse(
        request_id=request_id,
        source_coverage=SourceCoverage(
            market_data=False,
            telegram_signals=False,
            neural_states=False,
            rna_patterns=False,
            recent_trades=False,
        ),
        timestamp=timestamp,
        decisions=[
            DecisionHistoryItem(
                id=row.id,
                request_id=row.request_id,
                decision_type=cast(
                    Literal["market_regime", "signal_quality", "full_decision"],
                    row.decision_type,
                ),
                provider=row.provider,
                model=row.model,
                status=cast(Literal["success", "error"], row.status),
                output_data=row.output_data,
                reasoning=row.reasoning,
                timestamp=row.created_at,
            )
            for row in rows
        ],
    )
