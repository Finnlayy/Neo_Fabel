"""Local paper ledger + router fallback (Phase 3)."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from backend.app.integrations.kraken_cli import KrakenCliError
from backend.app.integrations.local_paper import LocalPaperLedger
from backend.app.integrations.paper_router import PaperExecutionRouter


@pytest.mark.asyncio
async def test_local_ledger_accepts_market_order() -> None:
    ledger = LocalPaperLedger()
    result = await ledger.paper_order("buy", "BTC/USD", Decimal("0.001"), "market", None)
    assert result["ok"] is True
    assert result["source"] == "local-paper-ledger"
    status = await ledger.paper_status()
    assert len(status["orders"]) == 1
    assert status["orders"][0]["pair"] == "BTCUSD"


@pytest.mark.asyncio
async def test_router_falls_back_when_cli_missing() -> None:
    cli = AsyncMock()
    cli.paper_order = AsyncMock(side_effect=KrakenCliError("config", "kraken executable is not installed"))
    cli.paper_status = AsyncMock(side_effect=KrakenCliError("config", "kraken executable is not installed"))
    router = PaperExecutionRouter(cli=cli, ledger=LocalPaperLedger())
    result = await router.paper_order("buy", "ETHUSD", Decimal("0.01"), "market", None)
    assert result["source"] == "local-paper-ledger"
    status = await router.paper_status()
    assert status["source"] == "local-paper-ledger"
