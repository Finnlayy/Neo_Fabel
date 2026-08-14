"""Analyze swarm signals + prompt-shot logs → prompt_evolution / A/B."""

from __future__ import annotations

from typing import Any

from backend.app.academy.ab_testing import ab_testing
from backend.app.academy.agent_registry import agent_registry
from backend.app.academy.prompt_evolution import prompt_evolution
from backend.app.academy.prompt_shot_log import read_recent_events
from backend.app.ai_prompts.loader import classify_skill_gate, load_doctrine, skill_names_in_text


class PromptShotOptimizer:
    """In-process analyzer — no separate agent bus, no full SKILL.md dumps."""

    def analyze_and_maybe_evolve(self, scout_name: str = "orchestrator") -> dict[str, Any]:
        ident = agent_registry.get_identity(scout_name)
        if not ident:
            return {"evolved": False, "reason": "no_identity"}

        events = read_recent_events(80)
        signals = self._collect_signals(scout_name, events, ident)
        if not signals["should_evolve"]:
            return {"evolved": False, "reason": signals["reason"], "signals": signals}

        parent = ident.born_from
        new_version_id = f"{scout_name}_v{ident.generation + 1}_shot_opt"
        if prompt_evolution.get_version(new_version_id):
            return {"evolved": False, "reason": "version_exists", "version_id": new_version_id}

        doctrine = load_doctrine()
        notes = "; ".join(signals["notes"][:5])
        prompt_text = (
            f"{doctrine}\n\n# Evolution notes\n{notes}\n"
            "Prefer DELEGATE paper_ok skills; REFUSE live_gated. "
            "Use ≤3 prompt shots; never paste skill bodies."
        )[:4000]

        prompt_evolution.create_version(
            scout_name,
            new_version_id,
            prompt_text,
            parent_version=parent,
            change_summary=f"PromptShotOptimizer: {signals['reason']}",
        )
        ab_testing.start_test(scout_name, parent, new_version_id)
        ident.generation += 1
        ident.born_from = new_version_id
        agent_registry.save_registry()
        return {
            "evolved": True,
            "reason": signals["reason"],
            "version_id": new_version_id,
            "signals": signals,
        }

    def _collect_signals(
        self,
        scout_name: str,
        events: list[dict[str, Any]],
        ident: Any,
    ) -> dict[str, Any]:
        notes: list[str] = []
        live_accepted = 0
        routing_fails = 0
        drill_misses = 0

        for event in events:
            if event.get("channel") not in {"orchestrate", "chat-orch", "drill"}:
                continue
            outcome = str(event.get("outcome") or "").upper()
            skills = event.get("skill_hints") or []
            if not isinstance(skills, list):
                skills = skill_names_in_text(str(skills))
            for skill in skills:
                gate = classify_skill_gate(str(skill))
                if gate == "live_gated" and outcome in {"PROCEED", "CONCLUSION", "HANDOFF"}:
                    live_accepted += 1
                    notes.append(f"accepted live_gated skill:{skill}")
            if event.get("skill_routing_ok") is False:
                routing_fails += 1
                notes.append("skill_routing_ok=false")
            if event.get("is_correct") is False and event.get("drill_type") in {
                "orchestration_teamwork",
                "execution_quality",
            }:
                drill_misses += 1
                notes.append(f"missed {event.get('drill_type')}")

        # Fellow-agent careers: low accuracy after enough calls.
        peer_weak = 0
        for peer in agent_registry.get_all_identities():
            if peer.name == scout_name:
                continue
            if peer.total_calls >= 8 and peer.accuracy < 0.55:
                peer_weak += 1
                notes.append(f"peer {peer.name} accuracy={peer.accuracy:.2f}")

        should = False
        reason = "healthy"
        if live_accepted >= 1:
            should = True
            reason = "live_gated_accepted"
        elif routing_fails >= 2 or drill_misses >= 3:
            should = True
            reason = "routing_or_drill_failures"
        elif ident.total_calls > 20 and ident.accuracy < 0.6:
            should = True
            reason = "orchestrator_accuracy"
        elif peer_weak >= 3 and ident.total_calls > 10:
            should = True
            reason = "peer_swarm_weakness"

        return {
            "should_evolve": should,
            "reason": reason,
            "notes": notes,
            "live_accepted": live_accepted,
            "routing_fails": routing_fails,
            "drill_misses": drill_misses,
            "peer_weak": peer_weak,
        }


prompt_shot_optimizer = PromptShotOptimizer()
