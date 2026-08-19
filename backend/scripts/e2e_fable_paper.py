"""End-to-end: fable intake -> worker -> local paper ledger (one shot)."""

from __future__ import annotations

import asyncio

from sqlalchemy import text

from backend.app.database import SessionFactory
from backend.app.integrations.ai_evaluator import build_evaluator
from backend.app.integrations.local_paper import get_local_paper_ledger
from backend.app.integrations.paper_factory import build_paper_router
from backend.app.paper_orders import PaperOrderService
from backend.app.settings import get_settings
from backend.app.signals.engine.generator import FableEngine
from backend.app.signals.executor import PaperOrderExecutionAdapter
from backend.app.signals.worker import SignalWorker


async def _fill_count() -> int:
    state = get_local_paper_ledger().snapshot_state()
    spot = len((state.get("spot") or {}).get("fills") or [])
    fut = len((state.get("futures") or {}).get("fills") or [])
    return spot + fut


async def main() -> None:
    settings = get_settings()
    print("dry_run=", settings.fable_engine_dry_run, "exec=", settings.signal_execution_enabled)

    before = await _fill_count()
    print("ledger_fills_before=", before)

    engine = FableEngine(settings=settings, session_factory=SessionFactory)
    intents = await engine.poll_once()
    print("engine_intents=", len(intents))

    router = build_paper_router(settings)
    worker = SignalWorker(
        settings=settings,
        session_factory=SessionFactory,
        executor=PaperOrderExecutionAdapter(service=PaperOrderService(sink=router)),
        evaluator=build_evaluator(settings),
    )

    processed = 0
    for _ in range(15):
        if not await worker.poll_once():
            break
        processed += 1

    after = await _fill_count()
    print("worker_jobs_processed=", processed)
    print("ledger_fills_after=", after, "delta=", after - before)

    async with SessionFactory() as session:
        rows = (
            await session.execute(
                text(
                    "SELECT status, COUNT(id) FROM signal_events "
                    "WHERE source = 'fable_engine' GROUP BY status ORDER BY COUNT(id) DESC"
                )
            )
        ).all()
        print("fable_status_counts=", rows)

        recent = (
            await session.execute(
                text(
                    "SELECT status, strategy_id, created_at FROM signal_events "
                    "WHERE source = 'fable_engine' ORDER BY created_at DESC LIMIT 5"
                )
            )
        ).all()
        print("recent=", recent)


if __name__ == "__main__":
    asyncio.run(main())
