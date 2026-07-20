"""Local paper ledger + router fallback (Phase 3)."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from backend.app.integrations.kraken_cli import KrakenCliError
from backend.app.integrations.local_paper import LocalPaperLedger, reset_local_paper_ledger_for_tests
from backend.app.integrations.paper_router import PaperExecutionRouter


async def _mock_price(_market_type: str, pair: str) -> Decimal:
    prices = {"BTCUSD": Decimal("50000"), "ETHUSD": Decimal("3000")}
    return prices.get(pair.upper().replace("/", "").replace("-", ""), Decimal("100"))


@pytest.fixture
def isolated_ledger(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> LocalPaperLedger:
    reset_local_paper_ledger_for_tests()
    monkeypatch.setattr("backend.app.integrations.paper_paths.LEDGER_FILE", tmp_path / "ledger.json")
    ledger = LocalPaperLedger(_path=tmp_path / "ledger.json")
    ledger.set_price_resolver(_mock_price)
    return ledger


@pytest.mark.asyncio
async def test_local_ledger_accepts_market_order(isolated_ledger: LocalPaperLedger) -> None:
    result = await isolated_ledger.paper_order("buy", "BTC/USD", Decimal("0.001"), "market", None)
    assert result["ok"] is True
    assert result["source"] == "local-paper-ledger"
    assert result["market_type"] == "spot"
    status = await isolated_ledger.paper_status()
    assert len(status["orders"]) == 1
    assert status["orders"][0]["pair"] == "BTCUSD"


@pytest.mark.asyncio
async def test_router_falls_back_when_cli_missing(isolated_ledger: LocalPaperLedger) -> None:
    cli = AsyncMock()
    cli.paper_order = AsyncMock(side_effect=KrakenCliError("config", "kraken executable is not installed"))
    cli.paper_status = AsyncMock(side_effect=KrakenCliError("config", "kraken executable is not installed"))
    router = PaperExecutionRouter(cli=cli, ledger=isolated_ledger)
    result = await router.paper_order("buy", "ETHUSD", Decimal("0.01"), "market", None)
    assert result["source"] == "local-paper-ledger"
    status = await router.paper_status()
    assert status["source"] == "local-paper-ledger"


@pytest.mark.asyncio
async def test_router_prefer_local_skips_cli(isolated_ledger: LocalPaperLedger) -> None:
    cli = AsyncMock()
    cli.paper_order = AsyncMock(return_value={"ok": True, "source": "kraken-cli"})
    router = PaperExecutionRouter(cli=cli, ledger=isolated_ledger, prefer_local=True)
    result = await router.paper_order("buy", "BTCUSD", Decimal("0.001"), "market", None)
    assert result["source"] == "local-paper-ledger"
    cli.paper_order.assert_not_called()
