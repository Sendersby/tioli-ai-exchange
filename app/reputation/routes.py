"""Reputation Engine — API routes."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.models import Agent
from app.config import settings
from app.database.db import async_session

from app.reputation.allocator import AllocationService
from app.reputation.dispatcher import DispatchService
from app.reputation.models import (
    PeerEndorsement, ReputationSnapshot, TaskAllocation,
    TaskDispatch, TaskOutcome, TaskRequest,
)
from app.reputation.outcome import OutcomeService
from app.reputation.scorer import ReputationScorer

router = APIRouter(prefix="/api/v1/reputation", tags=["Reputation Engine"])

# Services
allocator = AllocationService()
dispatcher = DispatchService()
outcome_svc = OutcomeService()
scorer = ReputationScorer(decay_days=getattr(settings, "reputation_decay_days", 90))


# ----- Dependencies -----

async def get_db():
    async with async_session() as session:
        yield session


def _check_enabled():
    if not getattr(settings, "reputation_engine_enabled", False):
        raise HTTPException(status_code=404, detail="Reputation engine is not enabled")


async def require_agent(
    authorization: str = Header(...), db: AsyncSession = Depends(get_db)
) -> Agent:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    from app.agents.auth import authenticate_agent
    agent = await authenticate_agent(db, authorization[7:])
    if not agent:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return agent


# ----- Request schemas -----

class TaskRequestCreate(BaseModel):
    title: str = Field(..., max_length=300)
    description: str | None = None
    required_skills: list[str] = []
    budget_min: float | None = None
    budget_max: float | None = None
    deadline: datetime | None = None
    priority: str = "normal"
    tags: list[str] = []


class DispatchCreate(BaseModel):
    agent_id: str
    sla_hours: int | None = None


class OutcomeCreate(BaseModel):
    quality_rating: int = Field(..., ge=1, le=5)
    rating_tags: list[str] = []
    review_text: str | None = None


class EndorsementCreate(BaseModel):
    endorsee_agent_id: str
    skill_tag: str = Field(..., max_length=100)
    comment: str | None = None


# ----- Task lifecycle endpoints -----

@router.post("/tasks", status_code=201)
async def create_task(
    body: TaskRequestCreate,
    agent: Agent = Depends(require_agent),
    db: AsyncSession = Depends(get_db),
):
    _check_enabled()
    task = TaskRequest(
        task_id=str(uuid.uuid4()),
        requester_agent_id=agent.id,
        title=body.title,
        description=body.description,
        required_skills=body.required_skills,
        budget_min=body.budget_min,
        budget_max=body.budget_max,
        deadline=body.deadline,
        priority=body.priority,
        tags=body.tags,
    )
    db.add(task)
    await db.commit()
    return {"task_id": task.task_id, "status": task.status}


@router.get("/tasks/{task_id}")
async def get_task(task_id: str, db: AsyncSession = Depends(get_db)):
    _check_enabled()
    task = await db.get(TaskRequest, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return {
        "task_id": task.task_id,
        "title": task.title,
        "description": task.description,
        "required_skills": task.required_skills,
        "budget_min": task.budget_min,
        "budget_max": task.budget_max,
        "deadline": task.deadline.isoformat() if task.deadline else None,
        "priority": task.priority,
        "status": task.status,
        "created_at": task.created_at.isoformat(),
    }


@router.post("/tasks/{task_id}/allocate")
async def allocate_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
):
    _check_enabled()
    try:
        allocations = await allocator.allocate(db, task_id)
        await db.commit()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "task_id": task_id,
        "candidates": [
            {
                "rank": a.rank,
                "agent_id": a.agent_id,
                "composite_score": a.composite_score,
                "skill_match": a.skill_match_score,
                "reputation": a.reputation_score,
                "price_fit": a.price_fit_score,
                "availability": a.availability_score,
                "response_time": a.response_time_score,
                "rationale": a.rationale,
            }
            for a in allocations
        ],
    }


@router.post("/tasks/{task_id}/dispatch")
async def dispatch_task(
    task_id: str,
    body: DispatchCreate,
    db: AsyncSession = Depends(get_db),
):
    _check_enabled()
    try:
        dispatch = await dispatcher.dispatch(
            db, task_id, body.agent_id, sla_hours=body.sla_hours
        )
        await db.commit()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "dispatch_id": dispatch.dispatch_id,
        "task_id": task_id,
        "agent_id": body.agent_id,
        "status": dispatch.status,
        "sla_deadline": dispatch.sla_deadline.isoformat() if dispatch.sla_deadline else None,
    }


@router.post("/dispatches/{dispatch_id}/accept")
async def accept_dispatch(
    dispatch_id: str,
    agent: Agent = Depends(require_agent),
    db: AsyncSession = Depends(get_db),
):
    _check_enabled()
    try:
        dispatch = await dispatcher.accept(db, dispatch_id)
        await db.commit()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "dispatch_id": dispatch.dispatch_id,
        "status": dispatch.status,
        "response_time_seconds": dispatch.response_time_seconds,
    }


@router.post("/dispatches/{dispatch_id}/reject")
async def reject_dispatch(
    dispatch_id: str,
    agent: Agent = Depends(require_agent),
    db: AsyncSession = Depends(get_db),
):
    _check_enabled()
    try:
        dispatch = await dispatcher.reject(db, dispatch_id)
        await db.commit()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {"dispatch_id": dispatch.dispatch_id, "status": dispatch.status}


@router.post("/dispatches/{dispatch_id}/deliver")
async def deliver_dispatch(
    dispatch_id: str,
    agent: Agent = Depends(require_agent),
    db: AsyncSession = Depends(get_db),
):
    _check_enabled()
    try:
        dispatch = await dispatcher.mark_delivered(db, dispatch_id)
        await db.commit()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "dispatch_id": dispatch.dispatch_id,
        "status": dispatch.status,
        "sla_met": dispatch.sla_met,
    }


@router.post("/dispatches/{dispatch_id}/rate")
async def rate_dispatch(
    dispatch_id: str,
    body: OutcomeCreate,
    agent: Agent = Depends(require_agent),
    db: AsyncSession = Depends(get_db),
):
    _check_enabled()
    try:
        outcome = await outcome_svc.record_outcome(
            db, dispatch_id, agent.id, body.quality_rating,
            rating_tags=body.rating_tags, review_text=body.review_text,
        )
        # Recalculate reputation for the rated agent
        dispatch = await db.get(TaskDispatch, dispatch_id)
        if dispatch:
            await scorer.calculate(db, dispatch.agent_id)
        await db.commit()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "outcome_id": outcome.outcome_id,
        "quality_rating": outcome.quality_rating,
        "on_time": outcome.on_time,
        "blockchain_tx_id": outcome.blockchain_tx_id,
    }


# ----- Reputation query endpoints -----

@router.get("/agents/{agent_id}")
async def get_agent_reputation(
    agent_id: str, db: AsyncSession = Depends(get_db)
):
    _check_enabled()
    from app.agentbroker.models import AgentReputationScore
    result = await db.execute(
        select(AgentReputationScore).where(
            AgentReputationScore.agent_id == agent_id
        )
    )
    score = result.scalar_one_or_none()
    if not score:
        raise HTTPException(status_code=404, detail="No reputation data for this agent")

    # Endorsement count
    from sqlalchemy import func as sa_func
    endorsements = (await db.execute(
        select(sa_func.count(PeerEndorsement.endorsement_id)).where(
            PeerEndorsement.endorsee_agent_id == agent_id
        )
    )).scalar() or 0

    # Quality average
    quality_avg = (await db.execute(
        select(sa_func.avg(TaskOutcome.quality_rating)).where(
            TaskOutcome.agent_id == agent_id
        )
    )).scalar()

    return {
        "agent_id": agent_id,
        "overall_score": score.overall_score,
        "delivery_rate": score.delivery_rate,
        "on_time_rate": score.on_time_rate,
        "acceptance_rate": score.acceptance_rate,
        "dispute_rate": score.dispute_rate,
        "volume_multiplier": score.volume_multiplier,
        "recency_score": score.recency_score,
        "total_engagements": score.total_engagements,
        "total_completed": score.total_completed,
        "total_disputed": score.total_disputed,
        "quality_avg": round(quality_avg, 2) if quality_avg else None,
        "peer_endorsements": endorsements,
        "calculated_at": score.calculated_at.isoformat() if score.calculated_at else None,
    }


@router.get("/agents/{agent_id}/history")
async def get_reputation_history(
    agent_id: str, db: AsyncSession = Depends(get_db)
):
    _check_enabled()
    result = await db.execute(
        select(ReputationSnapshot)
        .where(ReputationSnapshot.agent_id == agent_id)
        .order_by(ReputationSnapshot.calculated_at.desc())
        .limit(90)
    )
    snapshots = result.scalars().all()

    return {
        "agent_id": agent_id,
        "snapshots": [
            {
                "overall_score": s.overall_score,
                "quality_avg": s.quality_avg,
                "on_time_pct": s.on_time_pct,
                "endorsement_count": s.endorsement_count,
                "total_engagements": s.total_engagements,
                "calculated_at": s.calculated_at.isoformat(),
            }
            for s in snapshots
        ],
    }


@router.post("/agents/{agent_id}/recalculate")
async def recalculate_reputation(
    agent_id: str, db: AsyncSession = Depends(get_db)
):
    _check_enabled()
    score = await scorer.calculate(db, agent_id)
    await scorer.snapshot(db, agent_id)
    await db.commit()
    return {
        "agent_id": agent_id,
        "overall_score": score.overall_score,
        "recalculated_at": score.calculated_at.isoformat(),
    }


# ----- Peer endorsements -----

@router.post("/endorsements", status_code=201)
async def create_endorsement(
    body: EndorsementCreate,
    agent: Agent = Depends(require_agent),
    db: AsyncSession = Depends(get_db),
):
    _check_enabled()
    if agent.id == body.endorsee_agent_id:
        raise HTTPException(status_code=400, detail="Cannot endorse yourself")

    endorsement = PeerEndorsement(
        endorsement_id=str(uuid.uuid4()),
        endorser_agent_id=agent.id,
        endorsee_agent_id=body.endorsee_agent_id,
        skill_tag=body.skill_tag,
        comment=body.comment,
    )
    db.add(endorsement)
    await db.commit()
    return {"endorsement_id": endorsement.endorsement_id, "skill_tag": body.skill_tag}
