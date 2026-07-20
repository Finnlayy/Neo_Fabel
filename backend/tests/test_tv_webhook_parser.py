"""TradingView natural webhook → Kraken order field parser."""

from decimal import Decimal

import pytest

from backend.app.signals.tv_webhook_parser import (
    TvWebhookParseError,
    normalize_kraken_pair,
    parse_tradingview_natural_webhook,
    to_kraken_order_payload,
)


def _base(**overrides):
    body = {
        "schema_version": 1,
        "credential": "tvsec_test_secret_ok",
        "signal_id": "ord-1-2026-07-20T21:00:00Z",
        "occurred_at": "2026-07-20T21:00:00Z",
        "strategy_id": "lvn_break",
        "pair": "BTCUSD",
        "side": "buy",
        "volume": "0.001",
        "order_type": "market",
        "price": None,
        "order_id": "ord-1",
        "raw_symbol": "COINBASE:BTCUSD",
        "observed_price": "64059.78",
    }
    body.update(overrides)
    return body


def test_strict_neo_payload_parses():
    body = parse_tradingview_natural_webhook(_base())
    assert body.pair == "BTCUSD"
    assert body.side == "buy"
    assert body.volume == Decimal("0.001")
    kraken = to_kraken_order_payload(body)
    assert kraken == {
        "pair": "BTCUSD",
        "side": "buy",
        "volume": "0.001",
        "ordertype": "market",
        "price": None,
        "oflags": None,
        "client_order_id": "ord-1",
    }


def test_official_tv_placeholders_resolved_shape():
    """Shape after TradingView expands {{strategy.order.*}} / {{timenow}} / {{close}}."""
    body = parse_tradingview_natural_webhook(
        {
            "schema_version": 1,
            "credential": "tvsec_test_secret_ok",
            "signal_id": "Long-2026-07-20T21:10:43Z",
            "occurred_at": "2026-07-20T21:10:43Z",
            "strategy_id": "lvn_break",
            "pair": "BTCUSD",
            "side": "buy",
            "volume": "0.01",
            "order_type": "market",
            "price": None,
            "order_id": "Long",
            "raw_symbol": "COINBASE:BTCUSD",
            "observed_price": "64059.78",
        }
    )
    assert body.side == "buy"
    assert to_kraken_order_payload(body)["volume"] == "0.01"


def test_natural_aliases_and_coinbase_symbol():
    body = parse_tradingview_natural_webhook(
        {
            "credential": "tvsec_test_secret_ok",
            "strategy": "lvn_break",
            "ticker": "COINBASE:BTCUSD",
            "action": "buy",
            "contracts": 0.002,
            "timenow": "2026-07-20T21:10:43Z",
            "close": 64059.78,
            "type": "market",
        }
    )
    assert body.pair == "BTCUSD"
    assert body.side == "buy"
    assert body.volume == Decimal("0.002")
    assert body.observed_price == Decimal("64059.78")
    assert body.strategy_id == "lvn_break"


def test_binance_usdt_maps_to_usd_spot_pair():
    assert normalize_kraken_pair("BINANCE:BTCUSDT") == "BTCUSD"
    assert normalize_kraken_pair("BTC/USDT") == "BTCUSD"
    assert normalize_kraken_pair("XBTUSD") == "BTCUSD"


def test_sell_aliases():
    body = parse_tradingview_natural_webhook(_base(side="short", pair="XRPUSD"))
    assert body.side == "sell"
    body3 = parse_tradingview_natural_webhook(
        {
            "credential": "tvsec_test_secret_ok",
            "strategy_id": "s",
            "pair": "ADAUSD",
            "action": "sell",
            "volume": "1",
            "occurred_at": "2026-07-20T21:00:00Z",
        }
    )
    assert body3.side == "sell"


def test_rejects_unresolved_placeholders():
    with pytest.raises(TvWebhookParseError) as exc:
        parse_tradingview_natural_webhook(_base(side="{{strategy.order.action}}"))
    assert exc.value.code == "unresolved_placeholder"


def test_rejects_exponent_volume():
    with pytest.raises(TvWebhookParseError) as exc:
        parse_tradingview_natural_webhook(_base(volume="1e-3"))
    assert exc.value.code == "invalid_decimal"


def test_unix_timenow():
    body = parse_tradingview_natural_webhook(_base(occurred_at="1721509843"))
    assert body.occurred_at.endswith("Z")


def test_limit_requires_price():
    with pytest.raises(TvWebhookParseError) as exc:
        parse_tradingview_natural_webhook(_base(order_type="limit", price=None))
    assert exc.value.code == "missing_price"


def test_limit_order_kraken_fields():
    body = parse_tradingview_natural_webhook(_base(order_type="limit", price="64000"))
    kraken = to_kraken_order_payload(body)
    assert kraken["ordertype"] == "limit"
    assert kraken["price"] == "64000"
