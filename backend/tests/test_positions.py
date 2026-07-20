"""Positions list and close API."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.app.auth import require_user
from backend.app.integrations.local_paper import LocalPaperLedger, reset_local_paper_ledger_for_tests
from backend.app.integrations.positions import parse_live_balances, parse_open_orders
from backend.app.main import app

client = TestClient(app)


@pytest.fixture
def authenticated_user() -> None:
    app.dependency_overrides[require_user] = lambda: {
        "uid": "positions-test-user",
        "email_verified": True,
        "firebase": {"sign_in_provider": "google.com"},
    }
    yield
    app.dependency_overrides.pop(require_user, None)


def test_parse_live_balances_skips_fiat() -> None:
    rows = parse_live_balances({"BTC": "0.01", "USD": "5000", "ETH": "0"})
    assert len(rows) == 1
    assert rows[0]["asset"] == "BTC"
    assert rows[0]["pair"] == "BTCUSD"


def test_parse_open_orders_dict_shape() -> None:
    rows = parse_open_orders(
        {
            "open": {
                "O1": {
                    "txid": "O1",
                    "pair": "BTCUSD",
                    "vol": "0.001",
                    "descr": {"type": "buy", "price": "50000"},
                }
            }
        }
    )
    assert len(rows) == 1
    assert rows[0]["side"] == "buy"


@pytest.mark.asyncio
async def test_build_positions_skips_kraken_when_paper_only() -> None:
    from unittest.mock import AsyncMock

    from backend.app.integrations.kraken_cli import KrakenCliError
    from backend.app.integrations.positions import build_positions_snapshot

    cli = AsyncMock()
    cli.balance = AsyncMock(side_effect=KrakenCliError("config", "kraken executable is not installed"))
    cli.open_orders = AsyncMock(side_effect=KrakenCliError("config", "kraken executable is not installed"))

    async def _ticker(_pair: str):
        return {"last": "1"}, "test"

    snap = await build_positions_snapshot(
        paper_positions=[{"pair": "BTCUSD", "volume": "0.01"}],
        cli=cli,
        ticker_fn=_ticker,
        live_trading_enabled=False,
        trade_commands_enabled=False,
    )
    assert snap["errors"] == []
    assert snap["live"] == []
    assert snap["open_orders"] == []
    assert len(snap["paper"]) == 1
    cli.balance.assert_not_called()
    cli.open_orders.assert_not_called()


@pytest.mark.asyncio
async def test_close_paper_position_api(authenticated_user, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    reset_local_paper_ledger_for_tests()
    ledger_file = tmp_path / "ledger.json"
    monkeypatch.setattr("backend.app.integrations.paper_paths.LEDGER_FILE", ledger_file)
    monkeypatch.setattr("backend.app.integrations.paper_paths.ledger_path", lambda: ledger_file)

    async def _price(_market_type: str, pair: str) -> Decimal:
        return Decimal("50000")

    from backend.app.integrations.local_paper import get_local_paper_ledger

    ledger = get_local_paper_ledger()
    ledger.set_price_resolver(_price)
    await ledger.paper_order("buy", "BTCUSD", Decimal("0.01"), "market", None)

    list_resp = client.get("/api/v1/positions")
    assert list_resp.status_code == 200
    body = list_resp.json()
    assert len(body["paper"]) == 1

    close_resp = client.post(
        "/api/v1/positions/close",
        json={
            "pair": "BTCUSD",
            "mode": "paper",
            "order_type": "market",
            "idempotency_key": str(uuid4()),
        },
    )
    assert close_resp.status_code == 200, close_resp.text
    assert close_resp.json()["status"] == "ACCEPTED"

    after = client.get("/api/v1/positions")
    assert after.json()["paper"] == []

@pytest.mark.asyncio
async def test_open_volume_helper(tmp_path: Path) -> None:
    async def _price(_market_type: str, _pair: str) -> Decimal:
        return Decimal("100")

    ledger = LocalPaperLedger(starting_balance_usd=Decimal("10000"), _path=tmp_path / "ledger.json")
    ledger.set_price_resolver(_price)
    await ledger.paper_order("buy", "ETHUSD", Decimal("2"), "market", None)
    assert ledger.open_volume("ETHUSD") == Decimal("2")
