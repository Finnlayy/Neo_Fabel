from decimal import Decimal
import pytest
from backend.app.signals.policy import canonical_hash_for

def get_base_kwargs():
    return {
        "schema_version": 1,
        "signal_id": "test-id-123",
        "occurred_at": "2023-01-01T12:00:00Z",
        "strategy_id": "strat-A",
        "pair": "BTCUSD",
        "side": "buy",
        "volume": Decimal("1.5"),
        "order_type": "market",
        "price": Decimal("50000.0"),
        "order_id": "order-123",
        "raw_symbol": "BTC/USD",
        "observed_price": Decimal("49999.5"),
        "source": "tradingview",
    }

def test_canonical_hash_for_determinism():
    kwargs1 = get_base_kwargs()
    kwargs2 = get_base_kwargs()

    hash1 = canonical_hash_for(**kwargs1)
    hash2 = canonical_hash_for(**kwargs2)

    assert hash1 == hash2
    assert isinstance(hash1, str)
    assert len(hash1) == 64  # SHA-256 hexdigest length

def test_canonical_hash_for_changes():
    base_kwargs = get_base_kwargs()
    base_hash = canonical_hash_for(**base_kwargs)

    # Change side
    kwargs_side = get_base_kwargs()
    kwargs_side["side"] = "sell"
    assert canonical_hash_for(**kwargs_side) != base_hash

    # Change volume
    kwargs_vol = get_base_kwargs()
    kwargs_vol["volume"] = Decimal("2.0")
    assert canonical_hash_for(**kwargs_vol) != base_hash

    # Change time
    kwargs_time = get_base_kwargs()
    kwargs_time["occurred_at"] = "2023-01-01T12:00:01Z"
    assert canonical_hash_for(**kwargs_time) != base_hash

def test_canonical_hash_for_optional_fields():
    base_kwargs = get_base_kwargs()
    base_hash = canonical_hash_for(**base_kwargs)

    kwargs_none = get_base_kwargs()
    kwargs_none["price"] = None
    kwargs_none["order_id"] = None
    kwargs_none["raw_symbol"] = None
    kwargs_none["observed_price"] = None

    hash_none = canonical_hash_for(**kwargs_none)

    assert hash_none != base_hash

    # Verify determinism for None fields
    kwargs_none_2 = get_base_kwargs()
    kwargs_none_2["price"] = None
    kwargs_none_2["order_id"] = None
    kwargs_none_2["raw_symbol"] = None
    kwargs_none_2["observed_price"] = None

    assert hash_none == canonical_hash_for(**kwargs_none_2)
