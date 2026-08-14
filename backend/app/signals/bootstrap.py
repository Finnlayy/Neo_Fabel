"""Idempotent startup seeding for Fable Engine signal routes."""

from __future__ import annotations

import logging
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.app.settings import Settings
from backend.app.signals.repository import SignalRepository, new_route

logger = logging.getLogger("neo_fabel.signals.bootstrap")

# Shared route keys — per-pair engine strategy_ids (fable_grid_btcusd, …) map here.
FABLE_STRATEGIES: tuple[tuple[str, str], ...] = (
    ("fable_grid_opportunity", "Fable Grid Opportunities (auto)"),
    ("fable_dca_default", "Fable DCA (auto)"),
)

DEV_OWNER_UID = "local-dev"


def _paper_pair_allowlist(settings: Settings) -> str:
    if getattr(settings, "paper_allow_all_pairs", True):
        return "*"
    pairs = ",".join(
        p.strip().upper().replace("/", "").replace("-", "")
        for p in settings.kraken_pair_allowlist.split(",")
        if p.strip()
    )
    return pairs or "ADAUSD,XRPUSD,ADAEUR,XRPEUR"


async def ensure_fable_routes(
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> None:
    """Create enabled bypass routes for default Fable strategies when missing."""
    if not settings.fable_engine_enabled or not settings.signal_routes_enabled:
        return

    pairs = _paper_pair_allowlist(settings)

    async with session_factory() as session:
        repo = SignalRepository(session)
        created = 0
        updated = 0
        for strategy_id, name in FABLE_STRATEGIES:
            existing = await repo.find_enabled_route_by_strategy(strategy_id)
            if existing is not None:
                if (
                    getattr(settings, "paper_allow_all_pairs", True)
                    and existing.pair_allowlist.strip() != "*"
                ):
                    existing.pair_allowlist = "*"
                    existing.version = int(existing.version or 1) + 1
                    updated += 1
                    logger.info(
                        "updated fable route allowlist strategy_id=%s route_id=%s -> *",
                        strategy_id,
                        existing.id,
                    )
                continue
            route = new_route(
                owner_uid=DEV_OWNER_UID,
                name=name,
                strategy_id=strategy_id,
                pair_allowlist=pairs,
                max_volume=Decimal("1"),
                max_notional=Decimal("100000"),
                allowed_order_types="market,limit",
                max_event_age_seconds=settings.signal_max_age_seconds,
                max_rate_per_minute=60,
                max_backlog=500,
                policy_version=settings.signal_policy_version,
            )
            route.mode = "bypass_ai"
            route.enabled = True
            await repo.create_route(route)
            created += 1
            logger.info("bootstrapped fable route strategy_id=%s route_id=%s", strategy_id, route.id)
        if created or updated:
            await session.commit()
