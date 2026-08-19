"""Ledger v2 migration and combined performance."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from backend.app.integrations.local_paper import LocalPaperLedger, reset_local_paper_ledger_for_tests
from backend.app.integrations.paper_factory import build_paper_router
from backend.app.integrations.paper_performance import build_combined_performance
from backend.app.settings import Settings


@pytest.mark.asyncio
async def test_v1_ledger_migrates_to_v2(tmp_path: Path) -> None:
    v1 = {
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
            }
        ],
    }
    path = tmp_path / "ledger.json"
    path.write_text(__import__("json").dumps(v1), encoding="utf-8")

    ledger = LocalPaperLedger(_path=path)
    state = ledger.snapshot_state()
    assert state["version"] == 2
    assert state["spot"]["usd_balance"] == "9500"
    assert "BTCUSD" in (state["spot"].get("lots") or {})
    assert state["futures"]["margin_balance_usd"] is not None


def test_combined_performance_splits_books() -> None:
    state = {
        "version": 2,
        "spot": {
            "starting_balance_usd": "10000",
            "usd_balance": "9000",
            "lots": {},
            "fills": [],
        },
        "futures": {
            "starting_margin_usd": "10000",
            "margin_balance_usd": "9800",
            "positions": {},
            "fills": [],
        },
    }
    perf = build_combined_performance(state=state, mark_prices={})
    assert perf["ledger_version"] == 2
    assert perf["spot"] is not None
    assert perf["futures"] is not None
    assert Decimal(perf["combined_equity_usd"]) == Decimal(perf["spot"]["equity_usd"]) + Decimal(
        perf["futures"]["equity_usd"]
    )


def test_paper_factory_prefer_local() -> None:
    reset_local_paper_ledger_for_tests()
    settings = Settings(paper_local_ledger=True)
    router = build_paper_router(settings)
    assert router.prefer_local is True


@pytest.mark.asyncio
async def test_futures_roundtrip(tmp_path: Path) -> None:
    reset_local_paper_ledger_for_tests()
    ledger = LocalPaperLedger(
        starting_margin_usd=Decimal(10000),
        _path=tmp_path / "fut.json",
    )
    ledger.set_price_resolver(AsyncMock(return_value=Decimal(50000)))
    buy = await ledger.paper_order(
        "buy", "BTCUSD", Decimal("0.01"), "market", None, market_type="futures", leverage=5
    )
    assert buy["market_type"] == "futures"
    status = await ledger.paper_status()
    assert status["futures"]["open_positions"] == 1
