"""Neo_Fabel sub-agent identities + drill type mapping (Jules scout remap)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AgentDefinition:
    name: str
    archetype: str
    drill_type: str
    personality_vector: dict[str, float]


# Maps Jules scouts → Neo INITIAL_SUB_AGENTS ids.
NEO_AGENT_DEFINITIONS: tuple[AgentDefinition, ...] = (
    AgentDefinition(
        name="orchestrator",
        archetype="Diplomat",
        drill_type="regime_identification",
        personality_vector={"analytical": 0.5, "cautious": 0.5, "momentum_driven": 0.5},
    ),
    AgentDefinition(
        name="market_data",
        archetype="Analyst",
        drill_type="pattern_recognition",
        personality_vector={"analytical": 0.9, "cautious": 0.4, "momentum_driven": 0.8},
    ),
    AgentDefinition(
        name="rna_smart",
        archetype="Patternist",
        drill_type="pattern_recognition",
        personality_vector={"analytical": 0.85, "cautious": 0.35, "momentum_driven": 0.7},
    ),
    AgentDefinition(
        name="risk_gov",
        archetype="Guardian",
        drill_type="crisis_detection",
        personality_vector={"analytical": 0.8, "cautious": 0.95, "momentum_driven": 0.1},
    ),
    AgentDefinition(
        name="kraken_broker",
        archetype="Operator",
        drill_type="execution_quality",
        personality_vector={"analytical": 0.9, "cautious": 0.9, "momentum_driven": 0.2},
    ),
    AgentDefinition(
        name="predictive",
        archetype="Strategist",
        drill_type="regime_identification",
        personality_vector={"analytical": 0.7, "cautious": 0.7, "momentum_driven": 0.3},
    ),
    AgentDefinition(
        name="analytic",
        archetype="Analyst",
        drill_type="sentiment_analysis",
        personality_vector={"analytical": 0.9, "cautious": 0.4, "momentum_driven": 0.6},
    ),
    AgentDefinition(
        name="adaptive",
        archetype="Researcher",
        drill_type="sentiment_analysis",
        personality_vector={"analytical": 0.8, "cautious": 0.4, "momentum_driven": 0.6},
    ),
)

NEO_AGENT_NAMES: tuple[str, ...] = tuple(d.name for d in NEO_AGENT_DEFINITIONS)

_BY_NAME = {d.name: d for d in NEO_AGENT_DEFINITIONS}


def get_agent_definition(name: str) -> AgentDefinition | None:
    return _BY_NAME.get(name)
