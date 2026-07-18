from decimal import Decimal

import pytest
from pydantic import ValidationError

from backend.app.settings import Settings
from backend.app.signals.domain import LEGAL_TRANSITIONS, assert_transition
from backend.app.signals.evaluator import FakeSignalEvaluator, normalize_evaluation
from backend.app.signals.policy import build_candidate, canonical_hash_for, check_route_policy
from backend.app.signals.safety import SignalSafetyError, assert_signal_paper_only, assert_signals_module_imports
from backend.app.signals.schemas import TradingViewWebhookBody
from backend.app.trading.autonomy import AutonomyLevel


def test_signals_package_forbids_live_kraken_symbols():
    assert_signals_module_imports()


def test_paper_only_assertion_blocks_live_flags():
    settings = Settings(
        kraken_live_trading_enabled=True,
        kraken_autonomy_level=2,
    )
    with pytest.raises(SignalSafetyError):
        assert_signal_paper_only(settings)


def test_paper_only_allows_paper_autonomy():
    settings = Settings(
        kraken_live_trading_enabled=False,
        kraken_autonomy_level=2,
        signal_execution_enabled=True,
    )
    assert settings.autonomy == AutonomyLevel.PAPER
    assert_signal_paper_only(settings)


def test_webhook_schema_forbids_unknown_fields():
    with pytest.raises(ValidationError):
        TradingViewWebhookBody.model_validate(
            {
                "schema_version": 1,
                "credential": "tvsec_abcdefghijklmnopqrstuvwxyz012345",
                "signal_id": "x",
                "occurred_at": "2026-07-18T12:00:00Z",
                "strategy_id": "S",
                "pair": "BTCUSD",
                "side": "buy",
                "volume": "0.001",
                "order_type": "market",
                "extra": "nope",
            }
        )


def test_canonical_hash_stable_and_credential_free():
    h1 = canonical_hash_for(
        schema_version=1,
        signal_id="a",
        occurred_at="2026-07-18T12:00:00Z",
        strategy_id="S",
        pair="BTCUSD",
        side="buy",
        volume=Decimal("0.001"),
        order_type="market",
        price=None,
        order_id=None,
        raw_symbol=None,
        observed_price=None,
        source="tradingview",
    )
    h2 = canonical_hash_for(
        schema_version=1,
        signal_id="a",
        occurred_at="2026-07-18T12:00:00Z",
        strategy_id="S",
        pair="BTCUSD",
        side="buy",
        volume=Decimal("0.001"),
        order_type="market",
        price=None,
        order_id=None,
        raw_symbol=None,
        observed_price=None,
        source="tradingview",
    )
    assert h1 == h2
    assert "tvsec" not in h1


def test_legal_transitions_cover_happy_paths():
    assert_transition("queued", "validating")
    assert_transition("validating", "bypass_approved")
    assert_transition("bypass_approved", "paper_submitting")
    assert_transition("paper_submitting", "execution_unknown")
    with pytest.raises(ValueError):
        assert_transition("paper_accepted", "paper_submitting")
    assert "evaluating_advisory" in LEGAL_TRANSITIONS["validating"]


@pytest.mark.asyncio
async def test_fake_evaluator_approve_and_normalize_hash_mismatch():
    settings = Settings(advisory_provider="fake", advisory_model="deterministic-fake-v1")
    evaluator = FakeSignalEvaluator(settings)
    candidate = build_candidate(
        schema_version=1,
        signal_id="a",
        occurred_at="2026-07-18T12:00:00Z",
        strategy_id="S",
        pair="BTCUSD",
        side="buy",
        volume=Decimal("0.001"),
        order_type="market",
        price=None,
        order_id=None,
        raw_symbol=None,
        observed_price=None,
        source="tradingview",
    )
    result = await evaluator.evaluate(candidate, policy_version="v1", deterministic_ok=True)
    assert result.decision == "approve"
    mismatched = normalize_evaluation(
        result,
        expected_hash="0" * 64,
        expected_policy="v1",
        expected_provider="fake",
        expected_model="deterministic-fake-v1",
    )
    assert mismatched.decision == "abstain"
    assert mismatched.reason_code == "candidate_hash_mismatch"


def test_route_policy_rejects_pair():
    from backend.app.models import SignalRoute
    from datetime import UTC, datetime
    from uuid import uuid4

    route = SignalRoute(
        id=str(uuid4()),
        owner_user_uid="u",
        public_route_key="k",
        name="n",
        strategy_id="S",
        mode="advisory",
        enabled=True,
        execution_target="kraken_paper",
        pair_allowlist="ETHUSD",
        max_volume=Decimal("1"),
        max_notional=None,
        allowed_order_types="market",
        max_event_age_seconds=300,
        max_rate_per_minute=10,
        max_backlog=100,
        policy_version="v1",
        version=1,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    candidate = build_candidate(
        schema_version=1,
        signal_id="a",
        occurred_at="2026-07-18T12:00:00Z",
        strategy_id="S",
        pair="BTCUSD",
        side="buy",
        volume=Decimal("0.001"),
        order_type="market",
        price=None,
        order_id=None,
        raw_symbol=None,
        observed_price=None,
        source="tradingview",
    )
    result = check_route_policy(candidate, route)
    assert result.ok is False
    assert result.reason_code == "pair_not_allowed"
