import pytest
from decimal import Decimal
from uuid import UUID

from app.signals.repository import new_route
from app.models import SignalRoute

def test_new_route():
    # Test inputs
    owner_uid = "user-123"
    name = "Test Route"
    strategy_id = "strat-456"
    pair_allowlist = "BTC/USD,ETH/USD"
    max_volume = Decimal("1000.50")
    max_notional = Decimal("50000.00")
    allowed_order_types = "limit,market"
    max_event_age_seconds = 300
    max_rate_per_minute = 10
    max_backlog = 5
    policy_version = "v1"

    # Call the function
    route = new_route(
        owner_uid=owner_uid,
        name=name,
        strategy_id=strategy_id,
        pair_allowlist=pair_allowlist,
        max_volume=max_volume,
        max_notional=max_notional,
        allowed_order_types=allowed_order_types,
        max_event_age_seconds=max_event_age_seconds,
        max_rate_per_minute=max_rate_per_minute,
        max_backlog=max_backlog,
        policy_version=policy_version,
    )

    # Assertions
    assert isinstance(route, SignalRoute)

    # ID should be a valid UUID string
    try:
        UUID(route.id, version=4)
    except ValueError:
        pytest.fail("route.id is not a valid UUID4")

    assert route.owner_user_uid == owner_uid
    assert route.name == name
    assert route.strategy_id == strategy_id
    assert route.pair_allowlist == pair_allowlist
    assert route.max_volume == max_volume
    assert route.max_notional == max_notional
    assert route.allowed_order_types == allowed_order_types
    assert route.max_event_age_seconds == max_event_age_seconds
    assert route.max_rate_per_minute == max_rate_per_minute
    assert route.max_backlog == max_backlog
    assert route.policy_version == policy_version

    # Check default values
    assert route.mode == "advisory"
    assert route.enabled is False
    assert route.execution_target == "kraken_paper"
    assert isinstance(route.public_route_key, str)
    assert len(route.public_route_key) > 0

def test_new_route_null_notional():
    # Test inputs with None for max_notional
    route = new_route(
        owner_uid="user-123",
        name="Test Route 2",
        strategy_id="strat-456",
        pair_allowlist="BTC/USD",
        max_volume=Decimal("10.0"),
        max_notional=None,
        allowed_order_types="market",
        max_event_age_seconds=60,
        max_rate_per_minute=5,
        max_backlog=1,
        policy_version="v2",
    )

    assert route.max_notional is None
