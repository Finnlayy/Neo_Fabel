"""Runtime paper / live trading loop controller (UI switches).

Live start never flips KRAKEN_LIVE_TRADING_ENABLED — it only arms a session
when env gates already allow Level 4. Callers must supply session caps
(max margin, max concurrent trades; optional symbol allowlist).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from backend.app.settings import Settings, get_settings
from backend.app.trading.autonomy import AutonomyLevel
from backend.app.trading.live_session_ledger import live_session_ledger, parse_symbol_list
from backend.app.trading.position_sizing import validate_sizing_policy
from backend.app.trading.session import Level4Session
from backend.app.trading.session_policy import validate_session_risk_policy

logger = logging.getLogger("neo_fabel.trading.loops")


class TradingLoopsService:
    def __init__(self) -> None:
        self._paper_task: asyncio.Task[None] | None = None
        self._live_task: asyncio.Task[None] | None = None
        self._paper_running = False
        self._live_running = False
        self._live_blocked_reason: str | None = None
        self._live_last_error: str | None = None
        self._paper_last_error: str | None = None
        self._session: Level4Session | None = None

    def bind_session(self, session: Level4Session) -> None:
        self._session = session

    def status(self, settings: Settings | None = None) -> dict[str, Any]:
        cfg = settings or get_settings()
        live_enabled = bool(cfg.kraken_live_trading_enabled)
        algo_enabled = bool(cfg.kraken_live_algo_enabled)
        autonomy = int(cfg.autonomy)
        blocked: str | None = None
        if not live_enabled:
            blocked = "KRAKEN_LIVE_TRADING_ENABLED=false"
        elif autonomy < int(AutonomyLevel.AUTONOMOUS):
            blocked = f"autonomy_level={autonomy} (need >= 4)"
        elif not algo_enabled:
            blocked = "KRAKEN_LIVE_ALGO_ENABLED=false (supervised manual first)"
        deadman = bool(getattr(self._session, "_deadman_armed", False)) if self._session else False
        paper_engine = None
        try:
            from backend.app.signals.engine.generator import get_fable_engine

            eng = get_fable_engine()
            paper_engine = eng.status() if eng is not None else None
        except Exception:  # noqa: BLE001
            paper_engine = None
        session_snap = live_session_ledger.active
        return {
            "paper": {
                "running": self._paper_running,
                "mode": "paper",
                "last_error": self._paper_last_error,
                "engine": paper_engine,
            },
            "live": {
                "running": self._live_running,
                "blocked_reason": blocked if not self._live_running else None,
                "can_start": blocked is None,
                "deadman_armed": deadman,
                "autonomy": autonomy,
                "live_enabled": live_enabled,
                "algo_enabled": algo_enabled,
                "supervised_manual": live_enabled and autonomy >= 3,
                "last_error": self._live_last_error,
                "session": session_snap,
            },
        }

    async def start_paper(self, settings: Settings, session_factory: Any) -> dict[str, Any]:
        if self._paper_running:
            return {"started": False, "reason": "ALREADY_RUNNING"}
        from backend.app.signals.engine.config import EngineSettings
        from backend.app.signals.engine.generator import (
            FableEngine,
            default_strategies,
            engine_settings_from_app,
            get_fable_engine,
            set_fable_engine,
        )
        from backend.app.signals.safety import SignalSafetyError

        existing = get_fable_engine()
        if existing is not None and existing.status().get("started"):
            self._paper_running = True
            return {"started": False, "reason": "ALREADY_RUNNING", "engine": existing.status()}

        base = engine_settings_from_app(settings)
        # UI paper loop is always dry-run: record intents only, never place orders.
        # This may coexist with live env flags used by the Positions desk.
        eng_settings = EngineSettings(
            enabled=True,
            dry_run=True,
            poll_seconds=base.poll_seconds,
            market_rpm=base.market_rpm,
            onnx_bias=base.onnx_bias,
            strategies=base.strategies or default_strategies(settings),
        )
        engine = FableEngine(settings=settings, engine=eng_settings, session_factory=session_factory)
        try:
            engine.assert_start_safe()
        except SignalSafetyError as exc:
            self._paper_last_error = str(exc)
            return {"started": False, "reason": "SAFETY", "message": str(exc)}

        if settings.signal_routes_enabled:
            try:
                from backend.app.signals.bootstrap import ensure_fable_routes

                await ensure_fable_routes(session_factory, settings)
            except Exception as exc:  # noqa: BLE001
                logger.warning("fable route bootstrap on paper start: %s", exc)

        set_fable_engine(engine)

        async def _run() -> None:
            self._paper_last_error = None
            try:
                await engine.run_forever(force=True)
            except Exception as exc:  # noqa: BLE001
                self._paper_last_error = str(exc)
                logger.exception("paper loop failed: %s", exc)
            finally:
                self._paper_running = False
                self._paper_task = None

        self._paper_running = True
        self._paper_last_error = None
        self._paper_task = asyncio.create_task(_run(), name="trading-paper-loop")
        return {"started": True, "mode": "paper", "engine": engine.status()}

    async def stop_paper(self) -> dict[str, Any]:
        from backend.app.signals.engine.generator import get_fable_engine, set_fable_engine

        eng = get_fable_engine()
        if eng is not None:
            eng.stop()
        task = self._paper_task
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._paper_task = None
        self._paper_running = False
        set_fable_engine(None)
        return {"stopped": True, "mode": "paper"}

    async def start_live(
        self,
        settings: Settings,
        session: Level4Session,
        *,
        max_margin_eur: float,
        max_concurrent_trades: int,
        symbols: list[str] | None = None,
        starting_capital_eur: float | None = None,
        position_sizing_mode: str = "half_kelly",
        manual_notional_eur: float | None = None,
        max_session_size: Any = None,
        daily_loss_limit: Any = None,
        min_confidence_pct: float = 0.0,
        allow_pre_post_market: bool = True,
        human_verification: bool = False,
    ) -> dict[str, Any]:
        self.bind_session(session)
        snap = self.status(settings)
        if not snap["live"]["can_start"]:
            reason = snap["live"]["blocked_reason"] or "BLOCKED"
            self._live_blocked_reason = reason
            return {
                "started": False,
                "reason": "GATES",
                "blocked_reason": reason,
                "hint": (
                    "Need KRAKEN_LIVE_TRADING_ENABLED=true, KRAKEN_AUTONOMY_LEVEL=4, "
                    "and KRAKEN_LIVE_ALGO_ENABLED=true for unattended algo. "
                    "Manual Positions desk works without LIVE_ALGO (supervised)."
                ),
            }
        if self._live_running:
            return {"started": False, "reason": "ALREADY_RUNNING"}

        try:
            capital = float(starting_capital_eur) if starting_capital_eur is not None else float(max_margin_eur)
            if capital <= 0:
                raise ValueError("starting_capital_eur must be > 0")
            size_raw = max_session_size if max_session_size is not None else max_margin_eur
            loss_raw = daily_loss_limit if daily_loss_limit is not None else {"value": 5.0, "unit": "pct"}
            risk = validate_session_risk_policy(
                max_session_size=size_raw,
                max_concurrent_trades=max_concurrent_trades,
                daily_loss_limit=loss_raw,
                min_confidence_pct=min_confidence_pct,
                allow_pre_post_market=allow_pre_post_market,
                human_verification=human_verification,
                starting_capital_eur=capital,
            )
            margin = risk.max_session_size_eur()
            concurrent = risk.max_concurrent_trades
            symbol_list = parse_symbol_list(symbols)
            sizing = validate_sizing_policy(
                mode=position_sizing_mode,
                manual_notional_eur=manual_notional_eur,
            )
            if sizing.mode == "manual" and sizing.manual_notional_eur is not None:
                if sizing.manual_notional_eur > margin:
                    raise ValueError(
                        f"manual_notional_eur {sizing.manual_notional_eur} exceeds max_session_size {margin}"
                    )
            if risk.human_verification and not (
                settings.telegram_enabled and settings.telegram_bot_token and settings.telegram_chat_id
            ):
                raise ValueError(
                    "human_verification requires TELEGRAM_ENABLED + TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID"
                )
            tightened = session.apply_session_limits(
                max_margin_eur=margin,
                max_concurrent_trades=concurrent,
                symbols=symbol_list or None,
            )
            session.set_sizing_policy(sizing, capital_eur=capital, max_margin_eur=margin)
            session.set_risk_policy(risk)
        except ValueError as exc:
            return {"started": False, "reason": "SESSION_LIMITS", "message": str(exc)}

        preflight = await session.preflight()
        if not preflight.ok:
            return {
                "started": False,
                "reason": "PREFLIGHT_FAILED",
                "checks": preflight.checks,
            }
        try:
            await session.arm_deadman()
        except PermissionError as exc:
            return {"started": False, "reason": "AUTONOMY_GATE", "message": str(exc)}
        except Exception as exc:  # noqa: BLE001
            self._live_last_error = str(exc)
            return {"started": False, "reason": "DEADMAN_FAILED", "message": str(exc)}

        try:
            session_rec = live_session_ledger.start(
                max_margin_eur=margin,
                max_concurrent_trades=concurrent,
                symbols=symbol_list or None,
                starting_capital_eur=capital,
                position_sizing=sizing.to_dict(),
                risk_policy=risk.to_dict(),
                autonomy=int(settings.autonomy),
                deadman_seconds=int(settings.kraken_deadman_seconds),
            )
        except (ValueError, RuntimeError) as exc:
            return {"started": False, "reason": "SESSION_LIMITS", "message": str(exc)}

        async def _live_run() -> None:
            import time

            from backend.app.trading.live_heartbeat import send_live_heartbeat
            from backend.app.trading.session import _count_open

            self._live_last_error = None
            refresh = max(30.0, float(settings.kraken_deadman_seconds) / 3.0)
            heartbeat_every = float(
                getattr(settings, "live_session_telegram_heartbeat_seconds", 3600) or 3600
            )
            last_heartbeat = 0.0
            # Immediate start ping, then hourly while session stays active.
            await send_live_heartbeat(settings, kind="started", open_trades=0)
            last_heartbeat = time.monotonic()
            try:
                while self._live_running:
                    open_count = 0
                    try:
                        await session.refresh_deadman()
                    except Exception as exc:  # noqa: BLE001
                        self._live_last_error = str(exc)
                        logger.warning("live deadman refresh failed: %s", exc)
                    try:
                        orders = await session.cli.open_orders()
                        open_count = _count_open(orders if isinstance(orders, dict) else {})
                    except Exception:  # noqa: BLE001
                        open_count = int((live_session_ledger.active or {}).get("last_open_trades") or 0)
                    live_session_ledger.sample(open_trades=open_count)
                    now_m = time.monotonic()
                    if now_m - last_heartbeat >= heartbeat_every:
                        await send_live_heartbeat(
                            settings, kind="heartbeat", open_trades=open_count
                        )
                        last_heartbeat = now_m
                    await asyncio.sleep(refresh)
            finally:
                self._live_running = False
                self._live_task = None

        self._live_running = True
        self._live_task = asyncio.create_task(_live_run(), name="trading-live-loop")
        return {
            "started": True,
            "mode": "live",
            "deadman_armed": True,
            "deadman_seconds": settings.kraken_deadman_seconds,
            "session": session_rec,
            "position_sizing": sizing.to_dict(),
            "risk_policy": risk.to_dict(),
            "telegram_heartbeat_seconds": int(
                getattr(settings, "live_session_telegram_heartbeat_seconds", 3600) or 3600
            ),
            "guardrails": {
                "max_notional": str(tightened.max_notional),
                "max_open_positions": tightened.max_open_positions,
                "pair_allowlist": sorted(tightened.pair_allowlist),
            },
        }

    async def stop_live(self) -> dict[str, Any]:
        self._live_running = False
        task = self._live_task
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._live_task = None
        open_count = 0
        if self._session is not None:
            try:
                from backend.app.trading.session import _count_open

                orders = await self._session.cli.open_orders()
                open_count = _count_open(orders if isinstance(orders, dict) else {})
            except Exception:  # noqa: BLE001
                open_count = int((live_session_ledger.active or {}).get("last_open_trades") or 0)
        finished = live_session_ledger.stop(open_trades=open_count, status="stopped")
        if finished is not None:
            from backend.app.trading.live_heartbeat import send_live_heartbeat
            from backend.app.settings import get_settings

            await send_live_heartbeat(
                get_settings(),
                kind="stopped",
                open_trades=open_count,
                session_snapshot=finished,
            )
        return {"stopped": True, "mode": "live", "session": finished}

    async def kill_switch(self, session: Level4Session | None = None) -> dict[str, Any]:
        """Emergency stop: halt loops and cancel-all open live orders when possible."""
        from backend.app.trading.live_audit import log_live_event

        paper = await self.stop_paper()
        live = await self.stop_live()
        if live_session_ledger.active is not None:
            live_session_ledger.stop(status="killed")
        cancel_result: dict[str, Any] | None = None
        cancel_error: str | None = None
        cli = session.cli if session is not None else (self._session.cli if self._session else None)
        if cli is not None and getattr(cli, "allow_trade_commands", False):
            try:
                cancel_result = await cli.cancel_all()
            except Exception as exc:  # noqa: BLE001
                cancel_error = str(exc)
        log_live_event(
            "kill_switch",
            paper_stopped=paper.get("stopped"),
            live_stopped=live.get("stopped"),
            cancel_all=cancel_result is not None,
            cancel_error=cancel_error,
        )
        return {
            "killed": True,
            "paper": paper,
            "live": live,
            "cancel_all": cancel_result,
            "cancel_error": cancel_error,
        }

    async def shutdown(self) -> None:
        await self.stop_paper()
        await self.stop_live()


trading_loops = TradingLoopsService()
