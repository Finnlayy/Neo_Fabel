"""Choose Kraken CLI paper when available; otherwise local ledger."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Literal

from .kraken_cli import KrakenCli, KrakenCliError
from .local_paper import LocalPaperLedger, get_local_paper_ledger


class PaperExecutionRouter:
    """Paper-only sink used by PaperOrderService and /paper/status."""

    def __init__(self, cli: KrakenCli, ledger: LocalPaperLedger | None = None) -> None:
        self.cli = cli
        self.ledger = ledger or get_local_paper_ledger()
        self.last_source = "unknown"

    async def paper_order(
        self,
        side: Literal["buy", "sell"],
        pair: str,
        volume: Decimal,
        order_type: Literal["market", "limit"],
        price: Decimal | None,
    ) -> dict[str, Any]:
        try:
            result = await self.cli.paper_order(side, pair, volume, order_type, price)
            self.last_source = "kraken-cli"
            if isinstance(result, dict):
                result = {**result, "source": "kraken-cli"}
            return result
        except KrakenCliError as exc:
            if exc.category != "config":
                raise
            self.last_source = "local-paper-ledger"
            try:
                return await self.ledger.paper_order(side, pair, volume, order_type, price)
            except ValueError as ledger_exc:
                raise KrakenCliError("validation", str(ledger_exc)) from ledger_exc

    async def paper_status(self) -> dict[str, Any]:
        try:
            data = await self.cli.paper_status()
            self.last_source = "kraken-cli"
            if isinstance(data, dict):
                return {**data, "source": "kraken-cli"}
            return {"raw": data, "source": "kraken-cli"}
        except KrakenCliError as exc:
            if exc.category != "config":
                raise
            self.last_source = "local-paper-ledger"
            return await self.ledger.paper_status()
