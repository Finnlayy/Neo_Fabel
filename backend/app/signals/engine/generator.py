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
from backend.app.signals.engine.onnx_bias import apply_onnx_bias
from backend.app.signals.engine.ratelimit import TokenBucket
from backend.app.signals.engine.strategies import SignalIntent, StrategyState, build_strategy
from backend.app.signals.safety import SignalSafetyError

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


def paper_opportunity_pairs(settings: Settings) -> list[str]:
    """Universe the paper engine may scan for setups.

    This is the opportunity *watchlist*, not a fill target. Concurrent opens are
    capped separately by ``paper_max_open_positions`` (default 20) when buys fire.
    """
    raw = getattr(settings, "paper_opportunity_symbols", None) or ""
    if not str(raw).strip():
        raw = getattr(settings, "market_stream_symbols", "") or ""
    pairs: list[str] = []
    seen: set[str] = set()
    for part in str(raw).split(","):
        norm = part.strip().upper().replace("/", "").replace("-", "")
        if not norm or norm in seen:
            continue
        seen.add(norm)
        pairs.append(norm)
    if not pairs:
        # Fall back to live allowlist crumbs, then product spot pairs.
        for part in (settings.kraken_pair_allowlist or "").split(","):
            norm = part.strip().upper().replace("/", "").replace("-", "")
            if norm and norm not in seen:
                seen.add(norm)
                pairs.append(norm)
    if not pairs:
        pairs = ["ADAUSD", "XRPUSD"]
    return pairs


