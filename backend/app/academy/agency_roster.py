"""Agency roster — job cards merging static role docs + live Academy stats."""

from __future__ import annotations

from typing import Any

from backend.app.academy.agent_defs import (
    NEO_AGENT_DEFINITIONS,
    experience_rank,
    get_agent_definition,
    next_level_at,
)
from backend.app.academy.agent_registry import agent_registry


def build_agency_roster() -> list[dict[str, Any]]:
    """Each agent as an agency job profile for the Agency tab."""
    rows: list[dict[str, Any]] = []
    for definition in NEO_AGENT_DEFINITIONS:
        identity = agent_registry.get_identity(definition.name)
        total_calls = identity.total_calls if identity else 0
        accuracy = identity.accuracy if identity else 0.0
        confidence = identity.confidence_level if identity else 0.5
        streak = identity.current_streak if identity else 0
        badges = [b.model_dump() for b in identity.badges] if identity else []
        level, xp_title = experience_rank(total_calls)
        # Keep ScoutIdentity.experience_level string in sync when present.
        if identity and identity.experience_level != xp_title:
            identity.experience_level = xp_title
        rows.append(
            {
                "id": definition.name,
                "name": definition.display_name,
                "code_name": definition.name,
                "profession": definition.profession,
                "archetype": definition.archetype,
                "agenda": definition.agenda,
                "lifetask": definition.lifetask,
                "level": level,
                "experience_title": xp_title,
                "experience": total_calls,
                "experience_to_next": next_level_at(total_calls),
                "confidence": round(float(confidence), 4),
                "accuracy": round(float(accuracy), 4),
                "current_streak": streak,
                "badges": badges,
                "drill_type": definition.drill_type,
                "status": "ACTIVE" if total_calls > 0 or definition.name == "orchestrator" else "STANDBY",
            }
        )
    rows.sort(key=lambda r: (-r["level"], -r["experience"], r["code_name"]))
    return rows


def agency_summary(roster: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    roster = roster if roster is not None else build_agency_roster()
    if not roster:
        return {"headcount": 0, "avg_confidence": 0.0, "avg_level": 0.0, "total_experience": 0}
    return {
        "headcount": len(roster),
        "avg_confidence": round(sum(r["confidence"] for r in roster) / len(roster), 4),
        "avg_level": round(sum(r["level"] for r in roster) / len(roster), 2),
        "total_experience": sum(r["experience"] for r in roster),
        "paper_only": True,
    }


def sync_identity_progress(scout_name: str, *, is_correct: bool, confidence: float) -> None:
    """Update confidence + experience title after a drill (paper training)."""
    ident = agent_registry.get_identity(scout_name)
    if ident is None:
        return
    # EMA toward observed drill confidence (correct answers pull up harder).
    target = float(confidence) if is_correct else max(0.15, float(confidence) * 0.7)
    ident.confidence_level = max(0.0, min(1.0, 0.75 * ident.confidence_level + 0.25 * target))
    _level, title = experience_rank(ident.total_calls)
    ident.experience_level = title
    # Ensure definition fields stay available for deploy-created agents.
    definition = get_agent_definition(scout_name)
    if definition and not ident.archetype:
        ident.archetype = definition.archetype
