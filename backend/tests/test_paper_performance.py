"""Paper ledger FIFO PnL, persistence, and performance API."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.auth import require_user
from backend.app.integrations.local_paper import LocalPaperLedger, reset_local_paper_ledger_for_tests
from backend.app.integrations.paper_performance import build_performance_snapshot
from backend.app.main import app

client = TestClient(app)


@pytest.fixture
def authenticated_user() -> None:
    app.dependency_overrides[require_user] = lambda: {
        "uid": "paper-test-user",
        "email_verified": True,
        "firebase": {"sign_in_provider": "google.com"},
    }
    yield
    app.dependency_overrides.pop(require_user, None)


@pytest.fixture
def isolated_ledger(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> LocalPaperLedger:
    reset_local_paper_ledger_for_tests()
    monkeypatch.setattr("backend.app.integrations.paper_paths.LEDGER_FILE", tmp_path / "ledger.json")

    async def _price(market_type: str, pair: str) -> Decimal:
        prices = {"BTCUSD": Decimal("50000"), "ETHUSD": Decimal("3000")}
        return prices.get(pair.upper(), Decimal("100"))

    isolated = LocalPaperLedger(starting_balance_usd=Decimal("10000"), _path=tmp_path / "ledger.json")
    isolated.set_price_resolver(_price)
    return isolated


@pytest.mark.asyncio
async def test_fifo_realized_pnl_on_sell(isolated_ledger: LocalPaperLedger) -> None:
    buy = await isolated_ledger.paper_order("buy", "BTCUSD", Decimal("0.01"), "market", None)
    assert buy["ok"] is True
    sell = await isolated_ledger.paper_order("sell", "BTCUSD", Decimal("0.01"), "limit", Decimal("52000"))
    assert sell["ok"] is True
    order = sell["order"]
    realized = Decimal(str(order["realized_pnl"]))
    # Proceeds 520 - fee; cost ~500 + buy fee; should be positive
    assert realized > 0
    fee = Decimal(str(order["fee"]))
    assert fee == Decimal("52000") * Decimal("0.01") * Decimal("0")  # limit = maker 0%


@pytest.mark.asyncio
async def test_persistence_roundtrip(isolated_ledger: LocalPaperLedger) -> None:
    await isolated_ledger.paper_order("buy", "ETHUSD", Decimal("1"), "market", None)
    assert isolated_ledger._path.exists()  # noqa: SLF001

    reloaded = LocalPaperLedger(
        starting_balance_usd=Decimal("10000"),
        _path=isolated_ledger._path,  # noqa: SLF001
    )
    assert len(reloaded.snapshot_state().get("spot", {}).get("fills") or []) == 1


@pytest.mark.asyncio
async def test_insufficient_balance_rejected(isolated_ledger: LocalPaperLedger) -> None:
    with pytest.raises(ValueError, match="insufficient USD"):
        await isolated_ledger.paper_order("buy", "BTCUSD", Decimal("1"), "market", None)


def test_performance_snapshot_metrics() -> None:
    state = {
        "starting_balance_usd": "10000",
        "usd_balance": "9500",
        "lots": {"BTCUSD": [{"volume": "0.01", "unit_cost": "50000"}]},
        "fills": [
            {
                "pair": "BTCUSD",
                "side": "buy",
                "volume": "0.01",
                "price": "50000",
                "fee": "2.5",
                "realized_pnl": "0",
                "time": "2026-01-01T00:00:00Z",
            },
            {
                "pair": "BTCUSD",
                "side": "sell",
                "volume": "0.005",
                "price": "51000",
                "fee": "1.275",
                "realized_pnl": "45",
                "time": "2026-01-02T00:00:00Z",
            },
        ],
    }
    perf = build_performance_snapshot(state=state, mark_prices={"BTCUSD": Decimal("50500")})
    assert perf["fill_count"] == 2
    assert Decimal(perf["realized_pnl_usd"]) == Decimal("45")
    assert perf["win_rate"] == 1.0
    assert len(perf["positions"]) == 1
    assert len(perf["equity_curve"]) >= 2


@pytest.mark.asyncio
async def test_paper_performance_api(authenticated_user, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    reset_local_paper_ledger_for_tests()
    ledger_file = tmp_path / "ledger.json"
    monkeypatch.setattr("backend.app.integrations.paper_paths.LEDGER_FILE", ledger_file)
    monkeypatch.setattr("backend.app.integrations.paper_paths.ledger_path", lambda: ledger_file)

    async def _price(_market_type: str, pair: str) -> Decimal:
        return Decimal("50000")

    from backend.app.integrations.local_paper import get_local_paper_ledger

    ledger = get_local_paper_ledger()
    ledger.set_price_resolver(_price)
    await ledger.paper_order("buy", "BTCUSD", Decimal("0.001"), "market", None)

    async def _mock_ticker(pair: str):
        return {"last": "51000", "price": "51000"}, "kraken-public"

    monkeypatch.setattr("backend.app.main.crypto_ticker_data", _mock_ticker)

    resp = client.get("/api/v1/paper/performance")
    assert resp.status_code == 200
    body = resp.json()
    assert body["mode"] == "paper"
    assert body["execution"] == "paper-only"
    assert body["fill_count"] >= 1
    assert "equity_usd" in body
    assert "positions" in body
    assert "fills" in body
