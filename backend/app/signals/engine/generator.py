"""FableEngine poll loop — dry-run first, paper-only, market rate-limited."""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any

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
            reference_price=None,
            drawdown_steps_pct=[2.0, 4.0, 8.0],
        ),
    ]


class FableEngine:
    """Async poll loop analogous to SignalWorker.run_forever (no intake in P2)."""

    def __init__(
        self,
        *,
        settings: Settings,
        engine: EngineSettings | None = None,
        candle_fetcher: CandleFetcher | None = None,
        max_dry_runs: int = 200,
    ) -> None:
        self.app_settings = settings
        self.engine = engine or engine_settings_from_app(settings)
        self._candle_fetcher = candle_fetcher
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

    async def run_forever(self) -> None:
        if not self.engine.enabled:
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
            for strat in strats:
                state = self._states[strat.config.strategy_id]
                intents = strat.evaluate(candles, state)
                for intent in intents:
                    self._record_intent(intent)
                all_intents.extend(intents)

        self.ticks += 1
        self.last_tick_at = datetime.now(UTC).isoformat()
        return all_intents

    async def _fetch_candles(self, pair: str) -> list[dict[str, Any]]:
        if self._candle_fetcher is not None:
            return await self._candle_fetcher(pair)
        # Prefer CCXT public OHLCV; never Alpha Vantage in the poll loop.
        from backend.app.integrations.ccxt_market import CcxtMarketClient

        client = CcxtMarketClient(exchange_id=self.app_settings.market_ccxt_exchange)
        try:
            raw = await client.fetch_ohlcv(pair, timeframe="1h", limit=120)
            candles: list[dict[str, Any]] = []
            for row in raw or []:
                # CCXT: [ts, o, h, l, c, v]
                if not isinstance(row, (list, tuple)) or len(row) < 5:
                    continue
                candles.append(
                    {
                        "timestamp": row[0],
                        "open": float(row[1]),
                        "high": float(row[2]),
                        "low": float(row[3]),
                        "close": float(row[4]),
                        "volume": float(row[5]) if len(row) > 5 else 0.0,
                    }
                )
            return candles
        finally:
            await client.close()

    def _record_intent(self, intent: SignalIntent) -> None:
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


# Process-singleton for lifespan / status (P4 will expose read-only HTTP).
_engine: FableEngine | None = None


def get_fable_engine() -> FableEngine | None:
    return _engine


def set_fable_engine(engine: FableEngine | None) -> None:
    global _engine
    _engine = engine


def intent_as_dict(intent: SignalIntent) -> dict[str, Any]:
    data = asdict(intent)
    data["volume"] = format(intent.volume, "f")
    return data
