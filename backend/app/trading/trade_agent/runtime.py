"""Async scheduler + background runtime for Neo Trade Agent."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

from backend.app.settings import Settings, get_settings
from backend.app.trading.trade_agent import jobs
from backend.app.trading.trade_agent.schedules import DEFAULT_SLOTS, POSITIONS_WATCHDOG_SECONDS

logger = logging.getLogger("neo_fabel.trade_agent.runtime")


class TradeAgentRuntime:
    """Hybrid scheduler: wall-clock slots + optional positions watchdog.

    Paper-first. Does not place live orders — market scans drive FableEngine dry-run.
    """

    def __init__(self) -> None:
        self._task: asyncio.Task[None] | None = None
        self._watchdog_task: asyncio.Task[None] | None = None
        self._running = False
        self._last_fired: dict[str, str] = {}
        self._last_results: list[dict[str, Any]] = []
        self._last_error: str | None = None

    @property
    def running(self) -> bool:
        return self._running

    def status(self) -> dict[str, Any]:
        return {
            "running": self._running,
            "last_fired": dict(self._last_fired),
            "last_error": self._last_error,
            "recent_results": list(self._last_results[-12:]),
            "slots": [
                {
                    "job_id": s.job_id,
                    "hour": s.hour,
                    "minute": s.minute,
                    "tz": s.tz_name,
                    "description": s.description,
                }
                for s in DEFAULT_SLOTS
            ],
            "positions_watchdog_seconds": POSITIONS_WATCHDOG_SECONDS,
        }

    async def start(self, settings: Settings | None = None) -> dict[str, Any]:
        cfg = settings or get_settings()
        if not cfg.trade_agent_enabled:
            return {"started": False, "reason": "TRADE_AGENT_ENABLED=false"}
        if self._running:
            return {"started": False, "reason": "ALREADY_RUNNING"}
        self._running = True
        self._last_error = None
        self._task = asyncio.create_task(self._scheduler_loop(cfg), name="trade-agent-scheduler")
        if cfg.trade_agent_watchdog_enabled:
            self._watchdog_task = asyncio.create_task(
                self._watchdog_loop(cfg), name="trade-agent-watchdog"
            )
        logger.info("trade agent runtime started")
        return {"started": True, "status": self.status()}

    async def stop(self) -> dict[str, Any]:
        self._running = False
        for task in (self._task, self._watchdog_task):
            if task is not None and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        self._task = None
        self._watchdog_task = None
        logger.info("trade agent runtime stopped")
        return {"stopped": True}

    async def trigger(self, job_id: str, *, reason: str = "manual") -> dict[str, Any]:
        result = await self._dispatch(job_id, reason=reason)
        self._remember(job_id, result)
        return result

    def _remember(self, job_id: str, result: dict[str, Any]) -> None:
        self._last_fired[job_id] = datetime.now(UTC).isoformat()
        self._last_results.append({"job_id": job_id, **result})
        self._last_results = self._last_results[-40:]
        if not result.get("ok", True):
            self._last_error = str(result.get("error") or result)

    async def _dispatch(self, job_id: str, *, reason: str) -> dict[str, Any]:
        try:
            if job_id.startswith("market_scan") or job_id.startswith("et_"):
                return await jobs.run_market_scan(reason=f"{reason}:{job_id}")
            if job_id == "label_trades":
                return await jobs.run_label_trades()
            if job_id == "feedback_idle":
                from backend.app.trading.feedback import feedback_engine

                return await feedback_engine.run_cycle(reason=f"{reason}:feedback_idle")
            if job_id == "optimizer_night":
                return await jobs.run_optimizer()
            if job_id == "check_status":
                return await jobs.check_status_snapshot()
            if job_id == "check_positions":
                return await jobs.check_positions_snapshot()
            return {"ok": False, "error": f"unknown_job:{job_id}"}
        except Exception as exc:  # noqa: BLE001
            logger.exception("trade agent job %s failed", job_id)
            return {"ok": False, "job": job_id, "error": str(exc)}

    async def _scheduler_loop(self, settings: Settings) -> None:
        """Poll every 20s; fire each slot once per local calendar day."""
        fired_today: set[str] = set()
        last_day: str | None = None
        try:
            while self._running:
                now_utc = datetime.now(UTC)
                day_key = now_utc.date().isoformat()
                if day_key != last_day:
                    fired_today.clear()
                    last_day = day_key

                for slot in DEFAULT_SLOTS:
                    key = f"{day_key}:{slot.job_id}"
                    if key in fired_today:
                        continue
                    local = now_utc.astimezone(slot.tz)
                    if local.hour == slot.hour and local.minute == slot.minute:
                        fired_today.add(key)
                        result = await self._dispatch(slot.job_id, reason="schedule")
                        self._remember(slot.job_id, result)
                        logger.info("scheduled %s → %s", slot.job_id, result.get("ok"))

                await asyncio.sleep(20)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            self._last_error = str(exc)
            logger.exception("trade agent scheduler crashed")
        finally:
            self._running = False

    async def _watchdog_loop(self, settings: Settings) -> None:
        interval = max(60, int(settings.trade_agent_watchdog_seconds or POSITIONS_WATCHDOG_SECONDS))
        try:
            while self._running:
                result = await jobs.check_positions_snapshot()
                self._remember("check_positions", result)
                await asyncio.sleep(interval)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            self._last_error = str(exc)
            logger.exception("trade agent watchdog crashed")


trade_agent = TradeAgentRuntime()
