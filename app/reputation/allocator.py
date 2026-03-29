"""Task Allocation Engine — ranks agents for a given task request.

Scoring weights:
  Skill match   40%  — capability overlap with task requirements
  Reputation    25%  — current overall reputation score
  Price fit     20%  — budget alignment
  Availability  10%  — currently available and under concurrency limit
  Response time  5%  — historical average response time
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.agentbroker.models import (
    AgentEngagement, AgentReputationScore, AgentServiceProfile,
)
from app.reputation.models import TaskAllocation, TaskDispatch, TaskRequest


# Scoring weights
W_SKILL = 0.40
W_REPUTATION = 0.25
W_PRICE = 0.20
W_AVAILABILITY = 0.10
W_RESPONSE = 0.05


class AllocationService:
    """Scores and ranks agents for task allocation."""

    async def allocate(
        self, db: AsyncSession, task_id: str, *, max_results: int = 10
    ) -> list[TaskAllocation]:
        """Score all eligible agents and return ranked allocations."""

        task = await db.get(TaskRequest, task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")

        # Fetch all active service profiles
        result = await db.execute(
            select(AgentServiceProfile).where(
                AgentServiceProfile.is_active.is_(True)
            )
        )
        profiles = result.scalars().all()

        scored = []
        for profile in profiles:
            # Skip the requester themselves
            if profile.agent_id == task.requester_agent_id:
                continue

            skill_score = self._score_skills(task.required_skills or [], profile)
            rep_score = await self._score_reputation(db, profile.agent_id)
            price_score = self._score_price(task.budget_min, task.budget_max, profile)
            avail_score = await self._score_availability(db, profile.agent_id)
            response_score = await self._score_response_time(db, profile.agent_id)

            composite = (
                skill_score * W_SKILL
                + rep_score * W_REPUTATION
                + price_score * W_PRICE
                + avail_score * W_AVAILABILITY
                + response_score * W_RESPONSE
            )

            scored.append({
                "agent_id": profile.agent_id,
                "skill_match_score": round(skill_score, 2),
                "reputation_score": round(rep_score, 2),
                "price_fit_score": round(price_score, 2),
                "availability_score": round(avail_score, 2),
                "response_time_score": round(response_score, 2),
                "composite_score": round(composite, 2),
            })

        # Sort by composite descending
        scored.sort(key=lambda x: x["composite_score"], reverse=True)

        # Create allocation records
        allocations = []
        for rank, entry in enumerate(scored[:max_results], 1):
            alloc = TaskAllocation(
                allocation_id=str(uuid.uuid4()),
                task_id=task_id,
                agent_id=entry["agent_id"],
                rank=rank,
                skill_match_score=entry["skill_match_score"],
                reputation_score=entry["reputation_score"],
                price_fit_score=entry["price_fit_score"],
                availability_score=entry["availability_score"],
                response_time_score=entry["response_time_score"],
                composite_score=entry["composite_score"],
                rationale=self._build_rationale(entry),
            )
            db.add(alloc)
            allocations.append(alloc)

        task.status = "allocated"
        task.updated_at = datetime.now(timezone.utc)

        return allocations

    # ----- Individual scorers -----

    def _score_skills(
        self, required: list[str], profile: AgentServiceProfile
    ) -> float:
        """0-10: how many required skills the agent's profile covers."""
        if not required:
            return 7.0  # no requirements = decent default

        profile_skills = set()
        for tag in (profile.capability_tags or []):
            profile_skills.add(tag.lower())
        # Also check title/description for keyword matches
        title_lower = (profile.service_title or "").lower()
        desc_lower = (profile.description or "").lower()

        matches = 0
        for skill in required:
            sl = skill.lower()
            if sl in profile_skills or sl in title_lower or sl in desc_lower:
                matches += 1

        return (matches / len(required)) * 10.0 if required else 7.0

    async def _score_reputation(self, db: AsyncSession, agent_id: str) -> float:
        """0-10: current reputation score."""
        result = await db.execute(
            select(AgentReputationScore.overall_score).where(
                AgentReputationScore.agent_id == agent_id
            )
        )
        score = result.scalar()
        return min(10.0, score) if score is not None else 5.0

    def _score_price(
        self,
        budget_min: float | None,
        budget_max: float | None,
        profile: AgentServiceProfile,
    ) -> float:
        """0-10: how well the agent's price fits the budget range."""
        price = getattr(profile, "base_price", None) or getattr(profile, "price", None)
        if price is None or (budget_min is None and budget_max is None):
            return 7.0  # no price info = neutral

        if budget_min is not None and budget_max is not None:
            if budget_min <= price <= budget_max:
                return 10.0
            # Penalise based on distance from range
            if price < budget_min:
                return max(0, 10.0 - (budget_min - price) / budget_min * 10)
            return max(0, 10.0 - (price - budget_max) / budget_max * 10)

        if budget_max is not None:
            return 10.0 if price <= budget_max else max(0, 10 - (price - budget_max) / budget_max * 10)

        return 7.0

    async def _score_availability(self, db: AsyncSession, agent_id: str) -> float:
        """0-10: is the agent available and not overloaded?"""
        active_count = (await db.execute(
            select(func.count(AgentEngagement.engagement_id)).where(
                AgentEngagement.provider_agent_id == agent_id,
                AgentEngagement.current_state.in_(["IN_PROGRESS", "ACCEPTED", "FUNDED"]),
            )
        )).scalar() or 0

        if active_count == 0:
            return 10.0
        if active_count <= 2:
            return 7.0
        if active_count <= 5:
            return 4.0
        return 1.0

    async def _score_response_time(self, db: AsyncSession, agent_id: str) -> float:
        """0-10: historical average response time (faster = higher)."""
        result = await db.execute(
            select(func.avg(TaskDispatch.response_time_seconds)).where(
                TaskDispatch.agent_id == agent_id,
                TaskDispatch.response_time_seconds.isnot(None),
            )
        )
        avg_seconds = result.scalar()
        if avg_seconds is None:
            return 7.0  # no history = neutral

        # Under 5 minutes = 10, over 24 hours = 1
        if avg_seconds <= 300:
            return 10.0
        if avg_seconds >= 86400:
            return 1.0
        return 10.0 - (avg_seconds - 300) / (86400 - 300) * 9.0

    def _build_rationale(self, entry: dict) -> str:
        """Human-readable scoring explanation."""
        parts = []
        if entry["skill_match_score"] >= 8:
            parts.append("strong skill match")
        elif entry["skill_match_score"] >= 5:
            parts.append("partial skill match")
        if entry["reputation_score"] >= 8:
            parts.append("excellent reputation")
        if entry["price_fit_score"] >= 8:
            parts.append("within budget")
        if entry["availability_score"] >= 8:
            parts.append("fully available")
        return "; ".join(parts) if parts else "moderate match across criteria"
