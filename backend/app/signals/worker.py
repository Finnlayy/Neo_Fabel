"""PostgreSQL lease loop for durable signal processing."""

from __future__ import annotations

import asyncio
import logging
from decimal import Decimal
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..integrations.kraken_cli import KrakenCliError
from ..models import SignalEvaluation
from ..settings import Settings
from .domain import assert_transition
from .evaluator import FakeSignalEvaluator, SignalEvaluator, normalize_evaluation
from .executor import PaperExecutionPort
from .policy import build_candidate, check_route_policy, effective_mode
from .repository import SignalRepository, new_audit
from .safety import assert_signal_paper_only

logger = logging.getLogger("neo_fabel.signals.worker")


def _pattern_bias_from_event(metadata_json: dict | None) -> str | None:
    if not metadata_json:
        return None
    pb = metadata_json.get("pattern_bias")
    if pb in {"bullish", "bearish", "neutral"}:
        return pb
    return None


def _pattern_confidence_from_event(metadata_json: dict | None) -> Decimal | None:
    if not metadata_json:
        return None
    raw = metadata_json.get("pattern_confidence")
    if raw is None:
        return None
    try:
        return Decimal(str(raw))
    except Exception:  # noqa: BLE001 — metadata must never break worker loop
        return None


def _market_type_from_event(metadata_json: dict | None, *, default: str = "spot") -> str:
    if not metadata_json:
        return default
    mt = metadata_json.get("market_type")
    if mt in {"spot", "futures"}:
        return mt
    return default


def _leverage_from_event(metadata_json: dict | None) -> int:
    if not metadata_json:
        return 1
    raw = metadata_json.get("leverage")
    if raw is None:
        return 1
    try:
        lev = int(raw)
        return max(1, min(lev, 50))
    except (TypeError, ValueError):
        return 1


