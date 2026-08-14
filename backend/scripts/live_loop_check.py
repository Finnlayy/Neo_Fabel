"""One-shot diagnostic for autonomous paper loop."""

from __future__ import annotations

import asyncio
import json

from sqlalchemy import text

from backend.app.database import SessionFactory
from backend.app.integrations.paper_paths import ledger_path
from backend.app.settings import get_settings


async def main() -> None:
    settings = get_settings()
    print("settings.fable_engine_dry_run =", settings.fable_engine_dry_run)
    print("settings.signal_execution_enabled =", settings.signal_execution_enabled)
    print("settings.paper_local_ledger =", settings.paper_local_ledger)

    async with SessionFactory() as session:
        routes = (
            await session.execute(
                text(
                    "SELECT strategy_id, enabled, mode, owner_user_uid "
                    "FROM signal_routes ORDER BY created_at"
                )
            )
        ).all()
        print("routes:", routes)

        fable = (
            await session.execute(
                text(
                    "SELECT status, COUNT(id) AS n FROM signal_events "
                    "WHERE source = 'fable_engine' GROUP BY status ORDER BY n DESC"
                )
            )
        ).all()
        print("fable_events_by_status:", fable)

        recent = (
            await session.execute(
                text(
                    "SELECT id, status, strategy_id, pair, side, volume, created_at "
                    "FROM signal_events WHERE source = 'fable_engine' "
                    "ORDER BY created_at DESC LIMIT 8"
                )
            )
        ).all()
        print("recent_fable_events:")
        for row in recent:
            print(" ", row)

        last5 = (
            await session.execute(
                text(
                    "SELECT status, COUNT(id) AS n FROM signal_events "
                    "WHERE source = 'fable_engine' "
                    "AND created_at > (NOW() AT TIME ZONE 'utc') - INTERVAL '10 minutes' "
                    "GROUP BY status ORDER BY n DESC"
                )
            )
        ).all()
        print("fable_last_10min:", last5)

        paper_ok = (
            await session.execute(
                text(
                    "SELECT COUNT(id) FROM signal_events "
                    "WHERE source = 'fable_engine' AND status = 'paper_accepted'"
                )
            )
        ).scalar()
        print("paper_accepted_total:", paper_ok)

    path = ledger_path()
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        spot_fills = len((data.get("spot") or {}).get("fills") or [])
        fut_fills = len((data.get("futures") or {}).get("fills") or [])
        print("ledger:", path, "version=", data.get("version"), "spot_fills=", spot_fills, "fut_fills=", fut_fills)
    else:
        print("ledger: missing", path)


if __name__ == "__main__":
    asyncio.run(main())
