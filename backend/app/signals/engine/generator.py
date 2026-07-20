"""FableEngine poll loop — dry-run first, paper-only, market rate-limited."""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable
from dataclasses import asdict
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.app.settings import Settings
from backend.app.signals.engine.config import EngineSettings, StrategyConfig
from backend.app.signals.engine.ratelimit import TokenBucket
from backend.app.signals.engine.strategies import SignalIntent, StrategyState, build_strategy
from backend.app.signals.safety import SignalSafetyError, assert_signal_paper_only

logger = logging.getLogger("neo_fabel.signals.engine")

CandleFetcher = Callable[[str], Awaitable[list[dict[str, Any]]]]


def engine_settings_from_app(settings: Settings, strategies: list[StrategyConfig] | None = None) -> EngineSettings:
    return EngineSettings(
        enabled=settings.fable_engine_enabled,
        dry_run=settings.fable_engine_dry_run,
        poll_seconds=settings.fable_engine_poll_seconds,
        market_rpm=settings.fable_engine_market_rpm,
        onnx_bias=settings.fable_engine_onnx_bias,  # type: ignore[arg-type]
        strategies=strategies or default_strategies(settings),
    )


def default_strategies(settings: Settings) -> list[StrategyConfig]:
    """Minimal default pair of strategies when none injected (paper research)."""
    pairs = [p.strip() for p in settings.kraken_pair_allowlist.split(",") if p.strip()]
    pair = pairs[0] if pairs else "BTCUSD"
    return [
        StrategyConfig(
            strategy_id="fable_grid_default",
            kind="grid",
            pair=pair,
            range_low=1.0,
            range_high=3.0,
            grid_count=4,
        ),
        StrategyConfig(
            strategy_id="fable_dca_default",
            kind="dca",
            pair=pair,
            # Placeholder until UI/env strategy config: high ref forces drawdown
            # steps to fire on first live tick (BTC/ETH << 1e6) for P3–P4 smoke.
            reference_price=1_000_000.0,
            drawdown_steps_pct=[2.0, 4.0, 8.0],
        ),
    ]