def default_strategies(settings: Settings) -> list[StrategyConfig]:
    """One adaptive grid per watchlist pair; fills stop at paper_max_open_positions."""
    pairs = paper_opportunity_pairs(settings)
    strategies: list[StrategyConfig] = []
    for pair in pairs:
        strategies.append(
            StrategyConfig(
                strategy_id=f"fable_grid_{pair.lower()}",
                kind="grid",
                pair=pair,
                adaptive_range=True,
                grid_count=4,
                volume_per_zone=Decimal("0.001"),
            )
        )
    return strategies


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
        from backend.app.signals.safety import assert_fable_engine_start_safe

        assert_fable_engine_start_safe(self.app_settings, dry_run=bool(self.engine.dry_run))
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
                # Idle / paper feedback every ~30 ticks when enabled.
                if (
                    self.app_settings.feedback_engine_enabled
                    and self.ticks > 0
                    and self.ticks % 30 == 0
                ):
                    try:
                        from backend.app.trading.feedback import feedback_engine

                        await feedback_engine.run_cycle(reason=f"engine_tick_{self.ticks}")
                    except Exception as fb_exc:  # noqa: BLE001
                        logger.debug("feedback cycle skipped: %s", fb_exc)
            except Exception as exc:  # noqa: BLE001 — loop must survive tick errors
                self.last_error = str(exc)
                logger.exception("FableEngine tick failed: %s", exc)
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self.engine.poll_seconds)
            except asyncio.TimeoutError:
                pass
        self._started = False

    async def poll_once(self, *, candle_source: str | None = None) -> list[SignalIntent]:
        if not self._bucket.allow(1.0):
            logger.debug("FableEngine market rate-limit skip")
            return []

        by_pair: dict[str, list[Any]] = defaultdict(list)
        for strat in self._strategies:
            by_pair[strat.config.pair.upper()].append(strat)

        all_intents: list[SignalIntent] = []
        for pair, strats in by_pair.items():
            candles = await self._fetch_candles(pair, source_override=candle_source)
            last_ts = int(candles[-1].get("timestamp") or 0) if candles else 0
            onnx_ctx = self._fetch_onnx_context(pair, candles)
            for strat in strats:
                state = self._states[strat.config.strategy_id]
                intents = apply_onnx_bias(
                    strat.evaluate(candles, state),
                    mode=self.engine.onnx_bias,  # type: ignore[arg-type]
                    onnx=onnx_ctx,
                )
                for intent in intents:
                    if not self._allows_new_paper_opportunity(intent):
                        self._rollback_intent_state(intent, state)
                        record = self._record_intent(intent)
                        record["intake"] = "skipped:max_open_positions"
                        record["terminal"] = "capacity_skipped"
                        continue
                    record = self._record_intent(intent)
                    await self._submit_intake(intent, last_ts, record)
                all_intents.extend(intents)

        self.ticks += 1
        self.last_tick_at = datetime.now(UTC).isoformat()
        return all_intents

    def _rollback_intent_state(self, intent: SignalIntent, state: StrategyState) -> None:
        """Undo evaluate() side effects when a buy is dropped for capacity."""
        if intent.side != "buy":
            return
        if intent.kind == "grid" and intent.zone is not None:
            state.grid_inventory[intent.zone] = 0
        elif intent.kind == "dca" and intent.zone is not None:
            state.dca_steps_filled.discard(intent.zone)
            vol = intent.volume
            if state.dca_units > 0 and intent.price is not None:
                prev_units = state.dca_units - vol
                if prev_units <= 0:
                    state.dca_units = Decimal("0")
                    state.dca_entry_avg = None
                else:
                    avg = Decimal(str(state.dca_entry_avg or intent.price))
                    state.dca_entry_avg = float(
                        (avg * state.dca_units - Decimal(str(intent.price)) * vol) / prev_units
                    )
                    state.dca_units = prev_units

    def _allows_new_paper_opportunity(self, intent: SignalIntent) -> bool:
        """Respect paper_max_open_positions — only block *new* buys when at capacity."""
        if intent.side != "buy":
            return True
        try:
            from backend.app.integrations.local_paper import get_local_paper_ledger

            ledger = get_local_paper_ledger()
            max_open = int(
                getattr(self.app_settings, "paper_max_open_positions", None)
                or getattr(ledger, "max_open_positions", 20)
                or 20
            )
            open_n = int(ledger.open_position_count())
            pair = intent.pair.strip().upper().replace("/", "").replace("-", "")
            lots = (ledger._spot.get("lots") or {}).get(pair) or []
            if lots:
                return True  # scale-in on existing opportunity
            return open_n < max_open
        except Exception:  # noqa: BLE001
            return True

    async def _fetch_candles(
        self, pair: str, *, source_override: str | None = None
    ) -> list[dict[str, Any]]:
        if self._candle_fetcher is not None:
            return await self._candle_fetcher(pair)
        # tvremix get_ohlcv primary, CCXT fallback; never Alpha Vantage in the poll loop.
        from backend.app.signals.engine.market_source import fetch_candles

        return await fetch_candles(
            pair,
            settings=self.app_settings,
            count=120,
            source_override=source_override,
        )

    def _fetch_onnx_context(self, pair: str, candles: list[dict[str, Any]]) -> dict[str, Any] | None:
        """Sidecar ONNX inference for FABLE_ENGINE_ONNX_BIAS (off skips call)."""
        if self.engine.onnx_bias == "off":
            return None
        if len(candles) < 10:
            return None
        try:
            from backend.app.integrations.onnx.predictor import predict

            return predict(symbol=pair, bars=candles, source="fable_engine", allow_fallback=True)
        except Exception as exc:  # noqa: BLE001
            logger.debug("ONNX sidecar skipped for %s: %s", pair, exc)
            return None

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
                    rationale=str(record.get("rationale") or intent.reason),
                )
            record["intake"] = "replayed" if receipt.replayed else f"accepted:{receipt.submission_id}"
        except HTTPException as exc:
            detail = exc.detail if isinstance(exc.detail, dict) else {"code": str(exc.detail)}
            record["intake"] = f"rejected:{detail.get('code', exc.status_code)}"
        except Exception as exc:  # noqa: BLE001 — intake failure must not kill the tick
            record["intake"] = f"error:{exc}"
            logger.warning("fable intake failed: %s", exc)

    def _record_intent(self, intent: SignalIntent) -> dict[str, Any]:
        from backend.app.trading.feedback.rationale import format_trade_rationale

        rationale = format_trade_rationale(intent)
        record = {
            "recorded_at": datetime.now(UTC).isoformat(),
            "terminal": "dry_run_recorded" if self.engine.dry_run else "intent_pending_intake",
            "strategy_id": intent.strategy_id,
            "kind": intent.kind,
            "pair": intent.pair,
            "side": intent.side,
            "volume": format(intent.volume, "f"),
            "reason": intent.reason,
            "rationale": rationale,
            "zone": intent.zone,
            "price": intent.price,
            "meta": intent.meta,
        }
        self.dry_runs.append(record)
        logger.info(
            "FableEngine %s %s | %s",
            record["terminal"],
            intent.kind,
            rationale,
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
