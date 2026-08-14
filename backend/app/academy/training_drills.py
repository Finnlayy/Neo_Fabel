"""Synthetic drills + evaluation (paper/training only)."""

from __future__ import annotations

import asyncio
import random

from backend.app.academy.agent_defs import get_agent_definition
from backend.app.academy.agent_registry import agent_registry
from backend.app.academy.blind_patterns import make_pattern_scenario
from backend.app.academy.paths import ACADEMY_DATA_DIR, ensure_academy_data_dir
from backend.app.academy.schemas import CareerEntry, DrillResult, SyntheticDrill

DRILL_RESULTS_FILE = ACADEMY_DATA_DIR / "drill_results.jsonl"


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
    ) -> DrillResult:
        is_correct = scout_decision.upper() == str(drill.expected_outcome).upper()
        result = DrillResult(
            drill_id=drill.drill_id,
            scout_name=drill.scout_target,
            scout_decision=scout_decision,
            is_correct=is_correct,
            confidence=confidence,
            feedback_notes=f"Expected {drill.expected_outcome}, got {scout_decision}.",
        )

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
            write_log=persist,
        )

        if persist:
            await self.write_results([result])
        return result

    async def write_results(self, results: list[DrillResult]) -> None:
        if not results:
            return
        ensure_academy_data_dir()

        def _write() -> None:
            with open(DRILL_RESULTS_FILE, "a", encoding="utf-8") as handle:
                handle.writelines(result.model_dump_json() + "\n" for result in results)

        await asyncio.to_thread(_write)


training_drills = TrainingDrillsService()
