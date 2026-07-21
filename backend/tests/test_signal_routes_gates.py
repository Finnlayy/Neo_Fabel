"""Plan §10 verification gates — paper-only, webhook auth/dedupe, bypass/advisory, policy."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from backend.app.settings import Settings
from backend.app.signals.auth import digest_credential, make_credential, verify_credential
from backend.app.signals.evaluator import EvaluationResult, FakeSignalEvaluator
from backend.app.signals.executor import FakePaperExecutionPort
from backend.app.signals.policy import (
    build_candidate,
    check_freshness,
    check_open_exposure,
    check_route_policy,
    effective_mode,
)
from backend.app.signals.safety import (
    FORBIDDEN_NAMES,
    SignalSafetyError,
    assert_signal_paper_only,
    assert_signals_module_imports,
)
from backend.app.signals.schemas import SignalRouteCreate, TradingViewWebhookBody
from backend.app.signals.service import SignalSubmissionService
from backend.app.signals.worker import SignalWorker


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _paper_settings(**overrides) -> Settings:
    """Build Settings isolated from .env.local / operator vault overlays."""
    base = dict(
        _env_file=None,
        kraken_live_trading_enabled=False,
        kraken_autonomy_level=2,
        signal_routes_enabled=True,
        tradingview_ingress_enabled=True,
        signal_worker_enabled=True,
        signal_execution_enabled=True,
        paper_allow_all_pairs=False,
        advisory_provider="fake",
        advisory_model="deterministic-fake-v1",
        ai_advisory_enabled=False,
        signal_credential_pepper="test-pepper",
        signal_max_age_seconds=300,
        signal_future_skew_seconds=30,
    )
    base.update(overrides)
    return Settings(**base)


def _route(**overrides):
    now = datetime.now(UTC)
    data = dict(
        id=str(uuid4()),
        owner_user_uid="owner-1",
        public_route_key="pubkey",
        name="route",
        strategy_id="S",
        mode="advisory",
        enabled=True,
        execution_target="kraken_paper",
        pair_allowlist="ADAUSD,XRPUSD",
        max_volume=Decimal("10"),
        max_notional=None,
        allowed_order_types="market",
        max_event_age_seconds=300,
        max_rate_per_minute=10,
        max_backlog=100,
        max_open_exposure=None,
        policy_version="v1",
        version=1,
        created_at=now,
        updated_at=now,
    )
    data.update(overrides)
    return SimpleNamespace(**data)


def _candidate(**overrides):
    kwargs = dict(
        schema_version=1,
        signal_id="sig-1",
        occurred_at="2026-07-18T12:00:00Z",
        strategy_id="S",
        pair="ADAUSD",
        side="buy",
        volume=Decimal("1"),
        order_type="market",
        price=None,
        order_id=None,
        raw_symbol=None,
        observed_price=None,
        source="tradingview",
    )
    kwargs.update(overrides)
    return build_candidate(**kwargs)


def _event_for(candidate, route, *, mode_snapshot: str = "bypass_ai", status: str = "queued"):
    return SimpleNamespace(
        id=str(uuid4()),
        route_id=route.id,
        source=candidate.source,
        signal_id=candidate.signal_id,
        canonical_hash=candidate.canonical_hash,
        schema_version=candidate.schema_version,
        strategy_id=candidate.strategy_id,
        pair=candidate.pair,
        side=candidate.side,
        volume=candidate.volume,
        order_type=candidate.order_type,
        price=candidate.price,
        order_id=candidate.order_id,
        raw_symbol=candidate.raw_symbol,
        observed_price=candidate.observed_price,
        occurred_at=datetime(2026, 7, 18, 12, 0, 0, tzinfo=UTC),
        mode_snapshot=mode_snapshot,
        route_version=route.version,
        policy_version=route.policy_version,
        request_id=str(uuid4()),
        status=status,
        reason_code=None,
        paper_intent_id=None,
        metadata_json={},
    )


def _job(event, route):
    return SimpleNamespace(id=str(uuid4()), event_id=event.id, route_id=route.id, status="leased")


def _mock_repo():
    repo = MagicMock()
    session = AsyncMock()
    session.commit = AsyncMock()
    repo.session = session
    repo.transition_event = AsyncMock()
    repo.add_audit = AsyncMock()
    repo.complete_job = AsyncMock()
    repo.dead_job = AsyncMock()
    repo.add_evaluation = AsyncMock()
    repo.backlog_for_route = AsyncMock(return_value=0)
    repo.count_recent_events = AsyncMock(return_value=0)
    repo.open_exposure_for_route = AsyncMock(return_value=Decimal("0"))
    return repo


# ---------------------------------------------------------------------------
# Paper-only / safe defaults
# ---------------------------------------------------------------------------


def test_signal_feature_flags_default_false():
    # Field defaults (not operator .env overlays).
    for name in (
        "signal_routes_enabled",
        "tradingview_ingress_enabled",
        "mcp_signal_adapter_enabled",
        "signal_worker_enabled",
        "signal_execution_enabled",
        "ai_advisory_enabled",
    ):
        assert Settings.model_fields[name].default is False
    settings = Settings(_env_file=None)
    assert settings.signal_routes_enabled is False
    assert settings.tradingview_ingress_enabled is False
    assert settings.mcp_signal_adapter_enabled is False
    assert settings.signal_worker_enabled is False
    assert settings.signal_execution_enabled is False
    assert settings.trade_commands_enabled is False


def test_route_create_default_allowlist_is_product_pairs():
    payload = SignalRouteCreate(name="n", strategy_id="S")
    allow = {p.strip() for p in payload.pair_allowlist.split(",")}
    assert "ADAUSD" in allow
    assert "XRPUSD" in allow
    assert "BTCUSD" not in allow


def test_forbidden_live_symbols_catalog():
    assert "Level4Session" in FORBIDDEN_NAMES
    assert "execute_order" in FORBIDDEN_NAMES
    assert "place_order" in FORBIDDEN_NAMES
    assert_signals_module_imports()


def test_paper_only_blocks_live_and_supervised_composition():
    # trade_commands_enabled is derived: live AND autonomy >= supervised.
    live_supervised = _paper_settings(
        kraken_live_trading_enabled=True,
        kraken_autonomy_level=3,
        signal_execution_enabled=False,
    )
    assert live_supervised.trade_commands_enabled is True
    with pytest.raises(SignalSafetyError, match="live trading"):
        assert_signal_paper_only(live_supervised)


def test_paper_only_blocks_autonomy_above_paper():
    settings = _paper_settings(kraken_autonomy_level=3, signal_execution_enabled=False)
    with pytest.raises(SignalSafetyError):
        assert_signal_paper_only(settings)


def test_worker_constructor_refuses_live_composition():
    executor = FakePaperExecutionPort(calls=[])
    with pytest.raises(SignalSafetyError):
        SignalWorker(
            settings=_paper_settings(kraken_live_trading_enabled=True),
            session_factory=MagicMock(),
            executor=executor,
        )


# ---------------------------------------------------------------------------
# Webhook schema / auth
# ---------------------------------------------------------------------------


def test_webhook_rejects_unknown_fields_and_non_positive_volume():
    with pytest.raises(ValidationError):
        TradingViewWebhookBody.model_validate(
            {
                "schema_version": 1,
                "credential": "tvsec_abcdefghijklmnopqrstuvwxyz012345",
                "signal_id": "x",
                "occurred_at": "2026-07-18T12:00:00Z",
                "strategy_id": "S",
                "pair": "ADAUSD",
                "side": "buy",
                "volume": "1",
                "order_type": "market",
                "unexpected": True,
            }
        )
    with pytest.raises(ValidationError):
        TradingViewWebhookBody.model_validate(
            {
                "schema_version": 1,
                "credential": "tvsec_abcdefghijklmnopqrstuvwxyz012345",
                "signal_id": "x",
                "occurred_at": "2026-07-18T12:00:00Z",
                "strategy_id": "S",
                "pair": "ADAUSD",
                "side": "buy",
                "volume": "0",
                "order_type": "market",
            }
        )


def test_credential_verify_wrong_revoked_expired():
    settings = _paper_settings()
    generated = make_credential("tradingview_secret", settings)
    assert verify_credential(
        generated.plaintext,
        generated.digest,
        settings,
        revoked_at=None,
        expires_at=None,
    )
    assert not verify_credential(
        "tvsec_wrong_token_value_xxxxxxxxxxxx",
        generated.digest,
        settings,
        revoked_at=None,
        expires_at=None,
    )
    assert not verify_credential(
        generated.plaintext,
        generated.digest,
        settings,
        revoked_at=datetime.now(UTC),
        expires_at=None,
    )
    assert not verify_credential(
        generated.plaintext,
        generated.digest,
        settings,
        revoked_at=None,
        expires_at=datetime.now(UTC) - timedelta(seconds=1),
    )


@pytest.mark.asyncio
async def test_submit_tradingview_unknown_route_auth_failed_no_disclosure():
    service = SignalSubmissionService(_paper_settings())
    session = AsyncMock()
    repo = MagicMock()
    repo.get_route_by_public_key = AsyncMock(return_value=None)

    body = TradingViewWebhookBody.model_validate(
        {
            "schema_version": 1,
            "credential": "tvsec_abcdefghijklmnopqrstuvwxyz012345",
            "signal_id": "sig",
            "occurred_at": "2026-07-18T12:00:00Z",
            "strategy_id": "S",
            "pair": "ADAUSD",
            "side": "buy",
            "volume": "1",
            "order_type": "market",
        }
    )

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("backend.app.signals.service.SignalRepository", lambda _s: repo)
        with pytest.raises(HTTPException) as exc:
            await service.submit_tradingview(
                session,
                public_route_key="missing",
                body=body,
                request_id="req-1",
                external_correlation_id=None,
            )
    assert exc.value.status_code == 401
    assert exc.value.detail["code"] == "auth_failed"


@pytest.mark.asyncio
async def test_submit_tradingview_wrong_credential_auth_failed():
    service = SignalSubmissionService(_paper_settings())
    session = AsyncMock()
    route = _route()
    cred = SimpleNamespace(
        id="c1",
        route_id=route.id,
        kind="tradingview_secret",
        digest=digest_credential("tvsec_correct_secret_token_xx", _paper_settings()),
        pepper_version="v1",
        revoked_at=None,
        expires_at=None,
        last_used_at=None,
    )
    repo = MagicMock()
    repo.get_route_by_public_key = AsyncMock(return_value=route)
    repo.active_credentials = AsyncMock(return_value=[cred])

    body = TradingViewWebhookBody.model_validate(
        {
            "schema_version": 1,
            "credential": "tvsec_wrong_secret_token_xxxxxxxx",
            "signal_id": "sig",
            "occurred_at": "2026-07-18T12:00:00Z",
            "strategy_id": "S",
            "pair": "ADAUSD",
            "side": "buy",
            "volume": "1",
            "order_type": "market",
        }
    )

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("backend.app.signals.service.SignalRepository", lambda _s: repo)
        with pytest.raises(HTTPException) as exc:
            await service.submit_tradingview(
                session,
                public_route_key=route.public_route_key,
                body=body,
                request_id="req-2",
                external_correlation_id=None,
            )
    assert exc.value.status_code == 401
    assert exc.value.detail["code"] == "auth_failed"


# ---------------------------------------------------------------------------
# Duplicate vs conflict
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_accept_duplicate_replays_without_new_job():
    settings = _paper_settings()
    service = SignalSubmissionService(settings)
    route = _route(mode="bypass_ai")
    candidate = _candidate()
    existing = SimpleNamespace(
        id=str(uuid4()),
        canonical_hash=candidate.canonical_hash,
        request_id="prior-req",
    )
    repo = MagicMock()
    repo.find_event = AsyncMock(return_value=existing)
    repo.insert_event_job_audit = AsyncMock()

    receipt = await service._accept(
        repo,
        route=route,
        credential=None,
        source="tradingview",
        signal_id=candidate.signal_id,
        schema_version=1,
        occurred_at_raw="2026-07-18T12:00:00Z",
        strategy_id="S",
        pair="ADAUSD",
        side="buy",
        volume=Decimal("1"),
        order_type="market",
        price=None,
        order_id=None,
        raw_symbol=None,
        observed_price=None,
        request_id="new-req",
        external_correlation_id=None,
    )
    assert receipt.replayed is True
    assert str(receipt.submission_id) == existing.id
    assert receipt.request_id == "prior-req"
    repo.insert_event_job_audit.assert_not_called()


@pytest.mark.asyncio
async def test_accept_same_signal_id_changed_payload_conflicts():
    settings = _paper_settings()
    service = SignalSubmissionService(settings)
    route = _route()
    existing = SimpleNamespace(
        id=str(uuid4()),
        canonical_hash="0" * 64,
        request_id="prior-req",
    )
    repo = MagicMock()
    repo.find_event = AsyncMock(return_value=existing)
    repo.insert_event_job_audit = AsyncMock()

    with pytest.raises(HTTPException) as exc:
        await service._accept(
            repo,
            route=route,
            credential=None,
            source="tradingview",
            signal_id="sig-1",
            schema_version=1,
            occurred_at_raw="2026-07-18T12:00:00Z",
            strategy_id="S",
            pair="ADAUSD",
            side="buy",
            volume=Decimal("1"),
            order_type="market",
            price=None,
            order_id=None,
            raw_symbol=None,
            observed_price=None,
            request_id="new-req",
            external_correlation_id=None,
        )
    assert exc.value.status_code == 409
    assert exc.value.detail["code"] == "signal_conflict"
    repo.insert_event_job_audit.assert_not_called()


# ---------------------------------------------------------------------------
# Policy / effective mode
# ---------------------------------------------------------------------------


def test_effective_mode_advisory_is_more_restrictive():
    assert effective_mode("bypass_ai", "bypass_ai") == "bypass_ai"
    assert effective_mode("bypass_ai", "advisory") == "advisory"
    assert effective_mode("advisory", "bypass_ai") == "advisory"
    assert effective_mode("advisory", "advisory") == "advisory"


def test_policy_reject_paths_product_pairs():
    route = _route(
        pair_allowlist="ADAUSD,XRPUSD",
        max_volume=Decimal("1"),
        max_notional=Decimal("100"),
        allowed_order_types="market",
        strategy_id="S",
    )
    ok = check_route_policy(_candidate(pair="ADAUSD", volume=Decimal("0.5")), route)
    assert ok.ok is True

    assert check_route_policy(_candidate(pair="BTCUSD"), route).reason_code == "pair_not_allowed"
    assert (
        check_route_policy(_candidate(order_type="limit", price=Decimal("0.5")), route).reason_code
        == "order_type_not_allowed"
    )
    assert (
        check_route_policy(_candidate(volume=Decimal("5")), route).reason_code == "volume_cap_exceeded"
    )
    assert (
        check_route_policy(_candidate(strategy_id="OTHER"), route).reason_code == "strategy_mismatch"
    )
    notional = check_route_policy(
        _candidate(volume=Decimal("1"), observed_price=Decimal("200")),
        route,
    )
    assert notional.reason_code == "notional_cap_exceeded"


def test_open_exposure_cap_rejects_when_projected_exceeds():
    route = _route(max_open_exposure=Decimal("5"), max_volume=Decimal("10"))
    ok = check_open_exposure(
        _candidate(side="buy", volume=Decimal("2")),
        route,
        current_open_exposure=Decimal("2"),
    )
    assert ok.ok is True

    blocked = check_route_policy(
        _candidate(side="buy", volume=Decimal("4")),
        route,
        current_open_exposure=Decimal("2"),
    )
    assert blocked.ok is False
    assert blocked.reason_code == "open_exposure_cap_exceeded"

    # None cap = uncapped; sells never consume the buy exposure budget.
    uncapped = _route(max_open_exposure=None, max_volume=Decimal("10"))
    assert check_open_exposure(
        _candidate(side="buy", volume=Decimal("100")),
        uncapped,
        current_open_exposure=Decimal("999"),
    ).ok is True
    assert check_open_exposure(
        _candidate(side="sell", volume=Decimal("100")),
        route,
        current_open_exposure=Decimal("5"),
    ).ok is True


def test_freshness_stale_and_future_skew():
    settings = _paper_settings(signal_max_age_seconds=60, signal_future_skew_seconds=5)
    route = _route(max_event_age_seconds=60)
    stale = datetime.now(UTC) - timedelta(seconds=120)
    future = datetime.now(UTC) + timedelta(seconds=30)
    assert check_freshness(stale, settings, route).reason_code == "stale_event"
    assert check_freshness(future, settings, route).reason_code == "future_skew"
    assert check_freshness(datetime.now(UTC), settings, route).ok is True


# ---------------------------------------------------------------------------
# Worker: bypass / advisory / policy / execution_unknown
# ---------------------------------------------------------------------------


class _CountingEvaluator:
    def __init__(self, decision: str = "approve"):
        self.calls = 0
        self.decision = decision

    async def evaluate(self, candidate, *, policy_version: str, deterministic_ok: bool):
        self.calls += 1
        return EvaluationResult(
            decision=self.decision,  # type: ignore[arg-type]
            reason_code=f"forced_{self.decision}",
            candidate_hash=candidate.canonical_hash,
            policy_version=policy_version,
            provider="fake",
            model="deterministic-fake-v1",
            prompt_version="v1",
            latency_ms=1,
        )


@pytest.mark.asyncio
async def test_bypass_never_calls_evaluator_and_can_dispatch():
    settings = _paper_settings(signal_execution_enabled=True, paper_allow_all_pairs=False)
    executor = FakePaperExecutionPort(calls=[])
    evaluator = _CountingEvaluator()
    worker = SignalWorker(
        settings=settings,
        session_factory=MagicMock(),
        executor=executor,
        evaluator=evaluator,  # type: ignore[arg-type]
    )
    route = _route(mode="bypass_ai", pair_allowlist="ADAUSD,XRPUSD")
    candidate = _candidate()
    event = _event_for(candidate, route, mode_snapshot="bypass_ai")
    job = _job(event, route)
    repo = _mock_repo()

    await worker._run_pipeline(repo, job, event, route)

    assert evaluator.calls == 0
    assert len(executor.calls) == 1
    assert executor.calls[0]["pair"] == "ADAUSD"
    repo.add_evaluation.assert_not_called()


@pytest.mark.asyncio
async def test_advisory_reject_fails_closed_without_executor():
    settings = _paper_settings(signal_execution_enabled=True, paper_allow_all_pairs=False)
    executor = FakePaperExecutionPort(calls=[])
    evaluator = _CountingEvaluator(decision="reject")
    worker = SignalWorker(
        settings=settings,
        session_factory=MagicMock(),
        executor=executor,
        evaluator=evaluator,  # type: ignore[arg-type]
    )
    route = _route(mode="advisory", pair_allowlist="ADAUSD")
    candidate = _candidate()
    event = _event_for(candidate, route, mode_snapshot="advisory")
    job = _job(event, route)
    repo = _mock_repo()

    await worker._run_pipeline(repo, job, event, route)

    assert evaluator.calls == 1
    assert executor.calls == []
    repo.complete_job.assert_awaited()


@pytest.mark.asyncio
async def test_advisory_abstain_fails_closed_without_executor():
    settings = _paper_settings(signal_execution_enabled=True)
    executor = FakePaperExecutionPort(calls=[])
    evaluator = FakeSignalEvaluator(settings, force_decision="abstain")
    worker = SignalWorker(
        settings=settings,
        session_factory=MagicMock(),
        executor=executor,
        evaluator=evaluator,
    )
    route = _route(mode="advisory")
    candidate = _candidate()
    event = _event_for(candidate, route, mode_snapshot="advisory")
    job = _job(event, route)
    repo = _mock_repo()

    await worker._run_pipeline(repo, job, event, route)
    assert executor.calls == []


@pytest.mark.asyncio
async def test_queued_bypass_upgraded_to_advisory_when_route_now_advisory():
    """Receipt-time bypass + current advisory → effective advisory (more restrictive)."""
    settings = _paper_settings(signal_execution_enabled=True)
    executor = FakePaperExecutionPort(calls=[])
    evaluator = _CountingEvaluator(decision="reject")
    worker = SignalWorker(
        settings=settings,
        session_factory=MagicMock(),
        executor=executor,
        evaluator=evaluator,  # type: ignore[arg-type]
    )
    route = _route(mode="advisory")
    candidate = _candidate()
    event = _event_for(candidate, route, mode_snapshot="bypass_ai")
    job = _job(event, route)
    repo = _mock_repo()

    await worker._run_pipeline(repo, job, event, route)

    assert evaluator.calls == 1
    assert executor.calls == []


@pytest.mark.asyncio
async def test_worker_policy_reject_skips_evaluator_and_executor():
    settings = _paper_settings(signal_execution_enabled=True, paper_allow_all_pairs=False)
    executor = FakePaperExecutionPort(calls=[])
    evaluator = _CountingEvaluator()
    worker = SignalWorker(
        settings=settings,
        session_factory=MagicMock(),
        executor=executor,
        evaluator=evaluator,  # type: ignore[arg-type]
    )
    route = _route(mode="bypass_ai", pair_allowlist="XRPUSD", max_volume=Decimal("0.1"))
    candidate = _candidate(pair="ADAUSD", volume=Decimal("1"))
    event = _event_for(candidate, route, mode_snapshot="bypass_ai")
    job = _job(event, route)
    repo = _mock_repo()

    await worker._run_pipeline(repo, job, event, route)

    assert evaluator.calls == 0
    assert executor.calls == []


@pytest.mark.asyncio
async def test_worker_rejects_open_exposure_cap():
    settings = _paper_settings(signal_execution_enabled=True, paper_allow_all_pairs=False)
    executor = FakePaperExecutionPort(calls=[])
    worker = SignalWorker(
        settings=settings,
        session_factory=MagicMock(),
        executor=executor,
        evaluator=_CountingEvaluator(),  # type: ignore[arg-type]
    )
    route = _route(mode="bypass_ai", max_open_exposure=Decimal("1"), max_volume=Decimal("10"))
    candidate = _candidate(volume=Decimal("1"))
    event = _event_for(candidate, route, mode_snapshot="bypass_ai")
    job = _job(event, route)
    repo = _mock_repo()
    repo.open_exposure_for_route = AsyncMock(return_value=Decimal("1"))

    await worker._run_pipeline(repo, job, event, route)

    assert executor.calls == []
    reason_codes = [c.kwargs.get("reason_code") for c in repo.transition_event.await_args_list]
    assert "open_exposure_cap_exceeded" in reason_codes


@pytest.mark.asyncio
async def test_dispatch_timeout_yields_execution_unknown_no_retry_path():
    settings = _paper_settings(signal_execution_enabled=True)
    executor = FakePaperExecutionPort(calls=[], hang_after_claim=True)
    worker = SignalWorker(
        settings=settings,
        session_factory=MagicMock(),
        executor=executor,
        evaluator=_CountingEvaluator(),  # type: ignore[arg-type]
    )
    route = _route(mode="bypass_ai")
    candidate = _candidate()
    event = _event_for(candidate, route, mode_snapshot="bypass_ai")
    job = _job(event, route)
    repo = _mock_repo()

    await worker._run_pipeline(repo, job, event, route)

    assert len(executor.calls) == 1
    repo.dead_job.assert_awaited()
    # transition_event called with execution_unknown among other transitions
    statuses = [
        call.kwargs.get("status") or (call.args[1] if len(call.args) > 1 else None)
        for call in repo.transition_event.await_args_list
    ]
    # transition_event(event, status=...)
    status_kwargs = [c.kwargs.get("status") for c in repo.transition_event.await_args_list]
    assert "execution_unknown" in status_kwargs or any(
        "execution_unknown" in str(c) for c in repo.transition_event.await_args_list
    )
    assert statuses or status_kwargs  # sanity: transitions occurred
