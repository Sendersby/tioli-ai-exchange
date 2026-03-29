"""Enhanced Reputation Scorer — replaces placeholder logic with real calculations.

Weighted composite (same weights as existing AgentReputationScore):
  delivery_rate   30%  — completed / total engagements
  on_time_rate    20%  — on-time deliveries / total deliveries
  acceptance_rate 20%  — accepted dispatches / total dispatches
  dispute_score   15%  — inverted dispute ratio
  volume_score    10%  — logarithmic volume bonus
  recency_score    5%  — exponential decay favouring recent activity

Plus quality overlay from TaskOutcome ratings (1-5 stars).
"""

import math
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agentbroker.models import (
    AgentEngagement, AgentReputationScore, EngagementDispute,
)
from app.reputation.models import (
    PeerEndorsement, ReputationSnapshot, TaskDispatch, TaskOutcome,
)


class ReputationScorer:
    """Calculates comprehensive reputation scores with decay."""

    def __init__(self, decay_days: int = 90):
        self.decay_days = decay_days

    async def calculate(
        self, db: AsyncSession, agent_id: str
    ) -> AgentReputationScore:
        """Calculate and persist the full reputation score for an agent."""

        # --- Engagement stats ---
        total = (await db.execute(
            select(func.count(AgentEngagement.engagement_id)).where(
                AgentEngagement.provider_agent_id == agent_id,
                AgentEngagement.current_state.in_(
                    ["COMPLETED", "REFUNDED", "DISPUTED"]
                ),
            )
        )).scalar() or 0

        completed = (await db.execute(
            select(func.count(AgentEngagement.engagement_id)).where(
                AgentEngagement.provider_agent_id == agent_id,
                AgentEngagement.current_state == "COMPLETED",
            )
        )).scalar() or 0

        disputed = (await db.execute(
            select(func.count(EngagementDispute.dispute_id)).where(
                EngagementDispute.raised_by != agent_id,
            )
        )).scalar() or 0

        # --- Delivery rate (30%) ---
        delivery_rate = (completed / total * 10) if total > 0 else 10.0

        # --- On-time rate (20%) — from TaskOutcome data ---
        on_time_stats = await db.execute(
            select(
                func.count(TaskOutcome.outcome_id),
                func.count(TaskOutcome.outcome_id).filter(TaskOutcome.on_time.is_(True)),
            ).where(TaskOutcome.agent_id == agent_id)
        )
        row = on_time_stats.first()
        outcome_count = row[0] if row else 0
        on_time_count = row[1] if row and row[1] else 0

        if outcome_count > 0:
            on_time_rate = (on_time_count / outcome_count) * 10.0
        else:
            on_time_rate = 10.0  # no data = benefit of doubt

        # --- Acceptance rate (20%) — from TaskDispatch data ---
        dispatch_stats = await db.execute(
            select(
                func.count(TaskDispatch.dispatch_id),
                func.count(TaskDispatch.accepted_at),
            ).where(TaskDispatch.agent_id == agent_id)
        )
        d_row = dispatch_stats.first()
        total_dispatches = d_row[0] if d_row else 0
        accepted_dispatches = d_row[1] if d_row and d_row[1] else 0

        if total_dispatches > 0:
            acceptance_rate = (accepted_dispatches / total_dispatches) * 10.0
        else:
            acceptance_rate = delivery_rate  # proxy: use delivery rate

        # --- Dispute score (15%, inverted) ---
        dispute_score = ((1 - disputed / max(total, 1)) * 10) if total > 0 else 10.0

        # --- Volume score (10%) ---
        volume_score = min(10.0, math.log(max(total, 1) + 1) * 3)

        # --- Recency score (5%) — exponential decay ---
        recency_score = await self._calculate_recency(db, agent_id)

        # --- Quality overlay from ratings ---
        quality_avg = await self._calculate_quality_avg(db, agent_id)

        # --- Weighted composite ---
        overall = (
            delivery_rate * 0.30
            + on_time_rate * 0.20
            + acceptance_rate * 0.20
            + dispute_score * 0.15
            + volume_score * 0.10
            + recency_score * 0.05
        )

        # Quality adjustment: if we have ratings, blend them in (up to 20% influence)
        if quality_avg is not None:
            quality_normalised = quality_avg * 2.0  # 1-5 → 2-10
            overall = overall * 0.80 + quality_normalised * 0.20

        overall = round(min(10.0, max(0.0, overall)), 2)

        # --- Persist ---
        result = await db.execute(
            select(AgentReputationScore).where(
                AgentReputationScore.agent_id == agent_id
            )
        )
        score_record = result.scalar_one_or_none()

        if score_record:
            score_record.overall_score = overall
            score_record.delivery_rate = round(delivery_rate, 2)
            score_record.on_time_rate = round(on_time_rate, 2)
            score_record.acceptance_rate = round(acceptance_rate, 2)
            score_record.dispute_rate = round(dispute_score, 2)
            score_record.volume_multiplier = round(volume_score, 2)
            score_record.recency_score = round(recency_score, 2)
            score_record.total_engagements = total
            score_record.total_completed = completed
            score_record.total_disputed = disputed
            score_record.calculated_at = datetime.now(timezone.utc)
        else:
            score_record = AgentReputationScore(
                score_id=str(uuid.uuid4()),
                agent_id=agent_id,
                overall_score=overall,
                delivery_rate=round(delivery_rate, 2),
                on_time_rate=round(on_time_rate, 2),
                acceptance_rate=round(acceptance_rate, 2),
                dispute_rate=round(dispute_score, 2),
                volume_multiplier=round(volume_score, 2),
                recency_score=round(recency_score, 2),
                total_engagements=total,
                total_completed=completed,
                total_disputed=disputed,
                calculated_at=datetime.now(timezone.utc),
            )
            db.add(score_record)

        return score_record

    async def snapshot(self, db: AsyncSession, agent_id: str) -> ReputationSnapshot:
        """Take a point-in-time snapshot for history tracking."""
        result = await db.execute(
            select(AgentReputationScore).where(
                AgentReputationScore.agent_id == agent_id
            )
        )
        score = result.scalar_one_or_none()
        if not score:
            return None

        # Endorsement count
        endorsement_count = (await db.execute(
            select(func.count(PeerEndorsement.endorsement_id)).where(
                PeerEndorsement.endorsee_agent_id == agent_id
            )
        )).scalar() or 0

        snap = ReputationSnapshot(
            snapshot_id=str(uuid.uuid4()),
            agent_id=agent_id,
            overall_score=score.overall_score,
            delivery_rate=score.delivery_rate,
            quality_avg=await self._calculate_quality_avg(db, agent_id),
            on_time_pct=score.on_time_rate,
            dispute_rate=score.dispute_rate,
            endorsement_count=endorsement_count,
            total_engagements=score.total_engagements,
        )
        db.add(snap)
        return snap

    async def recalculate_all(self, db: AsyncSession) -> dict:
        """Recalculate scores for ALL agents (used by scheduled job)."""
        from sqlalchemy import select as sa_select
        from app.agents.models import Agent

        result = await db.execute(sa_select(Agent.id))
        agent_ids = [r[0] for r in result.all()]

        recalculated = 0
        for agent_id in agent_ids:
            await self.calculate(db, agent_id)
            await self.snapshot(db, agent_id)
            recalculated += 1

        return {"recalculated": recalculated}

    # ----- Internal helpers -----

    async def _calculate_recency(self, db: AsyncSession, agent_id: str) -> float:
        """Exponential decay based on days since last completed engagement."""
        result = await db.execute(
            select(func.max(AgentEngagement.completed_at)).where(
                AgentEngagement.provider_agent_id == agent_id,
                AgentEngagement.current_state == "COMPLETED",
            )
        )
        last_completed = result.scalar()
        if not last_completed:
            return 5.0  # no history

        days_ago = (datetime.now(timezone.utc) - last_completed).days
        decay = math.exp(-days_ago / self.decay_days)
        return round(decay * 10.0, 2)

    async def _calculate_quality_avg(
        self, db: AsyncSession, agent_id: str
    ) -> float | None:
        """Average quality rating from TaskOutcome (1-5 scale)."""
        result = await db.execute(
            select(func.avg(TaskOutcome.quality_rating)).where(
                TaskOutcome.agent_id == agent_id
            )
        )
        avg = result.scalar()
        return round(avg, 2) if avg is not None else None
