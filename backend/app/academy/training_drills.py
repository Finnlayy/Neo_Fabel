"""Synthetic drills + evaluation (paper/training only)."""

from __future__ import annotations

import asyncio
import random
from typing import Any

from backend.app.academy.agent_defs import get_agent_definition
from backend.app.academy.agent_registry import agent_registry
from backend.app.academy.blind_patterns import make_pattern_scenario
from backend.app.academy.chronos_drills import make_chronos_scenario
from backend.app.academy.paths import ACADEMY_DATA_DIR, ensure_academy_data_dir
from backend.app.academy.schemas import CareerEntry, DrillResult, SyntheticDrill

DRILL_RESULTS_FILE = ACADEMY_DATA_DIR / "drill_results.jsonl"

# Compact teamwork scenarios — packets + skill routing + shot grading.
_TEAMWORK_SCENARIOS: tuple[dict[str, Any], ...] = (
    {
        "expected": "HANDOFF",
        "context": "Depth online; RNA engulfing geometry; risk compliance ON; await paper fill.",
        "packets": [
            {"id": "market_data", "status": "ACTIVE", "lastAction": "BTCUSD depth ok"},
            {"id": "rna_smart", "status": "ACTIVE", "lastAction": "bullish engulfing geometry"},
            {"id": "risk_gov", "status": "ACTIVE", "lastAction": "session DD 0.4%"},
        ],
        "skill_hint": "kraken-paper-strategy",
        "routing": "DELEGATE",
        "prompt_shot_id": "swarm_handoff",
    },
    {
        "expected": "CONCLUSION",
        "context": "User wants paper DCA validation before any live capital.",
        "packets": [
            {"id": "adaptive", "status": "ACTIVE", "lastAction": "size 0.5% equity slices"},
            {"id": "analytic", "status": "STANDBY", "lastAction": "await paper fills"},
        ],
        "skill_hint": "kraken-paper-strategy",
        "routing": "DELEGATE",
        "prompt_shot_id": "kraken_paper_delegate",
    },
    {
        "expected": "BLOCKED",
        "context": "User asks withdrawal to cold storage + live autonomy L4.",
        "packets": [
            {"id": "risk_gov", "status": "ALERT", "lastAction": "live gate requested"},
            {"id": "kraken_broker", "status": "STANDBY", "lastAction": "no paper path"},
        ],
        "skill_hint": "recipe-withdrawal-to-cold-storage",
        "routing": "REFUSE",
        "prompt_shot_id": "kraken_live_refuse",
    },
    {
        "expected": "QUESTION",
        "context": "Risk cleared but symbol allowlist missing for paper route.",
        "packets": [
            {"id": "risk_gov", "status": "ACTIVE", "lastAction": "paper path clear"},
            {"id": "kraken_broker", "status": "STANDBY", "lastAction": "await symbol"},
        ],
        "skill_hint": "kraken-multi-pair",
        "routing": "DELEGATE",
        "prompt_shot_id": "swarm_handoff",
    },
    {
        "expected": "HANDOFF",
        "context": "Chronos coarse tokens bullish; RNA geometry agrees; paper path only.",
        "packets": [
            {"id": "chronos", "status": "ACTIVE", "lastAction": "coarse s1 trend PROCEED bias"},
            {"id": "rna_smart", "status": "ACTIVE", "lastAction": "bullish engulfing geometry"},
            {"id": "risk_gov", "status": "ACTIVE", "lastAction": "session DD 0.3%"},
        ],
        "skill_hint": "kraken-paper-strategy",
        "routing": "DELEGATE",
        "prompt_shot_id": "swarm_handoff",
    },
)


