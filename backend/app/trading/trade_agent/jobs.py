"""Job implementations for Neo Trade Agent (paper-safe by default)."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from backend.app.settings import Settings, get_settings

logger = logging.getLogger("neo_fabel.trade_agent.jobs")


def _session_factory() -> Any:
    from backend.app.database import SessionFactory

    return SessionFactory


async def _paper_status() -> dict[str, Any]:
    from backend.app.integrations.kraken_cli import KrakenCli
    from backend.app.integrations.paper_router import PaperExecutionRouter
    from backend.app.settings import get_settings as gs

    settings = gs()
    cli = KrakenCli(settings)
    router = PaperExecutionRouter(cli=cli, prefer_local=bool(settings.paper_local_ledger))
    return await router.paper_status()


async def run_market_scan(*, reason: str = "scheduled", settings: Settings | None = None) -> dict[str, Any]:
    """One paper scan tick via FableEngine (dry-run intents).

    Mirrors TradeAgent `run_scheduled_trading.py` market/pre-market scans.
    """
    cfg = settings or get_settings()
    started = datetime.now(UTC).isoformat()
    from backend.app.signals.engine.generator import get_fable_engine
    from backend.app.trading.loops import trading_loops

    eng = get_fable_engine()
    if eng is None or not eng.status().get("started"):
        start = await trading_loops.start_paper(cfg, _session_factory())
        eng = get_fable_engine()
        if eng is None:
            return {
                "ok": False,
                "job": "market_scan",
                "reason": reason,
                "started_at": started,
                "error": "paper_engine_unavailable",
                "start_result": start,
            }

    intents = await eng.poll_once()
    return {
        "ok": True,
        "job": "market_scan",
        "reason": reason,
        "started_at": started,
        "finished_at": datetime.now(UTC).isoformat(),
        "intent_count": len(intents),
        "engine": eng.status(),
        "mode": "paper_dry_run",
    }


async def run_label_trades(*, lookback_days: int = 14, settings: Settings | None = None) -> dict[str, Any]:
    """Label recent paper ledger rows for ML — TradeAgent `label_trades` schedule."""
    _ = settings or get_settings()
    root = Path(__file__).resolve().parents[3] / "data" / "trade_agent" / "labels"
    root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out = root / f"labels_{stamp}.jsonl"

    try:
        status = await _paper_status()
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "job": "label_trades", "error": str(exc)}

    data = status.get("data") if isinstance(status, dict) and "data" in status else status
    if not isinstance(data, dict):
        data = {}
    trades = data.get("fills") or data.get("orders") or data.get("trades") or []
    if not isinstance(trades, list):
        trades = []

    labeled = 0
    with out.open("w", encoding="utf-8") as fh:
        for row in trades[-200:]:
            if not isinstance(row, dict):
                continue
            pnl = float(row.get("pnl") or row.get("realized_pnl") or row.get("profit") or 0)
            label = "win" if pnl > 0 else "loss" if pnl < 0 else "flat"
            rec = {
                "labeled_at": datetime.now(UTC).isoformat(),
                "lookback_days": lookback_days,
                "label": label,
                "pnl": pnl,
                "symbol": row.get("symbol") or row.get("asset") or row.get("pair"),
                "side": row.get("side") or row.get("type"),
                "source": "paper_ledger",
            }
            fh.write(json.dumps(rec) + "\n")
            labeled += 1

    return {
        "ok": True,
        "job": "label_trades",
        "lookback_days": lookback_days,
        "labeled": labeled,
        "path": str(out),
        "finished_at": datetime.now(UTC).isoformat(),
    }


async def run_optimizer(*, population: int = 8, generations: int = 5) -> dict[str, Any]:
    """Kick a small GA job (TradeAgent adaptive optimizer analogue)."""
    from backend.app.integrations.ga_optimizer.jobs import ga_jobs
    from backend.app.integrations.ga_optimizer.schemas import OptimizeRequest

    req = OptimizeRequest(
        population=population,
        generations=generations,
        max_symbols=2,
        lookback_bars=400,
        symbols=["ETHUSDT"],
        market_source="cache",
        seed=42,
    )
    run = await ga_jobs.start_optimize(req.model_dump())
    return {
        "ok": True,
        "job": "optimizer",
        "run_id": run.get("runId") or run.get("run_id"),
        "status": run.get("status"),
        "finished_at": datetime.now(UTC).isoformat(),
    }


async def check_status_snapshot() -> dict[str, Any]:
    """TradeAgent check_status analogue — Neo loops + paper + AI spend."""
    from backend.app.integrations.llm_router import LlmRouter
    from backend.app.trading.loops import trading_loops

    settings = get_settings()
    loops = trading_loops.status(settings)
    ai = LlmRouter(settings).status_payload()
    try:
        paper = await _paper_status()
    except Exception as exc:  # noqa: BLE001
        paper = {"error": str(exc)}
    return {
        "ok": True,
        "job": "check_status",
        "at": datetime.now(UTC).isoformat(),
        "loops": loops,
        "ai_provider": ai.get("provider"),
        "spend": ai.get("spend"),
        "paper": paper,
    }


async def check_positions_snapshot() -> dict[str, Any]:
    """TradeAgent check_positions analogue — paper ledger open positions."""
    try:
        paper = await _paper_status()
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "job": "check_positions", "error": str(exc)}

    data = paper.get("data") if isinstance(paper, dict) and "data" in paper else paper
    if not isinstance(data, dict):
        data = {}
    spot = data.get("spot") if isinstance(data.get("spot"), dict) else {}
    return {
        "ok": True,
        "job": "check_positions",
        "at": datetime.now(UTC).isoformat(),
        "source": "paper",
        "open_positions": spot.get("open_positions") or data.get("open_positions"),
        "usd_balance": spot.get("usd_balance") or data.get("usd_balance"),
        "orders": len(data.get("orders") or []) if isinstance(data.get("orders"), list) else None,
        "fills": len(data.get("fills") or []) if isinstance(data.get("fills"), list) else None,
    }
