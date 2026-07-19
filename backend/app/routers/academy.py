"""Slim Academy API — paper/training only (no live orders, no vectorbt)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.app.academy.ab_testing import ab_testing
from backend.app.academy.academy_curriculum import academy_curriculum
from backend.app.academy.agent_registry import agent_registry
from backend.app.academy.training_drills import training_drills
from backend.app.academy.training_loop import training_loop
from backend.app.auth import require_user
from backend.app.academy.schemas import AgentDeployRequest, DrillEvaluateRequest

router = APIRouter(prefix="/api/v1/academy", tags=["academy"])


@router.get("/status")
async def academy_status(_user: dict[str, Any] = Depends(require_user)) -> dict[str, Any]:
    return training_loop.get_status()


@router.post("/train/start")
async def train_start(_user: dict[str, Any] = Depends(require_user)) -> dict[str, Any]:
    return await training_loop.start()


@router.post("/train/stop")
async def train_stop(_user: dict[str, Any] = Depends(require_user)) -> dict[str, Any]:
    await training_loop.stop()
    return {"stopped": True}


@router.post("/train/cycle")
async def train_cycle(_user: dict[str, Any] = Depends(require_user)) -> dict[str, Any]:
    await training_loop.trigger_manual_cycle()
    return {"ok": True, "status": training_loop.get_status()}


@router.get("/agents/registry")
async def agents_registry(_user: dict[str, Any] = Depends(require_user)) -> dict[str, Any]:
    agents = agent_registry.get_all_identities()
    return {"agents": [a.model_dump() for a in agents]}


@router.post("/agents/deploy")
async def deploy_agent(
    req: AgentDeployRequest | None = None,
    _user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    payload = req or AgentDeployRequest()
    try:
        agent = agent_registry.deploy_identity(
            name=payload.name,
            archetype=payload.archetype,
            personality_vector=payload.personality_vector,
            specialization_symbols=payload.specialization_symbols,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail={"code": "agent_exists", "message": str(exc)}) from exc
    return {"status": "created", "agent": agent.model_dump()}


@router.get("/agents/leaderboard")
async def agents_leaderboard(_user: dict[str, Any] = Depends(require_user)) -> dict[str, Any]:
    agents = agent_registry.get_all_identities()
    leaderboard = []
    for agent in agents:
        top_badge = agent.badges[-1].model_dump() if agent.badges else None
        leaderboard.append(
            {
                "scout_name": agent.name,
                "archetype": agent.archetype,
                "accuracy": agent.accuracy,
                "experience": agent.total_calls,
                "specialization_score": 0.0,
                "top_badge": top_badge,
                "badges": [b.model_dump() for b in agent.badges],
            }
        )
    leaderboard.sort(key=lambda x: (x["accuracy"], x["experience"]), reverse=True)
    return {"leaderboard": leaderboard}


@router.get("/agents/{scout_name}/career")
async def agent_career(
    scout_name: str,
    _user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    entries = agent_registry.get_career_log(scout_name)
    return {"career": [e.model_dump() for e in entries]}


@router.get("/agents/careers/recent")
async def recent_careers(
    limit: int = Query(default=50, ge=1, le=500),
    event_type: str | None = Query(default=None),
    _user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    entries = agent_registry.get_recent_career_events(limit=limit, event_type=event_type)
    return {"career": [e.model_dump() for e in entries], "count": len(entries)}


@router.get("/drills/available")
async def drills_available(
    scout_name: str = Query(...),
    count: int = Query(default=5, ge=1, le=20),
    _user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    drills = training_drills.generate_drills(scout_name, count)
    return {"drills": [d.model_dump() for d in drills]}


@router.post("/drill/evaluate")
async def drill_evaluate(
    body: DrillEvaluateRequest,
    _user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    result = await training_drills.evaluate_drill(
        body.drill, body.scout_decision, body.confidence
    )
    academy_curriculum.record_drill_result(
        body.drill.scout_target, "Beginner", result.is_correct, result.confidence
    )
    return result.model_dump()


@router.get("/curriculum/{scout_name}")
async def curriculum(
    scout_name: str,
    _user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    progress = academy_curriculum.get_all_for_scout(scout_name)
    if not progress:
        # Ensure Beginner row exists for UI
        academy_curriculum.get_progress(scout_name, "Beginner")
        progress = academy_curriculum.get_all_for_scout(scout_name)
    return {"curriculum": [p.model_dump() for p in progress]}


@router.get("/ab-tests")
async def list_ab_tests(_user: dict[str, Any] = Depends(require_user)) -> dict[str, Any]:
    return {"ab_tests": [t.model_dump() for t in ab_testing.get_all()]}
