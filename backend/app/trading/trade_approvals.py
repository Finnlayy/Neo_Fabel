"""Telegram human verification for live trade proposals."""

from __future__ import annotations

import logging
import secrets
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from threading import Lock
from typing import Any, Literal

logger = logging.getLogger("neo_fabel.trading.trade_approvals")

ProposalStatus = Literal["pending", "approved", "rejected", "expired", "executed", "failed"]

_LOCK = Lock()
_PROPOSALS: dict[str, TradeProposal] = {}
_DEFAULT_TTL_SEC = 900  # 15 minutes


@dataclass
class TradeProposal:
    proposal_id: str
    side: str
    pair: str
    volume: str
    order_type: str = "market"
    price: str | None = None
    confidence_pct: float | None = None
    rationale: str | None = None
    status: ProposalStatus = "pending"
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat().replace("+00:00", "Z"))
    decided_at: str | None = None
    decided_by: str | None = None
    result: dict[str, Any] | None = None
    error: str | None = None
    expires_at_monotonic: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("expires_at_monotonic", None)
        return data

    def expired(self) -> bool:
        return time.monotonic() >= self.expires_at_monotonic


class TradeApprovalQueue:
    def create(
        self,
        *,
        side: str,
        pair: str,
        volume: Decimal | str | float,
        order_type: str = "market",
        price: Decimal | str | float | None = None,
        confidence_pct: float | None = None,
        rationale: str | None = None,
        ttl_seconds: int = _DEFAULT_TTL_SEC,
    ) -> TradeProposal:
        pid = secrets.token_urlsafe(16)
        proposal = TradeProposal(
            proposal_id=pid,
            side=str(side).lower(),
            pair=str(pair).upper(),
            volume=format(Decimal(str(volume)), "f"),
            order_type=str(order_type).lower(),
            price=format(Decimal(str(price)), "f") if price is not None else None,
            confidence_pct=float(confidence_pct) if confidence_pct is not None else None,
            rationale=(rationale or "")[:500] or None,
            expires_at_monotonic=time.monotonic() + max(60, int(ttl_seconds)),
        )
        with _LOCK:
            self._expire_locked()
            _PROPOSALS[pid] = proposal
        return proposal

    def get(self, proposal_id: str) -> TradeProposal | None:
        with _LOCK:
            self._expire_locked()
            return _PROPOSALS.get(proposal_id)

    def list_pending(self) -> list[TradeProposal]:
        with _LOCK:
            self._expire_locked()
            return [p for p in _PROPOSALS.values() if p.status == "pending"]

    def decide(self, proposal_id: str, *, approve: bool, by: str = "telegram") -> TradeProposal | None:
        with _LOCK:
            self._expire_locked()
            proposal = _PROPOSALS.get(proposal_id)
            if proposal is None:
                return None
            if proposal.status != "pending":
                return proposal
            proposal.status = "approved" if approve else "rejected"
            proposal.decided_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
            proposal.decided_by = by
            return proposal

    def mark_executed(self, proposal_id: str, result: dict[str, Any]) -> None:
        with _LOCK:
            proposal = _PROPOSALS.get(proposal_id)
            if proposal is None:
                return
            proposal.status = "executed"
            proposal.result = result

    def mark_failed(self, proposal_id: str, error: str) -> None:
        with _LOCK:
            proposal = _PROPOSALS.get(proposal_id)
            if proposal is None:
                return
            proposal.status = "failed"
            proposal.error = error[:500]

    def _expire_locked(self) -> None:
        now = time.monotonic()
        for proposal in _PROPOSALS.values():
            if proposal.status == "pending" and now >= proposal.expires_at_monotonic:
                proposal.status = "expired"
                proposal.decided_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
                proposal.decided_by = "ttl"


trade_approvals = TradeApprovalQueue()


