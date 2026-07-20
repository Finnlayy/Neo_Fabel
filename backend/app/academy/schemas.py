"""Academy / training-loop Pydantic contracts (ported from Jules prompt pack)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Badge(BaseModel):
    name: str
    description: str
    icon: str
    awarded_at: str = Field(default_factory=_utc_now)


class CareerEntry(BaseModel):
    entry_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    scout_name: str
    event_type: str
    timestamp: str = Field(default_factory=_utc_now)
    details: dict[str, Any] = Field(default_factory=dict)


class ScoutIdentity(BaseModel):
    scout_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    archetype: str
    created_at: str = Field(default_factory=_utc_now)
    born_from: str = "v1_base"
    generation: int = 1
    specialization_symbols: list[str] = Field(default_factory=list)
    badges: list[Badge] = Field(default_factory=list)
    personality_vector: dict[str, float] = Field(default_factory=dict)
    total_calls: int = 0
    correct_calls: int = 0
    accuracy: float = 0.0
    current_streak: int = 0
    confidence_level: float = Field(default=0.5, ge=0.0, le=1.0)
    experience_level: str = Field(default="Novice")


class AgentLeaderboardEntry(BaseModel):
    scout_name: str
    accuracy: float
    experience: int
    specialization_score: float
    top_badge: Optional[Badge] = None


class SyntheticDrill(BaseModel):
    drill_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    drill_type: str
    scout_target: str
    scenario_data: dict[str, Any]
    expected_outcome: Any
    difficulty: int = 1


class DrillResult(BaseModel):
    result_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    drill_id: str
    scout_name: str
    scout_decision: Any
    is_correct: bool
    confidence: float
    timestamp: str = Field(default_factory=_utc_now)
    feedback_notes: str = ""
    rubric: dict[str, Any] = Field(default_factory=dict)


class PromptVersion(BaseModel):
    version_id: str
    scout_name: str
    prompt_text: str
    created_at: str = Field(default_factory=_utc_now)
    parent_version: Optional[str] = None
    change_summary: str = "Initial version"


class ABTest(BaseModel):
    test_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    scout_name: str
    variant_a_version: str
    variant_b_version: str
    status: str = "running"
    started_at: str = Field(default_factory=_utc_now)
    concluded_at: Optional[str] = None
    calls_a: int = 0
    calls_b: int = 0
    correct_a: int = 0
    correct_b: int = 0
    winner_version: Optional[str] = None


class CurriculumProgress(BaseModel):
    scout_name: str
    curriculum_level: str
    completed_drills: int = 0
    required_drills: int = 10
    passed_drills: int = 0
    average_confidence: float = 0.0


class DiversityMonitorStats(BaseModel):
    agreement_rate: float = 0.0
    total_evaluations: int = 0
    high_agreement_warnings: int = 0
    low_agreement_warnings: int = 0
    status: str = "optimal"


class DrillEvaluateRequest(BaseModel):
    drill: SyntheticDrill
    scout_decision: str
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)


class AgentDeployRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    archetype: str = Field(default="Analyst", min_length=1, max_length=64)
    personality_vector: dict[str, float] = Field(default_factory=dict)
    specialization_symbols: list[str] = Field(default_factory=list)
