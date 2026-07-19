"""Neo_Fabel sub-agent identities + drill type mapping (Jules scout remap)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AgentDefinition:
    name: str
    archetype: str
    drill_type: str
    personality_vector: dict[str, float]
    display_name: str
    profession: str
    agenda: str
    lifetask: str


# Maps Jules scouts → Neo INITIAL_SUB_AGENTS ids.
NEO_AGENT_DEFINITIONS: tuple[AgentDefinition, ...] = (
    AgentDefinition(
        name="orchestrator",
        archetype="Diplomat",
        drill_type="orchestration_teamwork",
        personality_vector={"analytical": 0.5, "cautious": 0.5, "momentum_driven": 0.5},
        display_name="Master Orchestrator",
        profession="Agency Director",
        agenda="Align swarm packets, skill routing, and execution gates into one coherent plan.",
        lifetask="Keep the agency paper-safe while maximizing coordinated decision quality.",
    ),
    AgentDefinition(
        name="market_data",
        archetype="Analyst",
        drill_type="pattern_recognition",
        personality_vector={"analytical": 0.9, "cautious": 0.4, "momentum_driven": 0.8},
        display_name="Market Data Agent",
        profession="Market Intelligence Officer",
        agenda="Ingest multi-venue ticks, depth, and OHLCV so every peer shares one tape truth.",
        lifetask="Never leave the agency blind — freshness and coverage before narrative.",
    ),
    AgentDefinition(
        name="rna_smart",
        archetype="Patternist",
        drill_type="pattern_recognition",
        personality_vector={"analytical": 0.85, "cautious": 0.35, "momentum_driven": 0.7},
        display_name="RNA Smartelligent",
        profession="Blind Geometry Specialist",
        agenda="Read candlestick structure as relative geometry — no symbols, no absolute prices.",
        lifetask="Surface honest pattern bias the agency can debate without look-ahead leakage.",
    ),
    AgentDefinition(
        name="risk_gov",
        archetype="Guardian",
        drill_type="crisis_detection",
        personality_vector={"analytical": 0.8, "cautious": 0.95, "momentum_driven": 0.1},
        display_name="Risk Governor",
        profession="Chief Risk Officer",
        agenda="Enforce drawdown, autonomy, and compliance shields before any capital path.",
        lifetask="Block toxic regimes early; protect the agency from irreversible live risk.",
    ),
    AgentDefinition(
        name="kraken_broker",
        archetype="Operator",
        drill_type="execution_quality",
        personality_vector={"analytical": 0.9, "cautious": 0.9, "momentum_driven": 0.2},
        display_name="Kraken Broker Execution",
        profession="Execution Specialist",
        agenda="Route paper fills cleanly; report slippage and rejects without live side-effects.",
        lifetask="Make execution telemetry trustworthy so strategy never invents fills.",
    ),
    AgentDefinition(
        name="predictive",
        archetype="Strategist",
        drill_type="regime_identification",
        personality_vector={"analytical": 0.7, "cautious": 0.7, "momentum_driven": 0.3},
        display_name="Predictive Modeling",
        profession="Regime Strategist",
        agenda="Project short-horizon vectors and volatility corridors for planning only.",
        lifetask="Warn the agency when regimes shift before they become losses.",
    ),
    AgentDefinition(
        name="chronos",
        archetype="KLine Linguist",
        drill_type="kline_language",
        personality_vector={"analytical": 0.95, "cautious": 0.75, "momentum_driven": 0.45},
        display_name="Chronos K-Line Agent",
        profession="K-Line Language Scientist",
        agenda="Tokenize OHLCVA via causal Z-score + BSQ; forecast with coarse/fine structure.",
        lifetask="Teach the agency the language of markets — paper signals, never auto-execution.",
    ),
    AgentDefinition(
        name="analytic",
        archetype="Analyst",
        drill_type="sentiment_analysis",
        personality_vector={"analytical": 0.9, "cautious": 0.4, "momentum_driven": 0.6},
        display_name="Analytical Analysis",
        profession="Portfolio Analyst",
        agenda="Compile performance, yield, and multi-asset context into decision-ready briefs.",
        lifetask="Turn ledger noise into clear agency scorecards.",
    ),
    AgentDefinition(
        name="adaptive",
        archetype="Researcher",
        drill_type="sentiment_analysis",
        personality_vector={"analytical": 0.8, "cautious": 0.4, "momentum_driven": 0.6},
        display_name="Adaptive Agent",
        profession="Parameter Researcher",
        agenda="Retune thresholds and sizing as regimes evolve — always under risk_gov veto.",
        lifetask="Keep the agency adaptive without becoming reckless.",
    ),
)

NEO_AGENT_NAMES: tuple[str, ...] = tuple(d.name for d in NEO_AGENT_DEFINITIONS)

_BY_NAME = {d.name: d for d in NEO_AGENT_DEFINITIONS}

_LEVEL_THRESHOLDS: tuple[tuple[int, str, int], ...] = (
    (0, "Novice", 1),
    (10, "Apprentice", 2),
    (50, "Adept", 3),
    (100, "Expert", 4),
    (250, "Master", 5),
)


def get_agent_definition(name: str) -> AgentDefinition | None:
    return _BY_NAME.get(name)


def experience_rank(total_calls: int) -> tuple[int, str]:
    """Return (level_number, experience_title) from career call count."""
    level_num = 1
    title = "Novice"
    for threshold, name, num in _LEVEL_THRESHOLDS:
        if total_calls >= threshold:
            level_num = num
            title = name
    return level_num, title


def next_level_at(total_calls: int) -> int | None:
    for threshold, _name, _num in _LEVEL_THRESHOLDS:
        if total_calls < threshold:
            return threshold
    return None