class FableEngine:
    """Async poll loop analogous to SignalWorker.run_forever.

    P3: intents are persisted through the normal signals intake when a
    session_factory is provided; the worker terminates them as
    `dry_run_recorded` while FABLE_ENGINE_DRY_RUN=true.
    """

    def __init__(
        self,
        *,
        settings: Settings,
        engine: EngineSettings | None = None,
        candle_fetcher: CandleFetcher | None = None,
        session_factory: async_sessionmaker[AsyncSession] | None = None,
        max_dry_runs: int = 200,
    ) -> None:
        self.app_settings = settings
        self.engine = engine or engine_settings_from_app(settings)
        self._candle_fetcher = candle_fetcher
        self._session_factory = session_factory
        self._stop = asyncio.Event()
        self._bucket = TokenBucket(self.engine.market_rpm)
        self._states: dict[str, StrategyState] = defaultdict(StrategyState)
        self._strategies = [build_strategy(c) for c in self.engine.strategies if c.enabled]
        self.dry_runs: deque[dict[str, Any]] = deque(maxlen=max_dry_runs)
        self.last_tick_at: str | None = None
        self.last_error: str | None = None
        self.ticks: int = 0
        self._started = False

    def assert_start_safe(self) -> None:
        """Fail-closed gates before the loop starts."""
        assert_signal_paper_only(self.app_settings)
        if not self.engine.dry_run and not self.app_settings.signal_execution_enabled:
            raise SignalSafetyError(
                "FableEngine refuses start: FABLE_ENGINE_DRY_RUN=false requires SIGNAL_EXECUTION_ENABLED=true"
            )

    def stop(self) -> None:
        self._stop.set()

    def status(self) -> dict[str, Any]:
        return {
            "enabled": self.engine.enabled,
            "dry_run": self.engine.dry_run,
            "started": self._started,
            "poll_seconds": self.engine.poll_seconds,
            "market_rpm": self.engine.market_rpm,
            "onnx_bias": self.engine.onnx_bias,
            "strategy_count": len(self._strategies),
            "ticks": self.ticks,
            "last_tick_at": self.last_tick_at,
            "last_error": self.last_error,
            "dry_run_count": len(self.dry_runs),
        }

    def recent_dry_runs(self, limit: int = 50) -> list[dict[str, Any]]:
        items = list(self.dry_runs)
        return items[-limit:]

    async def run_forever(self, *, force: bool = False) -> None:
        if not self.engine.enabled and not force:
            logger.info("FableEngine not started (FABLE_ENGINE_ENABLED=false)")
            return
        self.assert_start_safe()
        self._started = True
        logger.info(
            "FableEngine started dry_run=%s strategies=%s",
            self.engine.dry_run,
            len(self._strategies),
        )
        while not self._stop.is_set():
            try:
                await self.poll_once()
            except Exception as exc:  # noqa: BLE001 — loop must survive tick errors
                self.last_error = str(exc)
                logger.exception("FableEngine tick failed: %s", exc)
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self.engine.poll_seconds)
            except asyncio.TimeoutError:
                pass
        self._started = False

    async def poll_once(self) -> list[SignalIntent]:
        if not self._bucket.allow(1.0):
            logger.debug("FableEngine market rate-limit skip")
            return []

        by_pair: dict[str, list[Any]] = defaultdict(list)
        for strat in self._strategies:
            by_pair[strat.config.pair.upper()].append(strat)

        all_intents: list[SignalIntent] = []
        for pair, strats in by_pair.items():
            candles = await self._fetch_candles(pair)
            last_ts = int(candles[-1].get("timestamp") or 0) if candles else 0
            for strat in strats:
                state = self._states[strat.config.strategy_id]
                intents = strat.evaluate(candles, state)
                for intent in intents:
                    record = self._record_intent(intent)
                    await self._submit_intake(intent, last_ts, record)
                all_intents.extend(intents)

        self.ticks += 1
        self.last_tick_at = datetime.now(UTC).isoformat()
        return all_intents

    async def _fetch_candles(self, pair: str) -> list[dict[str, Any]]:
        if self._candle_fetcher is not None:
            return await self._candle_fetcher(pair)
        # tvremix get_ohlcv primary, CCXT fallback; never Alpha Vantage in the poll loop.
        from backend.app.signals.engine.market_source import fetch_candles

        return await fetch_candles(pair, settings=self.app_settings, count=120)

    async def _submit_intake(self, intent: SignalIntent, candle_ts: int, record: dict[str, Any]) -> None:
        """Persist the intent through the normal signals intake (route limits apply).

        Dry-run character is decided by the worker (terminal `dry_run_recorded`);
        intake failures only annotate the in-memory record — the tick survives.
        """
        if self._session_factory is None:
            record["intake"] = "memory_only"
            return
        from fastapi import HTTPException

        from backend.app.signals.service import SignalSubmissionService

        occurred_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        observed = Decimal(str(intent.price)) if intent.price is not None else None
        service = SignalSubmissionService(self.app_settings)
        try:
            async with self._session_factory() as session:
                receipt = await service.submit_fable_engine(
                    session,
                    strategy_id=intent.strategy_id,
                    signal_id=intent_signal_id(intent, candle_ts),
                    occurred_at=occurred_at,
                    # Same normalization as the webhook path — route allowlists compare normalized.
                    pair=intent.pair.strip().upper().replace("/", "").replace("-", ""),
                    side=intent.side,
                    volume=intent.volume,
                    observed_price=observed,
                    request_id=str(uuid4()),
                )
            record["intake"] = "replayed" if receipt.replayed else f"accepted:{receipt.submission_id}"
        except HTTPException as exc:
            detail = exc.detail if isinstance(exc.detail, dict) else {"code": str(exc.detail)}
            record["intake"] = f"rejected:{detail.get('code', exc.status_code)}"
        except Exception as exc:  # noqa: BLE001 — intake failure must not kill the tick
            record["intake"] = f"error:{exc}"
            logger.warning("fable intake failed: %s", exc)

    def _record_intent(self, intent: SignalIntent) -> dict[str, Any]:
        record = {
            "recorded_at": datetime.now(UTC).isoformat(),
            "terminal": "dry_run_recorded" if self.engine.dry_run else "intent_pending_intake",
            "strategy_id": intent.strategy_id,
            "kind": intent.kind,
            "pair": intent.pair,
            "side": intent.side,
            "volume": format(intent.volume, "f"),
            "reason": intent.reason,
            "zone": intent.zone,
            "price": intent.price,
            "meta": intent.meta,
        }
        self.dry_runs.append(record)
        logger.info(
            "FableEngine %s %s %s %s zone=%s",
            record["terminal"],
            intent.kind,
            intent.side,
            intent.pair,
            intent.zone,
        )
        return record


# Process-singleton for lifespan / status (P4 will expose read-only HTTP).
_engine: FableEngine | None = None


def get_fable_engine() -> FableEngine | None:
    return _engine


def set_fable_engine(engine: FableEngine | None) -> None:
    global _engine
    _engine = engine


def intent_signal_id(intent: SignalIntent, candle_ts: int) -> str:
    """Deterministic dedupe id — same zone/step on the same candle never double-submits,
    even across engine restarts (DB unique on route/source/signal_id)."""
    return f"{intent.strategy_id}:{intent.reason}:{int(candle_ts)}"[:128]


def intent_as_dict(intent: SignalIntent) -> dict[str, Any]:
    data = asdict(intent)
    data["volume"] = format(intent.volume, "f")
    return data