class SignalWorker:
    def __init__(
        self,
        *,
        settings: Settings,
        session_factory: async_sessionmaker[AsyncSession],
        executor: PaperExecutionPort,
        evaluator: SignalEvaluator | None = None,
        worker_id: str | None = None,
    ):
        assert_signal_paper_only(settings)
        self.settings = settings
        self.session_factory = session_factory
        self.executor = executor
        self.evaluator = evaluator or FakeSignalEvaluator(settings)
        self.worker_id = worker_id or f"worker-{uuid4().hex[:8]}"
        self._stop = asyncio.Event()

    def stop(self) -> None:
        self._stop.set()

    async def run_forever(self) -> None:
        if not self.settings.signal_worker_enabled:
            logger.warning("signal worker started but SIGNAL_WORKER_ENABLED=false")
        while not self._stop.is_set():
            processed = await self.poll_once()
            if not processed:
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=self.settings.signal_worker_poll_seconds)
                except TimeoutError:
                    pass

    async def poll_once(self) -> bool:
        async with self.session_factory() as session:
            repo = SignalRepository(session)
            job = await repo.claim_job(
                worker_id=self.worker_id,
                lease_seconds=self.settings.signal_worker_lease_seconds,
            )
            if job is None:
                return False
        # Process in a fresh session after claim commit.
        async with self.session_factory() as session:
            await self._process_job(session, job.id)
        return True

    async def _process_job(self, session: AsyncSession, job_id: str) -> None:
        from ..models import SignalJob

        repo = SignalRepository(session)
        job = await session.get(SignalJob, job_id)
        if job is None:
            return
        event = await repo.get_event(job.event_id)
        route = await repo.get_route(job.route_id) if event else None
        if event is None or route is None:
            await repo.dead_job(job, error_code="missing_event_or_route")
            return

        try:
            await self._run_pipeline(repo, job, event, route)
        except Exception:
            logger.exception("signal job failed unexpectedly event=%s", event.id)
            await repo.dead_job(job, error_code="worker_internal_error")
            await repo.transition_event(event, status="failed_closed", reason_code="worker_internal_error")
            await session.commit()

    async def _run_pipeline(self, repo: SignalRepository, job, event, route) -> None:
        session = repo.session
        await repo.transition_event(event, status="validating")
        await repo.add_audit(
            new_audit(
                actor_kind="worker",
                actor_subject=self.worker_id,
                route_id=route.id,
                event_id=event.id,
                request_id=event.request_id,
                transition="validating",
                route_version=route.version,
                policy_version=route.policy_version,
            )
        )
        await session.commit()

        # Global / route kill switches — more restrictive only.
        if not self.settings.signal_routes_enabled or not route.enabled:
            await self._fail(repo, job, event, "rejected_guardrail", "route_or_global_disabled")
            return
        if route.execution_target != "kraken_paper":
            await self._fail(repo, job, event, "failed_closed", "invalid_execution_target")
            return

        backlog = await repo.backlog_for_route(route.id)
        if backlog > route.max_backlog:
            await self._fail(repo, job, event, "rejected_guardrail", "backlog_cap_exceeded")
            return
        rate = await repo.count_recent_events(route.id, window_seconds=60)
        if rate > route.max_rate_per_minute:
            await self._fail(repo, job, event, "rejected_guardrail", "rate_cap_exceeded")
            return

        candidate = build_candidate(
            schema_version=event.schema_version,
            signal_id=event.signal_id,
            occurred_at=event.occurred_at.isoformat().replace("+00:00", "Z"),
            strategy_id=event.strategy_id,
            pair=event.pair,
            side=event.side,
            volume=Decimal(str(event.volume)),
            order_type=event.order_type,
            price=Decimal(str(event.price)) if event.price is not None else None,
            order_id=event.order_id,
            raw_symbol=event.raw_symbol,
            observed_price=Decimal(str(event.observed_price)) if event.observed_price is not None else None,
            source=event.source,  # type: ignore[arg-type]
            pattern_bias=_pattern_bias_from_event(event.metadata_json),
            pattern_confidence=_pattern_confidence_from_event(event.metadata_json),
        )
        if candidate.canonical_hash != event.canonical_hash:
            await self._fail(repo, job, event, "failed_closed", "canonical_hash_mismatch")
            return

        open_exposure = await repo.open_exposure_for_route(route.id)
        policy = check_route_policy(
            candidate,
            route,
            allow_all_pairs=bool(getattr(self.settings, "paper_allow_all_pairs", True)),
            current_open_exposure=open_exposure,
        )
        if not policy.ok:
            await self._fail(repo, job, event, "rejected_guardrail", policy.reason_code or "policy_rejected")
            return

        mode = effective_mode(event.mode_snapshot, route.mode)

        if mode == "bypass_ai":
            # Bypass must never instantiate/call evaluator beyond this branch.
            await repo.transition_event(event, status="bypass_approved")
            await repo.add_audit(
                new_audit(
                    actor_kind="worker",
                    actor_subject=self.worker_id,
                    route_id=route.id,
                    event_id=event.id,
                    request_id=event.request_id,
                    transition="bypass_approved",
                    route_version=route.version,
                    policy_version=route.policy_version,
                )
            )
            await session.commit()
        else:
            if not (self.settings.ai_advisory_enabled or self.settings.advisory_provider == "fake"):
                await self._fail(repo, job, event, "failed_closed", "advisory_unavailable")
                return
            await repo.transition_event(event, status="evaluating_advisory")
            await session.commit()
            raw = await self.evaluator.evaluate(
                candidate,
                policy_version=route.policy_version,
                deterministic_ok=True,
            )
            result = normalize_evaluation(
                raw,
                expected_hash=candidate.canonical_hash,
                expected_policy=route.policy_version,
                expected_provider=self.settings.advisory_provider,
                expected_model=self.settings.advisory_model,
            )
            await repo.add_evaluation(
                SignalEvaluation(
                    id=str(uuid4()),
                    event_id=event.id,
                    decision=result.decision,
                    reason_code=result.reason_code,
                    candidate_hash=result.candidate_hash,
                    provider=result.provider,
                    model=result.model,
                    prompt_version=result.prompt_version,
                    policy_version=result.policy_version,
                    latency_ms=result.latency_ms,
                )
            )
            if result.decision != "approve":
                status = "rejected_advisory" if result.decision == "reject" else "failed_closed"
                await self._fail(repo, job, event, status, result.reason_code)
                return
            # Re-check deterministic policy after approval (including tighter exposure).
            open_exposure_again = await repo.open_exposure_for_route(route.id)
            policy_again = check_route_policy(
                candidate,
                route,
                allow_all_pairs=bool(getattr(self.settings, "paper_allow_all_pairs", True)),
                current_open_exposure=open_exposure_again,
            )
            if not policy_again.ok:
                await self._fail(repo, job, event, "rejected_guardrail", policy_again.reason_code or "post_ai_policy")
                return
            await repo.transition_event(event, status="approved")
            await session.commit()

        if event.source == "fable_engine" and self.settings.fable_engine_dry_run:
            # Fable dry-run terminal: fully validated + policy-checked, never dispatched.
            await repo.transition_event(event, status="dry_run_recorded", reason_code="fable_dry_run")
            await repo.complete_job(job)
            await repo.add_audit(
                new_audit(
                    actor_kind="worker",
                    actor_subject=self.worker_id,
                    route_id=route.id,
                    event_id=event.id,
                    request_id=event.request_id,
                    transition="dry_run_recorded",
                    reason_code="fable_dry_run",
                    route_version=route.version,
                )
            )
            await session.commit()
            await self._notify_trade(kind="dry_run", event=event, candidate=candidate, reason_code="fable_dry_run")
            return

        if not self.settings.signal_execution_enabled:
            # Shadow mode: durable receipt + controls, no paper dispatch.
            await repo.complete_job(job)
            await repo.add_audit(
                new_audit(
                    actor_kind="worker",
                    actor_subject=self.worker_id,
                    route_id=route.id,
                    event_id=event.id,
                    request_id=event.request_id,
                    transition="shadow_complete",
                    reason_code="execution_disabled",
                    route_version=route.version,
                )
            )
            await session.commit()
            await self._notify_trade(
                kind="shadow",
                event=event,
                candidate=candidate,
                reason_code="execution_disabled",
            )
            return

        # Commit execution claim before subprocess.
        await repo.transition_event(event, status="paper_submitting")
        await session.commit()

        try:
            outcome = await self.executor.submit_paper(
                session=session,
                user_uid=route.owner_user_uid,
                event_id=event.id,
                pair=candidate.pair,
                side=candidate.side,
                volume=candidate.volume,
                order_type=candidate.order_type,
                price=candidate.price,
                request_id=event.request_id,
                market_type=_market_type_from_event(  # type: ignore[arg-type]
                    event.metadata_json,
                    default=self.settings.paper_default_market,
                ),
                leverage=_leverage_from_event(event.metadata_json),
            )
        except TimeoutError:
            await repo.transition_event(event, status="execution_unknown", reason_code="dispatch_timeout")
            await repo.dead_job(job, error_code="execution_unknown")
            await repo.add_audit(
                new_audit(
                    actor_kind="worker",
                    actor_subject=self.worker_id,
                    route_id=route.id,
                    event_id=event.id,
                    request_id=event.request_id,
                    transition="execution_unknown",
                    reason_code="dispatch_timeout",
                )
            )
            await session.commit()
            await self._notify_trade(
                kind="execution_unknown",
                event=event,
                candidate=candidate,
                reason_code="dispatch_timeout",
            )
            return
        except KrakenCliError as exc:
            await repo.transition_event(event, status="paper_failed", reason_code=exc.category)
            await repo.complete_job(job)
            await session.commit()
            await self._notify_trade(
                kind="paper_failed",
                event=event,
                candidate=candidate,
                reason_code=exc.category,
            )
            return

        await repo.transition_event(
            event,
            status="paper_accepted",
            paper_intent_id=str(outcome.get("intent_id")) if outcome.get("intent_id") else None,
        )
        await repo.complete_job(job)
        await repo.add_audit(
            new_audit(
                actor_kind="worker",
                actor_subject=self.worker_id,
                route_id=route.id,
                event_id=event.id,
                request_id=event.request_id,
                transition="paper_accepted",
                route_version=route.version,
            )
        )
        await session.commit()
        await self._notify_trade(kind="paper_accepted", event=event, candidate=candidate)

    async def _notify_trade(self, *, kind: str, event, candidate, reason_code: str | None = None) -> None:
        try:
            from ..integrations.telegram_trade_notify import notify_trade_signal

            await notify_trade_signal(
                self.settings,
                kind=kind,
                pair=str(candidate.pair),
                side=str(candidate.side),
                volume=str(candidate.volume),
                order_type=str(candidate.order_type),
                price=str(candidate.price) if candidate.price is not None else None,
                source=str(event.source) if getattr(event, "source", None) else None,
                signal_id=str(event.signal_id) if getattr(event, "signal_id", None) else None,
                reason_code=reason_code,
                request_id=str(event.request_id) if getattr(event, "request_id", None) else None,
            )
        except Exception:
            logger.debug("trade telegram notify failed", exc_info=True)

    async def _fail(self, repo: SignalRepository, job, event, status: str, reason: str) -> None:
        try:
            assert_transition(event.status if event.status in {"validating", "evaluating_advisory", "approved", "bypass_approved"} else "validating", status)  # type: ignore[arg-type]
        except ValueError:
            pass
        await repo.transition_event(event, status=status, reason_code=reason)
        await repo.complete_job(job)
        await repo.add_audit(
            new_audit(
                actor_kind="worker",
                actor_subject=self.worker_id,
                route_id=event.route_id,
                event_id=event.id,
                request_id=event.request_id,
                transition=status,
                reason_code=reason,
            )
        )
        await repo.session.commit()


async def run_signal_worker(settings: Settings, session_factory, executor: PaperExecutionPort) -> None:
    worker = SignalWorker(settings=settings, session_factory=session_factory, executor=executor)
    await worker.run_forever()
