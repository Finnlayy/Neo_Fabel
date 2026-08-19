"""Choose Kraken CLI paper when available; otherwise local ledger."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Literal

from backend.app.market.instruments import MarketType

from .kraken_cli import KrakenCli, KrakenCliError
from .local_paper import LocalPaperLedger, get_local_paper_ledger


class PaperExecutionRouter:
    """Paper-only sink used by PaperOrderService and /paper/status."""

    def __init__(
        self,
        cli: KrakenCli,
        ledger: LocalPaperLedger | None = None,
        *,
        prefer_local: bool = False,
    ) -> None:
        self.cli = cli
        self.ledger = ledger or get_local_paper_ledger()
        self.prefer_local = prefer_local
        self.last_source = "unknown"

    async def paper_order(
        self,
        side: Literal["buy", "sell"],
        pair: str,
        volume: Decimal,
        order_type: Literal["market", "limit"],
        price: Decimal | None,
        *,
        market_type: MarketType = "spot",
        leverage: int = 1,
        rationale: str | None = None,
    ) -> dict[str, Any]:
        if self.prefer_local:
            self.last_source = "local-paper-ledger"
            try:
                return await self.ledger.paper_order(
                    side,
                    pair,
                    volume,
                    order_type,
                    price,
                    market_type=market_type,
                    leverage=leverage,
                    rationale=rationale,
                )
            except ValueError as ledger_exc:
                raise KrakenCliError("validation", str(ledger_exc)) from ledger_exc

        # Prefer the Kraken CLI when present, but keep paper trading usable on
        # developer machines where the optional executable is not configured.
        try:
            result = await self.cli.paper_order(side, pair, volume, order_type, price)
        except KrakenCliError as exc:
            # Do not mask operational or execution errors as local paper fills.
            if exc.category != "config":
                raise
            self.last_source = "local-paper-ledger"
            return await self.ledger.paper_order(
                side,
                pair,
                volume,
                order_type,
                price,
                market_type=market_type,
                leverage=leverage,
                rationale=rationale,
            )
        else:
            self.last_source = "kraken-cli"
            if isinstance(result, dict):
                return {**result, "source": "kraken-cli", "market_type": "spot"}
            return result

    async def paper_status(self) -> dict[str, Any]:
        if self.prefer_local:
            self.last_source = "local-paper-ledger"
            return await self.ledger.paper_status()

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

    async def paper_performance(self, mark_prices: dict | None = None) -> dict[str, Any]:
        """Performance metrics — local ledger only (Windows / CLI fallback path)."""
        prices = None
        if mark_prices:
            prices = {str(k): Decimal(str(v)) for k, v in mark_prices.items()}
        return await self.ledger.performance(prices)
