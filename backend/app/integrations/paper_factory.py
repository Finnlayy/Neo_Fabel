"""Shared paper execution router factory (API + signal worker)."""

from __future__ import annotations

from decimal import Decimal

from backend.app.integrations.kraken_cli import KrakenCli
from backend.app.integrations.kraken_futures_public import KrakenFuturesPublicClient
from backend.app.integrations.kraken_public import KrakenPublicClient
from backend.app.integrations.local_paper import get_local_paper_ledger
from backend.app.integrations.paper_router import PaperExecutionRouter
from backend.app.market.instruments import MarketType, resolve_instrument
from backend.app.settings import Settings


def build_kraken_cli(settings: Settings) -> KrakenCli:
    return KrakenCli(
        binary=settings.kraken_binary,
        timeout_seconds=settings.kraken_timeout_seconds,
        allow_trade_commands=settings.trade_commands_enabled,
        api_key=settings.kraken_api_key,
        api_secret=settings.kraken_api_secret,
    )


async def _spot_ticker_price(symbol: str, *, public: KrakenPublicClient) -> Decimal:
    data = await public.ticker(symbol)
    last = data.get("last") or data.get("price") or data.get("close")
    if isinstance(last, list) and last:
        last = last[0]
    price = Decimal(str(last))
    if price <= 0:
        raise ValueError(f"no spot ticker price for {symbol}")
    return price


async def _futures_ticker_price(symbol: str, *, futures: KrakenFuturesPublicClient) -> Decimal:
    return await futures.last_price(symbol)


def build_paper_router(settings: Settings) -> PaperExecutionRouter:
    """Local ledger with spot/futures price resolvers — CLI optional fallback."""
    ledger = get_local_paper_ledger(
        starting_balance_usd=settings.paper_starting_balance_usd,
        starting_margin_usd=settings.paper_futures_starting_margin_usd,
        maker_fee_rate=settings.paper_maker_fee_rate,
        taker_fee_rate=settings.paper_taker_fee_rate,
        max_open_positions=settings.paper_max_open_positions,
    )

    spot_public = KrakenPublicClient(timeout_seconds=settings.kraken_timeout_seconds)
    futures_public = KrakenFuturesPublicClient(timeout_seconds=settings.kraken_timeout_seconds)

    async def _resolve_price(market_type: MarketType, pair: str) -> Decimal:
        inst = resolve_instrument(market_type, pair)
        if inst.market_type == "futures":
            return await _futures_ticker_price(inst.symbol, futures=futures_public)
        return await _spot_ticker_price(inst.symbol, public=spot_public)

    ledger.set_price_resolver(_resolve_price)
    cli = build_kraken_cli(settings)
    return PaperExecutionRouter(cli=cli, ledger=ledger, prefer_local=settings.paper_local_ledger)
