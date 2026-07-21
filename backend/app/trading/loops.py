"""Runtime paper / live trading loop controller (UI switches).

Live start never flips KRAKEN_LIVE_TRADING_ENABLED — it only arms a session
when env gates already allow Level 4.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from backend.app.settings import Settings, get_settings
from backend.app.trading.autonomy import AutonomyLevel
from backend.app.trading.session import Level4Session

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

    async def start_live(self, settings: Settings, session: Level4Session) -> dict[str, Any]:
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

        async def _live_run() -> None:
            self._live_last_error = None
            refresh = max(30.0, float(settings.kraken_deadman_seconds) / 3.0)
            try:
                while self._live_running:
                    try:
                        await session.refresh_deadman()
                    except Exception as exc:  # noqa: BLE001
                        self._live_last_error = str(exc)
                        logger.warning("live deadman refresh failed: %s", exc)
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
        return {"stopped": True, "mode": "live"}

    async def kill_switch(self, session: Level4Session | None = None) -> dict[str, Any]:
        """Emergency stop: halt loops and cancel-all open live orders when possible."""
        from backend.app.trading.live_audit import log_live_event

        paper = await self.stop_paper()
        live = await self.stop_live()
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
