"""CLI entry — run Neo Trade Agent jobs (Fable5 TradeAgent parity).

Usage (from repo root):
  python -m backend.scripts.run_trade_agent status
  python -m backend.scripts.run_trade_agent market
  python -m backend.scripts.run_trade_agent pre-market
  python -m backend.scripts.run_trade_agent label
  python -m backend.scripts.run_trade_agent optimize
  python -m backend.scripts.run_trade_agent positions
  python -m backend.scripts.run_trade_agent background
"""

from __future__ import annotations

import asyncio
import json
import sys


async def _main(argv: list[str]) -> int:
    from backend.app.trading.trade_agent import jobs, trade_agent
    from backend.app.settings import get_settings

    cmd = (argv[1] if len(argv) > 1 else "status").lower().replace("_", "-")
    settings = get_settings()

    if cmd in {"status", "check-status"}:
        result = await jobs.check_status_snapshot()
    elif cmd in {"positions", "check-positions"}:
        result = await jobs.check_positions_snapshot()
    elif cmd in {"market", "market-hours", "scan"}:
        result = await jobs.run_market_scan(reason="cli:market", settings=settings)
    elif cmd in {"pre-market", "premarket"}:
        result = await jobs.run_market_scan(reason="cli:pre-market", settings=settings)
    elif cmd in {"label", "label-trades"}:
        result = await jobs.run_label_trades()
    elif cmd in {"optimize", "optimizer"}:
        result = await jobs.run_optimizer()
    elif cmd in {"background", "daemon", "schedule"}:
        started = await trade_agent.start(settings)
        print(json.dumps(started, indent=2, default=str))
        print("Trade agent running — Ctrl+C to stop", flush=True)
        try:
            while trade_agent.running:
                await asyncio.sleep(5)
        except KeyboardInterrupt:
            pass
        result = await trade_agent.stop()
    else:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        print(__doc__, file=sys.stderr)
        return 2

    print(json.dumps(result, indent=2, default=str))
    return 0 if result.get("ok", True) or result.get("stopped") or result.get("started") else 1


def main() -> None:
    raise SystemExit(asyncio.run(_main(sys.argv)))


if __name__ == "__main__":
    main()
