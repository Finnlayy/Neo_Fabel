"""Run: python -m backend.app.signals"""

from __future__ import annotations

import asyncio
import logging

from ..database import SessionFactory
from ..integrations.ai_evaluator import build_evaluator
from ..integrations.kraken_cli import KrakenCli
from ..paper_orders import PaperOrderService
from ..settings import get_settings
from .executor import PaperOrderExecutionAdapter
from .safety import assert_signal_paper_only, assert_signals_module_imports
from .worker import SignalWorker


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    settings = get_settings()
    assert_signals_module_imports()
    assert_signal_paper_only(settings)
    if not settings.signal_worker_enabled:
        raise SystemExit("SIGNAL_WORKER_ENABLED must be true to start the signal worker")

    cli = KrakenCli(
        binary=settings.kraken_binary,
        timeout_seconds=settings.kraken_timeout_seconds,
        allow_trade_commands=False,
    )
    executor = PaperOrderExecutionAdapter(service=PaperOrderService(sink=cli))
    # Evaluator is composed but Bypass never calls it.
    _ = build_evaluator(settings)
    worker = SignalWorker(
        settings=settings,
        session_factory=SessionFactory,
        executor=executor,
        evaluator=build_evaluator(settings),
    )
    asyncio.run(worker.run_forever())


if __name__ == "__main__":
    main()