def format_proposal_message(proposal: TradeProposal) -> str:
    conf = (
        f"{proposal.confidence_pct:.1f}%"
        if proposal.confidence_pct is not None
        else "n/a"
    )
    lines = [
        "🔐 <b>LIVE TRADE APPROVAL REQUIRED</b>",
        "",
        f"• <b>ID:</b> <code>{proposal.proposal_id}</code>",
        f"• <b>Side:</b> {proposal.side.upper()}",
        f"• <b>Pair:</b> {proposal.pair}",
        f"• <b>Volume:</b> {proposal.volume}",
        f"• <b>Type:</b> {proposal.order_type}",
    ]
    if proposal.price:
        lines.append(f"• <b>Price:</b> {proposal.price}")
    lines.append(f"• <b>Confidence:</b> {conf}")
    if proposal.rationale:
        lines.append(f"• <b>Why:</b> {proposal.rationale}")
    lines.extend(
        [
            "",
            f"Reply <code>/approve {proposal.proposal_id}</code> or <code>/reject {proposal.proposal_id}</code>",
            "or tap the buttons below.",
        ]
    )
    return "\n".join(lines)


def approval_keyboard(proposal_id: str) -> dict[str, Any]:
    return {
        "inline_keyboard": [
            [
                {"text": "✅ Approve", "callback_data": f"tv:ok:{proposal_id}"},
                {"text": "❌ Reject", "callback_data": f"tv:no:{proposal_id}"},
            ]
        ]
    }


async def send_trade_proposal_telegram(
    settings: Any,
    proposal: TradeProposal,
) -> dict[str, Any] | None:
    try:
        from backend.app.integrations.telegram_bot import (
            TelegramBot,
            TelegramNotConfigured,
            push_local_signal,
        )

        bot = TelegramBot(settings)
        if not bot.configured:
            return None
        text = format_proposal_message(proposal)
        result = await bot.send_message(
            text,
            parse_mode="HTML",
            reply_markup=approval_keyboard(proposal.proposal_id),
        )
        push_local_signal(message=text, channel="TRADE APPROVAL")
        return result if isinstance(result, dict) else {"ok": True}
    except TelegramNotConfigured:
        return None
    except Exception as exc:  # noqa: BLE001
        logger.warning("trade proposal telegram failed: %s", exc)
        return None


async def execute_approved_proposal(proposal_id: str, *, by: str = "telegram") -> dict[str, Any]:
    """Mark approved and place via the bound Level4 live session when possible."""
    proposal = trade_approvals.decide(proposal_id, approve=True, by=by)
    if proposal is None:
        return {"ok": False, "reason": "not_found"}
    if proposal.status == "rejected":
        return {"ok": False, "reason": "already_rejected", "proposal": proposal.to_dict()}
    if proposal.status == "expired":
        return {"ok": False, "reason": "expired", "proposal": proposal.to_dict()}
    if proposal.status == "executed":
        return {"ok": True, "reason": "already_executed", "proposal": proposal.to_dict()}
    if proposal.status != "approved":
        return {"ok": False, "reason": proposal.status, "proposal": proposal.to_dict()}

    from backend.app.trading.loops import trading_loops

    session = getattr(trading_loops, "_session", None)
    if session is None:
        trade_approvals.mark_failed(proposal_id, "no live session bound")
        return {"ok": False, "reason": "no_session", "proposal": proposal.to_dict()}

    try:
        price = Decimal(proposal.price) if proposal.price else None
        # Bypass human gate for the actual placement after explicit approval.
        result = await session.execute_order(
            proposal.side,  # type: ignore[arg-type]
            proposal.pair,
            Decimal(proposal.volume),
            proposal.order_type,  # type: ignore[arg-type]
            price,
            skip_human_verification=True,
        )
        trade_approvals.mark_executed(proposal_id, result if isinstance(result, dict) else {"ok": True})
        executed = trade_approvals.get(proposal_id)
        return {
            "ok": True,
            "proposal": executed.to_dict() if executed is not None else None,
            "result": result,
        }
    except Exception as exc:  # noqa: BLE001
        trade_approvals.mark_failed(proposal_id, str(exc))
        return {"ok": False, "reason": "execution_failed", "error": str(exc), "proposal": proposal.to_dict()}


async def reject_proposal(proposal_id: str, *, by: str = "telegram") -> dict[str, Any]:
    proposal = trade_approvals.decide(proposal_id, approve=False, by=by)
    if proposal is None:
        return {"ok": False, "reason": "not_found"}
    return {"ok": True, "proposal": proposal.to_dict()}