class TrainingDrillsService:
    def generate_random_drill(self, scout_name: str, difficulty: int = 1) -> SyntheticDrill:
        definition = get_agent_definition(scout_name)
        drill_type = definition.drill_type if definition else "pattern_recognition"

        if drill_type == "pattern_recognition":
            bias = random.choice(["bullish", "bearish", "neutral"])
            candles, expected_outcome = make_pattern_scenario(bias)  # type: ignore[arg-type]
            scenario_data = {
                "mode": "blind_geometry",
                "candles": candles,
                "context": f"Blind pattern drill difficulty {difficulty} — no symbol/TF/price",
                "hint_bias": bias,
            }
        elif drill_type == "kline_language" or scout_name == "chronos":
            scenario_data, expected_outcome = make_chronos_scenario(difficulty)
            drill_type = "kline_language"
        else:
            expected_outcome = random.choice(["PROCEED", "REJECT"])
            scenario_data = {
                "mode": "synthetic",
                "context": f"Simulated {drill_type} scenario for difficulty {difficulty}",
            }
            if drill_type == "crisis_detection":
                scenario_data["crisis_score"] = 80 if expected_outcome == "REJECT" else 20
            elif drill_type == "sentiment_analysis":
                scenario_data["headline"] = (
                    "Risk-off headlines dominate"
                    if expected_outcome == "REJECT"
                    else "Risk appetite improves on constructive flows"
                )
            elif drill_type == "regime_identification":
                scenario_data["regime"] = "trend" if expected_outcome == "PROCEED" else "chop"
            elif drill_type == "execution_quality":
                # Paper-only execution quality — never implies a live Kraken fill.
                scenario_data["venue"] = "kraken_broker"
                scenario_data["slippage_bps"] = 35 if expected_outcome == "REJECT" else 4
                scenario_data["fill_ratio"] = 0.42 if expected_outcome == "REJECT" else 0.98
                scenario_data["context"] = (
                    f"Kraken broker execution drill (paper) · slippage "
                    f"{scenario_data['slippage_bps']} bps · fill ratio {scenario_data['fill_ratio']}"
                )
            elif drill_type == "orchestration_teamwork":
                scenario = random.choice(_TEAMWORK_SCENARIOS)
                expected_outcome = scenario["expected"]
                scenario_data = {
                    "mode": "teamwork",
                    "context": scenario["context"],
                    "packets": scenario["packets"],
                    "skill_hint": scenario.get("skill_hint"),
                    "routing": scenario.get("routing"),
                    "prompt_shot_id": scenario.get("prompt_shot_id"),
                }

        return SyntheticDrill(
            drill_type=drill_type,
            scout_target=scout_name,
            scenario_data=scenario_data,
            expected_outcome=expected_outcome,
            difficulty=difficulty,
        )

    def generate_drills(self, scout_name: str, count: int = 5) -> list[SyntheticDrill]:
        return [
            self.generate_random_drill(scout_name, difficulty=random.randint(1, 3))
            for _ in range(count)
        ]

    async def evaluate_drill(
        self,
        drill: SyntheticDrill,
        scout_decision: str,
        confidence: float,
        *,
        persist: bool = True,
        save_registry: bool = True,
        write_log: bool | None = None,
    ) -> DrillResult:
        """Evaluate a drill.

        persist: append DrillResult to drill_results.jsonl
        write_log: append CareerEntry to agent_careers.jsonl (defaults to persist)
        """
        is_correct = scout_decision.upper() == str(drill.expected_outcome).upper()
        result = DrillResult(
            drill_id=drill.drill_id,
            scout_name=drill.scout_target,
            scout_decision=scout_decision,
            is_correct=is_correct,
            confidence=confidence,
            feedback_notes=f"Expected {drill.expected_outcome}, got {scout_decision}.",
        )

        try:
            from backend.app.academy.agency_roster import sync_identity_progress

            sync_identity_progress(
                drill.scout_target, is_correct=is_correct, confidence=float(confidence)
            )
        except Exception:  # noqa: BLE001
            pass

        await agent_registry.log_career_event(
            CareerEntry(
                scout_name=drill.scout_target,
                event_type="prediction_result",
                details={
                    "mode": drill.scenario_data.get("mode", "synthetic"),
                    "is_correct": is_correct,
                    "drill_type": drill.drill_type,
                    "drill_id": drill.drill_id,
                },
            ),
            save_registry=save_registry,
            write_log=persist if write_log is None else write_log,
        )

        if drill.drill_type == "orchestration_teamwork":
            try:
                from backend.app.academy.prompt_shot_log import append_prompt_shot_event

                skill_hint = str(drill.scenario_data.get("skill_hint") or "")
                routing = str(drill.scenario_data.get("routing") or "").upper()
                live_skill = "withdrawal" in skill_hint or "cold-storage" in skill_hint
                if not is_correct:
                    routing_ok = False
                elif live_skill:
                    routing_ok = routing == "REFUSE"
                else:
                    routing_ok = True
                append_prompt_shot_event(
                    {
                        "channel": "drill",
                        "shot_ids": [str(drill.scenario_data.get("prompt_shot_id") or "")],
                        "drill_type": drill.drill_type,
                        "is_correct": is_correct,
                        "skill_hints": [skill_hint] if skill_hint else [],
                        "skill_routing_ok": routing_ok,
                        "outcome": str(drill.expected_outcome),
                        "roster": drill.scenario_data.get("packets") or [],
                    }
                )
            except Exception:  # noqa: BLE001 — logging must not fail drill scoring
                pass

        if persist:
            await self.write_results([result])
        return result

    async def write_results(self, results: list[DrillResult]) -> None:
        if not results:
            return
        ensure_academy_data_dir()

        def _write() -> None:
            with open(DRILL_RESULTS_FILE, "a", encoding="utf-8") as handle:
                for result in results:
                    handle.write(result.model_dump_json() + "\n")

        await asyncio.to_thread(_write)


training_drills = TrainingDrillsService()
