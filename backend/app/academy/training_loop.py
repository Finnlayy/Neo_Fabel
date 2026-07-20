"""Night/idle training orchestrator (no live orders; no vectorbt policy)."""

from __future__ import annotations

import asyncio
import random
from datetime import datetime
from typing import Any

from backend.app.academy.academy_curriculum import academy_curriculum
from backend.app.academy.agent_defs import NEO_AGENT_NAMES
from backend.app.academy.agent_registry import agent_registry
from backend.app.academy.chronos_drills import chronos_auto_decision
from backend.app.academy.drill_market import resolve_academy_source
from backend.app.academy.drill_scenarios import resolve_risk_policy_expected
from backend.app.academy.prompt_shot_optimizer import prompt_shot_optimizer
from backend.app.academy.training_drills import training_drills
from backend.app.academy.schemas import DiversityMonitorStats
from backend.app.settings import get_settings


def _auto_decision_for_drill(drill: Any, acc: float) -> str:
    """Pick a training-loop decision without random binary flips for multi-outcome types."""
    expected = str(drill.expected_outcome)
    actions = drill.scenario_data.get("actions")
    allowed = [str(a).upper() for a in actions] if isinstance(actions, list) and actions else []

    if drill.scout_target == "chronos" or drill.drill_type == "kline_language":
        model_vote = chronos_auto_decision(drill.scenario_data)
        if model_vote and random.random() < max(acc, 0.55):
            return str(model_vote)
        if random.random() < acc:
            return expected
        alts = [a for a in (allowed or ["PROCEED", "REJECT", "CHOP"]) if a != expected.upper()]
        return random.choice(alts or ["REJECT"])

    if drill.drill_type == "risk_policy":
        if random.random() < acc:
            return expected
        policy = drill.scenario_data.get("policy") or {}
        state = drill.scenario_data.get("state") or {}
        computed = resolve_risk_policy_expected(policy, state)
        if computed != expected.upper() and random.random() < 0.5:
            return computed
        alts = [a for a in (allowed or ["ALLOW_PAPER", "BLOCK"]) if a != expected.upper()]
        return random.choice(alts or ["BLOCK"])

    if random.random() < acc:
        return expected
    if allowed:
        alts = [a for a in allowed if a != expected.upper()]
        return random.choice(alts or allowed)
    return "PROCEED" if expected.upper() == "REJECT" else "REJECT"

