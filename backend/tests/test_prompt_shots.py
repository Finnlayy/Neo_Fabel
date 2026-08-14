"""Doctrine / prompt-shot loader, skill gates, and optimizer path."""

from __future__ import annotations

from pathlib import Path

from backend.app.academy.prompt_shot_log import append_prompt_shot_event, read_recent_events
from backend.app.academy.prompt_shot_optimizer import prompt_shot_optimizer
from backend.app.academy.training_drills import training_drills
from backend.app.ai_prompts.loader import (
    MAX_SHOTS,
    MAX_SYSTEM_CHARS,
    build_orchestrator_system,
    classify_skill_gate,
    load_doctrine,
    load_kraken_skill_index,
    load_prompt_shots,
    skill_names_in_text,
)


def test_doctrine_and_index_present() -> None:
    import re

    doctrine = load_doctrine()
    index = load_kraken_skill_index()
    assert "MASTER ORCHESTRATOR" in doctrine or "Master Orchestrator" in doctrine
    assert "paper_ok" in index
    assert "live_gated" in index
    skill_ids = set(re.findall(r"(?:kraken|recipe)-[a-z0-9-]+", index, flags=re.I))
    assert len(skill_ids) >= 40
    # Never embed full plugin SKILL.md dump markers.
    assert "```yaml" not in index
    assert len(doctrine) < 8_000


def test_prompt_shots_budget() -> None:
    block, ids = load_prompt_shots()
    assert 1 <= len(ids) <= MAX_SHOTS
    assert len(block) <= 1_200
    system, shot_ids = build_orchestrator_system()
    assert len(system) <= MAX_SYSTEM_CHARS
    assert shot_ids
    assert "PROMPT SHOTS" in system
    assert "KRAKEN SKILL INDEX" in system or "skill:" in system.lower()


def test_skill_gates_paper_vs_live() -> None:
    assert classify_skill_gate("kraken-paper-strategy") == "paper_ok"
    assert classify_skill_gate("skill: recipe-paper-strategy-backtest") == "paper_ok"
    assert classify_skill_gate("recipe-withdrawal-to-cold-storage") == "live_gated"
    assert classify_skill_gate("kraken-paper-to-live") == "live_gated"
    assert classify_skill_gate("kraken-spot-execution") == "live_gated"
    names = skill_names_in_text("DELEGATE skill:kraken-paper-strategy then REFUSE skill:kraken-paper-to-live")
    assert "kraken-paper-strategy" in names
    assert "kraken-paper-to-live" in names


def test_orchestrator_teamwork_drill() -> None:
    drill = training_drills.generate_random_drill("orchestrator", difficulty=2)
    assert drill.drill_type == "orchestration_teamwork"
    assert drill.scenario_data.get("mode") == "teamwork"
    assert drill.expected_outcome in {"HANDOFF", "BLOCKED", "QUESTION", "CONCLUSION"}
    assert "packets" in drill.scenario_data


def test_prompt_shot_log_and_optimizer_evolution(tmp_path: Path, monkeypatch) -> None:
    log_file = tmp_path / "prompt_shot_log.jsonl"
    monkeypatch.setattr(
        "backend.app.academy.prompt_shot_log.PROMPT_SHOT_LOG_FILE",
        log_file,
    )

    append_prompt_shot_event(
        {
            "channel": "orchestrate",
            "shot_ids": ["kraken_live_refuse"],
            "skill_hints": ["recipe-withdrawal-to-cold-storage"],
            "skill_routing_ok": False,
            "outcome": "PROCEED",
            "is_correct": False,
            "drill_type": "orchestration_teamwork",
        }
    )
    events = read_recent_events(10)
    assert events
    assert events[-1]["skill_hints"][0].startswith("recipe-")

    from backend.app.academy.agent_registry import agent_registry

    ident = agent_registry.get_identity("orchestrator")
    assert ident is not None
    # Unique generation so create_version does not collide across runs.
    ident.generation = 900 + (ident.generation % 50)
    result = prompt_shot_optimizer.analyze_and_maybe_evolve("orchestrator")
    assert result.get("reason") in {
        "live_gated_accepted",
        "routing_or_drill_failures",
        "version_exists",
    } or result["evolved"] is True
    if result["evolved"]:
        assert "version_id" in result
        assert "shot_opt" in result["version_id"]