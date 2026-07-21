"""Level 4 session orchestration: preflight, dead-man switch, and guarded order flow."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Literal

from ..integrations.kraken_cli import KrakenCli, KrakenCliError
from .autonomy import AutonomyLevel, require_autonomy
from .guardrails import GuardrailViolation, TradingGuardrails
from .live_session_ledger import normalize_pair
from .position_sizing import PositionSizingPolicy, compute_notional_eur, volume_from_notional
from .session_policy import (
    SessionRiskPolicy,
    assert_confidence_ok,
    assert_daily_loss_ok,
    assert_market_hours_allowed,
)

if TYPE_CHECKING:
    from ..settings import Settings


@dataclass(frozen=True)
class PreflightResult:
    ok: bool
    checks: list[dict[str, Any]]
    autonomy_level: int
    live_trading_enabled: bool


class Level4Session:
    """Guarded autonomous trading session (Level 4).

    Hard gates:
    - KRAKEN_AUTONOMY_LEVEL >= 4
    - KRAKEN_LIVE_TRADING_ENABLED=true
    - Guardrails (pair, size, open positions, rate)
    - Dead man's switch must be armed before orders
    """

    def __init__(self, settings: Settings, cli: KrakenCli | None = None):
        from ..settings import get_trade_rate_limiter

        self.settings = settings
        self.guardrails: TradingGuardrails = settings.trading_guardrails()
        self.rate_limiter = get_trade_rate_limiter()
        if cli is not None:
            self.cli = cli
        else:
            from ..integrations.paper_factory import build_kraken_cli

            self.cli = build_kraken_cli(settings)
        self._deadman_armed = False
        self.sizing_policy: PositionSizingPolicy | None = None
        self.session_capital_eur: float | None = None
        self.session_max_margin_eur: float | None = None
        self.risk_policy: SessionRiskPolicy | None = None

    def set_sizing_policy(
        self,
        policy: PositionSizingPolicy,
        *,
        capital_eur: float,
        max_margin_eur: float,
    ) -> None:
        self.sizing_policy = policy
        self.session_capital_eur = float(capital_eur)
        self.session_max_margin_eur = float(max_margin_eur)

    def set_risk_policy(self, policy: SessionRiskPolicy) -> None:
        self.risk_policy = policy

    def resolve_order_volume(
        self,
        *,
        price: Decimal,
        confidence: float | None = None,
        stop_pct: float | None = None,
        take_pct: float | None = None,
        volume: Decimal | None = None,
    ) -> tuple[Decimal, dict[str, Any]]:
        """Return (volume, sizing_detail). Explicit volume wins when provided."""
        if volume is not None and volume > 0:
            return volume, {"mode": "explicit_volume", "volume": str(volume)}
        if self.sizing_policy is None:
            raise ValueError("no position sizing policy set for this session")
        capital = float(self.session_capital_eur or 0)
        margin = float(self.session_max_margin_eur or capital)
        detail = compute_notional_eur(
            self.sizing_policy,
            capital_eur=capital,
            max_margin_eur=margin,
            confidence=confidence,
            stop_pct=stop_pct,
            take_pct=take_pct,
        )
        notional = float(detail.get("notional_eur") or 0)
        if notional <= 0:
            raise ValueError("sizing resolved to zero notional")
        sized = volume_from_notional(notional_eur=notional, price=price)
        detail["volume"] = str(sized)
        return sized, detail

    def apply_session_limits(
        self,
        *,
        max_margin_eur: float,
        max_concurrent_trades: int,
        symbols: list[str] | None = None,
    ) -> TradingGuardrails:
        """Tighten env guardrails for one live session (never widen)."""
        base = self.guardrails
        margin = Decimal(str(max_margin_eur))
        if margin <= 0:
            raise ValueError("max_margin_eur must be > 0")
        if max_concurrent_trades < 1 or max_concurrent_trades > 10:
            raise ValueError("max_concurrent_trades must be 1..10")

        requested = [normalize_pair(s) for s in (symbols or []) if normalize_pair(s)]
        if requested:
            unknown = [s for s in requested if s not in base.pair_allowlist]
            if unknown:
                raise ValueError(
                    "symbols outside env allowlist: "
                    + ",".join(unknown)
                    + f" (env={','.join(sorted(base.pair_allowlist))})"
                )
            pairs = frozenset(requested)
        else:
            pairs = base.pair_allowlist

        tightened = TradingGuardrails(
            max_order_size=base.max_order_size,
            max_notional=min(base.max_notional, margin),
            max_open_positions=min(base.max_open_positions, int(max_concurrent_trades)),
            max_trades_per_hour=base.max_trades_per_hour,
            min_trade_interval_seconds=base.min_trade_interval_seconds,
            pair_allowlist=pairs,
        )
        self.guardrails = tightened
        return tightened

    def _assert_level4(self) -> None:
        require_autonomy(self.settings.autonomy, AutonomyLevel.AUTONOMOUS)
        if not self.settings.kraken_live_trading_enabled:
            raise PermissionError("KRAKEN_LIVE_TRADING_ENABLED must be true for Level 4")

    async def preflight(self) -> PreflightResult:
        checks: list[dict[str, Any]] = []

        def record(name: str, ok: bool, detail: str = "") -> None:
            checks.append({"name": name, "ok": ok, "detail": detail})

        record(
            "autonomy_level",
            self.settings.autonomy >= AutonomyLevel.AUTONOMOUS,
            f"level={int(self.settings.autonomy)}",
        )
        record(
            "live_trading_flag",
            self.settings.kraken_live_trading_enabled,
            f"enabled={self.settings.kraken_live_trading_enabled}",
        )
        record(
            "withdrawal_note",
            True,
            "API key must be trade-only (no Withdraw Funds / no funding permissions)",
        )
        record(
            "capital_policy",
            True,
            "no external replenish; no debt/leverage>1; no negative cash; max notional enforced",
        )

        try:
            await self.cli.auth_test()
            record("auth_test", True)
        except KrakenCliError as exc:
            record("auth_test", False, f"{exc.category}: {exc}")

        try:
            await self.cli.balance()
            record("balance", True)
        except KrakenCliError as exc:
            record("balance", False, f"{exc.category}: {exc}")

        for pair in sorted(self.guardrails.pair_allowlist):
            try:
                await self.cli.pairs(pair)
                record(f"pair_{pair}", True)
            except KrakenCliError as exc:
                record(f"pair_{pair}", False, f"{exc.category}: {exc}")

        ok = all(item["ok"] for item in checks if item["name"] != "withdrawal_note")
        return PreflightResult(
            ok=ok,
            checks=checks,
            autonomy_level=int(self.settings.autonomy),
            live_trading_enabled=self.settings.kraken_live_trading_enabled,
        )

    async def arm_deadman(self) -> dict[str, Any]:
        self._assert_level4()
        result = await self.cli.cancel_after(self.settings.kraken_deadman_seconds)
        self._deadman_armed = True
        return result

    async def refresh_deadman(self) -> dict[str, Any]:
        return await self.arm_deadman()

    async def monitor_snapshot(self) -> dict[str, Any]:
        """Level 1 monitoring view — safe at any autonomy level with query keys.

        When live trading is disabled, skip the Kraken CLI entirely (paper research
        must not require a local `kraken` binary).
        """
        balance: dict[str, Any] | None = None
        open_orders: dict[str, Any] | None = None
        errors: list[dict[str, str]] = []
        paper_only = not self.settings.kraken_live_trading_enabled

        if not paper_only:
            try:
                balance = await self.cli.balance()
            except KrakenCliError as exc:
                errors.append({"source": "balance", "category": exc.category, "message": str(exc)})
            try:
                open_orders = await self.cli.open_orders()
            except KrakenCliError as exc:
                errors.append({"source": "open_orders", "category": exc.category, "message": str(exc)})

        return {
            "autonomy_level": int(self.settings.autonomy),
            "paper_only": paper_only,
            "deadman_seconds": self.settings.kraken_deadman_seconds,
            "deadman_armed": self._deadman_armed,
            "guardrails": {
                "max_order_size": str(self.guardrails.max_order_size),
                "max_notional": str(self.guardrails.max_notional),
                "max_open_positions": self.guardrails.max_open_positions,
                "max_trades_per_hour": self.guardrails.max_trades_per_hour,
                "min_trade_interval_seconds": self.guardrails.min_trade_interval_seconds,
                "pair_allowlist": sorted(self.guardrails.pair_allowlist),
                "trades_in_last_hour": self.rate_limiter.trades_in_window(),
            },
            "balance": balance,
            "open_orders": open_orders,
            "errors": errors,
            "note": (
                "Kraken CLI skipped — live trading disabled; paper lots via /api/v1/positions"
                if paper_only
                else None
            ),
        }

    async def execute_order(
        self,
        side: Literal["buy", "sell"],
        pair: str,
        volume: Decimal,
        order_type: Literal["market", "limit"] = "limit",
        price: Decimal | None = None,
        *,
        open_positions: int | None = None,
        confidence_pct: float | None = None,
        rationale: str | None = None,
        skip_human_verification: bool = False,
    ) -> dict[str, Any]:
        """Validate, guardrail-check, then place with --yes (Level 4).

        When session human_verification is on (and not skipped), queues a Telegram
        approval instead of placing immediately.
        """
        self._assert_level4()
        if not self._deadman_armed:
            raise PermissionError("dead man's switch must be armed before autonomous orders")

        risk = self.risk_policy
        if risk is not None:
            try:
                assert_market_hours_allowed(pair, allow_pre_post_market=risk.allow_pre_post_market)
                assert_confidence_ok(confidence_pct, min_confidence_pct=risk.min_confidence_pct)
                from backend.app.trading.live_session_ledger import live_session_ledger

                day_loss = float((live_session_ledger.active or {}).get("realized_loss_eur_today") or 0)
                assert_daily_loss_ok(
                    realized_loss_eur=day_loss,
                    daily_loss_limit_eur=risk.daily_loss_limit_eur(),
                )
            except ValueError as exc:
                from backend.app.trading.live_audit import log_live_event

                log_live_event(
                    "live_reject",
                    code="session_policy",
                    message=str(exc),
                    side=side,
                    pair=pair,
                    volume=str(volume),
                )
                raise KrakenCliError("validation", f"session_policy: {exc}") from exc

            if risk.human_verification and not skip_human_verification:
                from backend.app.trading.trade_approvals import (
                    send_trade_proposal_telegram,
                    trade_approvals,
                )

                proposal = trade_approvals.create(
                    side=side,
                    pair=pair,
                    volume=volume,
                    order_type=order_type,
                    price=price,
                    confidence_pct=confidence_pct,
                    rationale=rationale,
                )
                await send_trade_proposal_telegram(self.settings, proposal)
                from backend.app.trading.live_audit import log_live_event

                log_live_event(
                    "live_awaiting_approval",
                    proposal_id=proposal.proposal_id,
                    side=side,
                    pair=pair,
                    volume=str(volume),
                )
                return {
                    "status": "awaiting_approval",
                    "proposal_id": proposal.proposal_id,
                    "proposal": proposal.to_dict(),
                }

        if open_positions is None:
            try:
                orders = await self.cli.open_orders()
                open_positions = _count_open(orders)
            except KrakenCliError as exc:
                if exc.category == "auth":
                    raise
                raise KrakenCliError(exc.category, str(exc), retryable=exc.retryable) from exc

        try:
            normalized = self.guardrails.check_order(
                pair=pair, volume=volume, open_positions=open_positions
            )
            self.rate_limiter.assert_can_trade()
            from backend.app.integrations.kraken_status import assert_safe_to_trade_pair

            assert_safe_to_trade_pair(normalized)
            balance = await self.cli.balance()
            from backend.app.trading.capital_policy import assert_live_order_capital

            assert_live_order_capital(
                side=side,
                pair=normalized,
                volume=volume,
                price=price,
                balance_payload=balance if isinstance(balance, dict) else None,
                market_type="spot",
                leverage=1,
                reduce_only=False,
                max_notional=self.guardrails.max_notional,
            )
        except GuardrailViolation as exc:
            from backend.app.trading.live_audit import log_live_event

            log_live_event(
                "live_reject",
                code=exc.code,
                message=str(exc),
                side=side,
                pair=pair,
                volume=str(volume),
            )
            raise KrakenCliError("validation", f"{exc.code}: {exc}") from exc

        try:
            await self.cli.validate_order(side, normalized, volume, order_type, price)
        except KrakenCliError as exc:
            if exc.category in {"validation", "api"}:
                raise
            if exc.category == "auth":
                raise
            if exc.category == "rate_limit":
                raise KrakenCliError("rate_limit", str(exc), retryable=True) from exc
            if exc.category == "network":
                raise KrakenCliError("network", str(exc), retryable=True) from exc
            raise

        result = await self.cli.place_order(side, normalized, volume, order_type, price, yes=True)
        self.rate_limiter.record_trade()
        from backend.app.trading.live_audit import log_live_event

        log_live_event(
            "live_place",
            side=side,
            pair=normalized,
            volume=str(volume),
            order_type=order_type,
            price=str(price) if price is not None else None,
            source="level4_session",
        )
        return result


def _count_open(payload: dict[str, Any]) -> int:
    for key in ("open", "result", "orders"):
        value = payload.get(key)
        if isinstance(value, dict):
            return len(value)
        if isinstance(value, list):
            return len(value)
    return 0
