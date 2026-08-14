"""Error / feedback engine — idle-market coach for agents + light param adapts.

Runs when the market is quiet and Neo is paper-only (or engine idle).
Consumes dry-runs, last_error, and labeled fills; writes career feedback and
optionally nudges FableEngine poll / risk knobs on acute streaks.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from backend.app.academy.agent_registry import agent_registry
from backend.app.academy.prompt_shot_optimizer import prompt_shot_optimizer
from backend.app.academy.schemas import CareerEntry
from backend.app.settings import Settings, get_settings
from backend.app.trading.feedback.rationale import rationale_from_fill_row

logger = logging.getLogger("neo_fabel.feedback_engine")

FEEDBACK_DIR = Path(__file__).resolve().parents[3] / "data" / "trade_agent" / "feedback"


class FeedbackEngine:
    def __init__(self) -> None:
        self._last_run: dict[str, Any] | None = None
        self._error_streak = 0
        self._loss_streak = 0

    @property
    def last_run(self) -> dict[str, Any] | None:
        return self._last_run

    def is_idle_or_paper_quiet(self, settings: Settings | None = None) -> dict[str, Any]:
        """Gate: paper-only / engine idle / no live algo — suitable for feedback."""
        cfg = settings or get_settings()
        from backend.app.signals.engine.generator import get_fable_engine
        from backend.app.trading.loops import trading_loops

        loops = trading_loops.status(cfg)
        live_on = bool(loops.get("live", {}).get("running"))
        paper_on = bool(loops.get("paper", {}).get("running"))
        eng = get_fable_engine()
        eng_status = eng.status() if eng is not None else None
        ticks = int((eng_status or {}).get("ticks") or 0)
        dry_count = int((eng_status or {}).get("dry_run_count") or 0)
        last_error = (eng_status or {}).get("last_error") or loops.get("paper", {}).get("last_error")

        # Quiet if: live algo off AND (paper off OR engine has no fresh errors OR few recent intents)
        paper_only = not live_on and not bool(cfg.kraken_live_trading_enabled and cfg.kraken_live_algo_enabled)
        engine_idle = eng is None or not (eng_status or {}).get("started")
        acute = bool(last_error) or self._error_streak >= 2 or self._loss_streak >= 3

        allow = (paper_only or engine_idle or paper_on) and (not live_on)
        return {
            "allow": allow,
            "paper_only": paper_only,
            "paper_on": paper_on,
            "live_on": live_on,
            "engine_idle": engine_idle,
            "acute": acute,
            "ticks": ticks,
            "dry_run_count": dry_count,
            "last_error": last_error,
        }

    async def run_cycle(
        self,
        *,
        reason: str = "idle",
        force: bool = False,
        settings: Settings | None = None,
    ) -> dict[str, Any]:
        cfg = settings or get_settings()
        if not cfg.feedback_engine_enabled and not force:
            return {"ok": False, "skipped": True, "reason": "FEEDBACK_ENGINE_ENABLED=false"}

        gate = self.is_idle_or_paper_quiet(cfg)
        if not gate["allow"] and not force and not gate["acute"]:
            return {"ok": False, "skipped": True, "reason": "not_idle", "gate": gate}

        from backend.app.signals.engine.generator import get_fable_engine

        eng = get_fable_engine()
        dry_runs = eng.recent_dry_runs(40) if eng is not None else []
        last_error = gate.get("last_error")

        labeled = self._read_recent_labels(limit=40)
        losses = [r for r in labeled if r.get("label") == "loss"]
        wins = [r for r in labeled if r.get("label") == "win"]

        if last_error:
            self._error_streak += 1
        else:
            self._error_streak = 0
        if losses and (not wins or len(losses) > len(wins)):
            self._loss_streak = min(10, self._loss_streak + 1)
        elif wins:
            self._loss_streak = max(0, self._loss_streak - 1)

        notes = self._build_notes(dry_runs, labeled, last_error)
        packets = self._agent_packets(notes, gate)

        # Career feedback for orchestrator + risk + adaptive
        for scout, detail in (
            ("orchestrator", {"role": "coordinator", "notes": notes[:5], "gate": gate}),
            ("risk_gov", {"role": "risk", "error_streak": self._error_streak, "loss_streak": self._loss_streak}),
            ("adaptive", {"role": "param_adapt", "suggested": self._suggest_params(gate)}),
            ("analytic", {"role": "pnl_synth", "wins": len(wins), "losses": len(losses)}),
        ):
            await agent_registry.log_career_event(
                CareerEntry(
                    scout_name=scout,
                    event_type="trade_feedback",
                    details={
                        "reason": reason,
                        "is_correct": self._loss_streak < 3 and self._error_streak < 2,
                        "feedback": "; ".join(notes[:3]) if notes else "healthy",
                        **detail,
                    },
                )
            )

        evolved = prompt_shot_optimizer.analyze_and_maybe_evolve("orchestrator")
        adapts = self._apply_acute_adapts(eng, gate)

        FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        out = FEEDBACK_DIR / f"feedback_{stamp}.json"
        payload = {
            "ok": True,
            "at": datetime.now(UTC).isoformat(),
            "reason": reason,
            "gate": gate,
            "notes": notes,
            "packets": packets,
            "dry_runs_reviewed": len(dry_runs),
            "labels_reviewed": len(labeled),
            "error_streak": self._error_streak,
            "loss_streak": self._loss_streak,
            "prompt_evolution": evolved,
            "param_adapts": adapts,
        }
        out.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        self._last_run = payload
        logger.info(
            "feedback cycle reason=%s notes=%s adapts=%s",
            reason,
            len(notes),
            adapts,
        )
        return payload

    def _read_recent_labels(self, limit: int = 40) -> list[dict[str, Any]]:
        root = Path(__file__).resolve().parents[3] / "data" / "trade_agent" / "labels"
        if not root.exists():
            return []
        files = sorted(root.glob("labels_*.jsonl"), reverse=True)[:3]
        rows: list[dict[str, Any]] = []
        for path in files:
            try:
                for line in path.read_text(encoding="utf-8").splitlines():
                    if not line.strip():
                        continue
                    rows.append(json.loads(line))
            except (OSError, json.JSONDecodeError):
                continue
        return rows[-limit:]

    def _build_notes(
        self,
        dry_runs: list[dict[str, Any]],
        labeled: list[dict[str, Any]],
        last_error: str | None,
    ) -> list[str]:
        notes: list[str] = []
        if last_error:
            notes.append(f"engine_error: {str(last_error)[:120]}")
        rejects = [r for r in dry_runs if str(r.get("intake") or "").startswith(("rejected", "error"))]
        if rejects:
            notes.append(f"intake_failures={len(rejects)} last={rejects[-1].get('intake')}")
        for r in dry_runs[-5:]:
            rat = r.get("rationale") or r.get("reason")
            if rat:
                notes.append(f"intent: {rat}")
        for row in labeled[-5:]:
            notes.append(f"label {row.get('label')}: {rationale_from_fill_row(row)}")
        if self._loss_streak >= 3:
            notes.append(f"acute_loss_streak={self._loss_streak}")
        if self._error_streak >= 2:
            notes.append(f"acute_error_streak={self._error_streak}")
        return notes[:20]

    def _agent_packets(self, notes: list[str], gate: dict[str, Any]) -> list[dict[str, str]]:
        summary = "; ".join(notes[:2]) if notes else "No acute issues — paper path healthy"
        return [
            {
                "id": "orchestrator",
                "status": "FEEDBACK",
                "lastAction": summary[:200],
                "directive": "Incorporate trade rationales; refuse live_gated; paper-only adapts."[:280],
            },
            {
                "id": "risk_gov",
                "status": "REVIEW" if gate.get("acute") else "OK",
                "lastAction": f"error_streak={self._error_streak} loss_streak={self._loss_streak}"[:200],
                "directive": "Tighten size if loss_streak>=3; clear after quiet wins."[:280],
            },
            {
                "id": "adaptive",
                "status": "PARAM_ADAPT" if gate.get("acute") else "IDLE",
                "lastAction": summary[:200],
                "directive": "Apply poll/risk nudges only on acute streaks; log rationale."[:280],
            },
        ]

    def _suggest_params(self, gate: dict[str, Any]) -> dict[str, Any]:
        suggest: dict[str, Any] = {}
        if self._error_streak >= 2:
            suggest["poll_seconds_delta"] = +5.0
        if self._loss_streak >= 3:
            suggest["volume_scale"] = 0.75
        if not suggest:
            suggest["hold"] = True
        suggest["acute"] = bool(gate.get("acute"))
        return suggest

    def _apply_acute_adapts(self, eng: Any, gate: dict[str, Any]) -> list[str]:
        """Light in-process nudges — never flips live trading flags."""
        applied: list[str] = []
        if eng is None or not gate.get("acute"):
            return applied
        try:
            if self._error_streak >= 2:
                old = float(eng.engine.poll_seconds)
                new = min(120.0, old + 5.0)
                if new > old:
                    eng.engine.poll_seconds = new
                    applied.append(f"poll_seconds {old}->{new}")
            if self._loss_streak >= 3:
                from decimal import Decimal

                for strat in getattr(eng, "_strategies", []) or []:
                    cfg = getattr(strat, "config", None)
                    if cfg is None:
                        continue
                    sid = getattr(cfg, "strategy_id", "?")
                    if getattr(cfg, "volume_per_zone", None) is not None:
                        before = cfg.volume_per_zone
                        cfg.volume_per_zone = (before * Decimal("0.75")).quantize(Decimal("0.00000001"))
                        applied.append(f"{sid} volume_per_zone {before}->{cfg.volume_per_zone}")
                    if getattr(cfg, "dca_volume", None) is not None:
                        before = cfg.dca_volume
                        cfg.dca_volume = (before * Decimal("0.75")).quantize(Decimal("0.00000001"))
                        applied.append(f"{sid} dca_volume {before}->{cfg.dca_volume}")
                self._loss_streak = 0  # consume acute once applied
        except Exception as exc:  # noqa: BLE001
            logger.warning("param adapt failed: %s", exc)
            applied.append(f"adapt_error:{exc}")
        return applied


feedback_engine = FeedbackEngine()