class TrainingLoopService:
    def __init__(self) -> None:
        self.is_running = False
        self.task: asyncio.Task[None] | None = None
        self.diversity_stats = DiversityMonitorStats()
        self.last_run_time: str | None = None
        self.recent_drills: list[dict[str, Any]] = []
        self.cycles_completed = 0
        self.errors_last_5min = 0
        self.last_error: str | None = None
        self.last_skip_reason: str | None = None
        # Session override when Start is pressed in development with TRAINING_LOOP_ENABLED=false.
        self._session_enabled: bool = False

    def _cfg(self) -> Any:
        return get_settings()

    def _loop_allowed(self) -> bool:
        cfg = self._cfg()
        return bool(cfg.training_loop_enabled or self._session_enabled)

    def _parse_minutes(self, value: str, default: int) -> int:
        try:
            hour_raw, minute_raw = value.split(":", 1)
            hour = int(hour_raw)
            minute = int(minute_raw)
            if 0 <= hour <= 23 and 0 <= minute <= 59:
                return hour * 60 + minute
        except (TypeError, ValueError):
            pass
        return default

    def _is_night_time(self) -> bool:
        cfg = self._cfg()
        if not cfg.training_loop_night_mode:
            return True
        now = datetime.now().astimezone()
        now_minutes = now.hour * 60 + now.minute
        start = self._parse_minutes(cfg.training_loop_night_start, 22 * 60)
        end = self._parse_minutes(cfg.training_loop_night_end, 6 * 60)
        if start == end:
            return True
        if start < end:
            return start <= now_minutes < end
        return now_minutes >= start or now_minutes < end

    def _sleep_seconds(self) -> float:
        drills_per_hour = max(float(self._cfg().training_loop_drills_per_hour or 12.0), 1.0)
        return max(60.0, 3600.0 / drills_per_hour)

    async def start(self) -> dict[str, Any]:
        cfg = self._cfg()
        if not cfg.training_loop_enabled:
            # Local/dev: allow Start without editing env; production still requires the flag.
            if (cfg.app_env or "").lower() == "development":
                self._session_enabled = True
            else:
                self.last_skip_reason = "TRAINING_LOOP_DISABLED"
                return {
                    "started": False,
                    "reason": self.last_skip_reason,
                    "hint": "Set TRAINING_LOOP_ENABLED=true in .env.local and restart the API.",
                }
        if self.is_running:
            return {"started": False, "reason": "ALREADY_RUNNING"}

        self.is_running = True
        self.last_skip_reason = None
        try:
            await self._run_cycle()
        except Exception as exc:  # noqa: BLE001
            self.is_running = False
            self.last_error = str(exc)
            self.last_skip_reason = "CYCLE_FAILED"
            return {"started": False, "reason": "CYCLE_FAILED", "error": str(exc)}
        self.task = asyncio.create_task(self._loop_routine())
        return {
            "started": True,
            "reason": None,
            "session_enabled": self._session_enabled and not cfg.training_loop_enabled,
            "night_mode": cfg.training_loop_night_mode,
            "is_night_time": self._is_night_time(),
        }

    async def stop(self) -> None:
        task = self.task
        self.is_running = False
        self._session_enabled = False
        self.task = None
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    def stop_now(self) -> None:
        self.is_running = False
        self._session_enabled = False
        if self.task and not self.task.done():
            self.task.cancel()
        self.task = None

    async def trigger_manual_cycle(self) -> None:
        await self._run_cycle()

    async def _loop_routine(self) -> None:
        while self.is_running:
            try:
                await asyncio.sleep(self._sleep_seconds())
                if self._is_night_time():
                    await self._run_cycle()
                    self.last_skip_reason = None
                else:
                    self.last_skip_reason = "WAITING_FOR_NIGHT_WINDOW"
            except asyncio.CancelledError:
                break
            except Exception as exc:  # noqa: BLE001
                self.errors_last_5min += 1
                self.last_error = str(exc)
                await asyncio.sleep(60)

    async def _run_cycle(self) -> None:
        self.last_run_time = datetime.now().astimezone().isoformat()
        decisions: list[str] = []
        cycle_results = []

        for scout in NEO_AGENT_NAMES:
            difficulty = random.randint(1, 3)
            drill = training_drills.generate_random_drill(scout, difficulty=difficulty)
            identity = agent_registry.get_identity(scout)
            acc = identity.accuracy if identity and identity.accuracy > 0 else 0.5

            scout_decision = _auto_decision_for_drill(drill, acc)
            decisions.append(scout_decision)

            # Batch drill_results.jsonl at end of cycle, but append careers immediately
            # so POST /train/cycle satisfies the V1 disk contract for agent_careers.jsonl.
            result = await training_drills.evaluate_drill(
                drill,
                scout_decision,
                confidence=random.uniform(0.5, 0.99),
                persist=False,
                save_registry=False,
                write_log=True,
            )
            cycle_results.append(result)
            academy_curriculum.record_drill_result(
                scout, "Beginner", result.is_correct, result.confidence, save=False
            )
            await self._check_auto_evolution(scout)

            drill_log = result.model_dump()
            drill_log["drill_type"] = drill.drill_type
            drill_log["difficulty"] = drill.difficulty
            self.recent_drills.insert(0, drill_log)
            if len(self.recent_drills) > 50:
                self.recent_drills.pop()

        self._update_diversity(decisions)
        await training_drills.write_results(cycle_results)
        agent_registry.save_registry()
        academy_curriculum.save_progress()
        self.cycles_completed += 1

    async def _check_auto_evolution(self, scout_name: str) -> None:
        # Optimizer-driven evolution from careers/drills/prompt-shot logs (not random stub).
        # Never raise — a failed evolution must not abort the remaining scout drills.
        try:
            del scout_name
            prompt_shot_optimizer.analyze_and_maybe_evolve("orchestrator")
        except Exception as exc:  # noqa: BLE001
            self.last_error = f"prompt_shot_optimizer: {exc}"

    def _update_diversity(self, decisions: list[str]) -> None:
        if not decisions:
            return
        proceeds = decisions.count("PROCEED")
        rejects = decisions.count("REJECT")
        agreement = max(proceeds, rejects) / len(decisions)
        if self.diversity_stats.total_evaluations == 0:
            self.diversity_stats.agreement_rate = agreement
        else:
            self.diversity_stats.agreement_rate = (
                self.diversity_stats.agreement_rate * 0.9
            ) + (agreement * 0.1)
        self.diversity_stats.total_evaluations += 1
        if self.diversity_stats.agreement_rate > 0.9:
            self.diversity_stats.high_agreement_warnings += 1
            self.diversity_stats.status = "echo_chamber"
        elif self.diversity_stats.agreement_rate < 0.5:
            self.diversity_stats.low_agreement_warnings += 1
            self.diversity_stats.status = "divergent"
        else:
            self.diversity_stats.status = "optimal"

    def get_status(self) -> dict[str, Any]:
        cfg = self._cfg()
        enabled = self._loop_allowed()
        return {
            "is_running": self.is_running,
            "auto_start_enabled": cfg.training_loop_auto_start,
            "enabled": enabled,
            "env_enabled": bool(cfg.training_loop_enabled),
            "session_enabled": self._session_enabled,
            "night_mode": cfg.training_loop_night_mode,
            "is_night_time": self._is_night_time(),
            "last_run_time": self.last_run_time,
            "cycles_completed": self.cycles_completed,
            "next_interval_seconds": self._sleep_seconds(),
            "last_skip_reason": self.last_skip_reason,
            "last_error": self.last_error,
            "errors_last_5min": self.errors_last_5min,
            "recent_drills": self.recent_drills,
            "diversity": self.diversity_stats.model_dump(),
            "agents": list(NEO_AGENT_NAMES),
            "paper_only": True,
            "drill_market_source": resolve_academy_source(cfg),
            "academy_drill_live_data": bool(cfg.academy_drill_live_data),
            "hint": (
                None
                if enabled
                else "Set TRAINING_LOOP_ENABLED=true in .env.local (or Start in development to session-enable)."
            ),
        }


training_loop = TrainingLoopService()
