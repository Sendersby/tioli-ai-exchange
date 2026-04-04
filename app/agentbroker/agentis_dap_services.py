"""AGENTIS DAP v0.5.1 — Service functions for dispute arbitration protocol.

TVF calculation, case law, strike/streak management, epoch unlocks.
All integer arithmetic where specified by the protocol.
"""

import uuid
from datetime import datetime, timezone, timedelta

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.agentbroker.models import (
    AgentEngagement, EngagementDispute,
    OperatorReputationStrike, OperatorCleanStreak,
    AgentisCaseLaw, AgentisEpochState, AgentisTokenTransaction,
)


# -- Strike Weight Calculation --

STRIKE_HALF_JOBS = 10
STRIKE_ERASE_JOBS = 25


def strike_weight(streak: int) -> float:
    """Calculate strike weight based on clean streak.
    1.0 -> 0.5 after 10 clean -> 0.0 after 25 clean.
    """
    if streak >= STRIKE_ERASE_JOBS:
        return 0.0
    if streak >= STRIKE_HALF_JOBS:
        return 0.5
    return 1.0


async def add_strike(
    db: AsyncSession, operator_id: str,
    engagement_id: str, dispute_id: str
):
    """Add a dispute strike and reset the clean streak."""
    db.add(OperatorReputationStrike(
        strike_id=str(uuid.uuid4()),
        operator_id=operator_id,
        engagement_id=engagement_id,
        dispute_id=dispute_id,
        weight=1.0,
    ))
    result = await db.execute(
        select(OperatorCleanStreak).where(
            OperatorCleanStreak.operator_id == operator_id
        )
    )
    streak_record = result.scalar_one_or_none()
    if streak_record:
        streak_record.clean_streak = 0
        streak_record.updated_at = datetime.now(timezone.utc)
    else:
        db.add(OperatorCleanStreak(
            operator_id=operator_id, clean_streak=0,
        ))
    await db.flush()


async def award_clean_streak(db: AsyncSession, operator_id: str):
    """Increment clean streak and recalculate all strike weights."""
    result = await db.execute(
        select(OperatorCleanStreak).where(
            OperatorCleanStreak.operator_id == operator_id
        )
    )
    streak_record = result.scalar_one_or_none()
    if streak_record:
        streak_record.clean_streak += 1
        streak_record.updated_at = datetime.now(timezone.utc)
    else:
        streak_record = OperatorCleanStreak(
            operator_id=operator_id, clean_streak=1,
        )
        db.add(streak_record)
    await db.flush()

    new_streak = streak_record.clean_streak
    # Update all strike weights for this operator
    strikes_result = await db.execute(
        select(OperatorReputationStrike).where(
            OperatorReputationStrike.operator_id == operator_id
        )
    )
    for s in strikes_result.scalars().all():
        s.weight = strike_weight(new_streak)
        s.clean_streak_snapshot = new_streak
    await db.flush()


async def calculate_weighted_strike_rate(
    db: AsyncSession, operator_id: str, total_jobs: int
) -> float:
    """Calculate weighted strike rate for rep score (replaces flat dispute_rate)."""
    if total_jobs == 0:
        return 0.0
    result = await db.execute(
        select(func.sum(OperatorReputationStrike.weight)).where(
            OperatorReputationStrike.operator_id == operator_id
        )
    )
    weighted = float(result.scalar() or 0)
    return weighted / total_jobs


def get_effective_rating(engagement: AgentEngagement) -> float:
    """Return arbiter_rating if set, else client rating from the engagement."""
    if settings.agentis_dap_enabled and engagement.arbiter_rating is not None:
        return float(engagement.arbiter_rating)
    if hasattr(engagement, 'dispute_record') and engagement.dispute_record:
        dr = engagement.dispute_record
        if isinstance(dr, dict) and dr.get('rating'):
            return float(dr['rating'])
    return 5.0


# -- TVF (Transaction Volume Floor) --

async def get_verified_gtv_cents(db: AsyncSession) -> int:
    """Sum of COMPLETED engagement values in 730-day window, no dispute deposit."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=730)
    result = await db.execute(
        select(func.sum(AgentEngagement.proposed_price)).where(
            AgentEngagement.current_state == "COMPLETED",
            AgentEngagement.completed_at >= cutoff,
            AgentEngagement.dispute_deposit_cents == 0,
        )
    )
    total_float = result.scalar() or 0
    return int(total_float * 100)


async def get_tvf_micros(db: AsyncSession) -> int:
    """TVF as integer micros (cents x 10000). No float arithmetic."""
    gtv_cents = await get_verified_gtv_cents(db)
    supply_result = await db.execute(
        select(func.sum(AgentisEpochState.supply_tranche)).where(
            AgentisEpochState.unlocked == True
        )
    )
    supply = int(supply_result.scalar() or 0)
    if supply == 0:
        return 0
    return (gtv_cents * 10000) // supply


async def check_epoch_unlocks(db: AsyncSession):
    """One-way epoch unlock on GTV milestones."""
    gtv_cents = await get_verified_gtv_cents(db)
    result = await db.execute(
        select(AgentisEpochState).where(AgentisEpochState.unlocked == False)
    )
    for ep in result.scalars().all():
        if gtv_cents >= ep.gtv_threshold_cents:
            ep.unlocked = True
            ep.unlocked_at = datetime.now(timezone.utc)
    await db.flush()


# -- Case Law --

async def publish_case_law(
    db: AsyncSession, dispute: EngagementDispute,
    engagement: AgentEngagement, ruling_body
):
    """Record immutable case law entry."""
    db.add(AgentisCaseLaw(
        case_id=str(uuid.uuid4()),
        dispute_id=dispute.dispute_id,
        engagement_id=engagement.engagement_id,
        operator_client_id=engagement.client_agent_id,
        operator_prov_id=engagement.provider_agent_id,
        engagement_title=engagement.engagement_title,
        category=None,
        value_cents=int(engagement.proposed_price * 100),
        hash_matched=ruling_body.hash_matched,
        scope_complied=ruling_body.scope_complied,
        ruling=ruling_body.winner,
        arbiter_rating=ruling_body.arbiter_rating,
        arbiter_reasoning=ruling_body.arbiter_reasoning,
        deposit_cents=dispute.dispute_deposit_cents,
        deposit_forfeited=dispute.deposit_forfeited,
        acceptance_criteria=engagement.acceptance_criteria,
        phase="phase_1",
        block_ref=str(engagement.ledger_transaction_id or ""),
    ))
    dispute.case_law_published_at = datetime.now(timezone.utc)
    await db.flush()


# -- Charity Guard --

def should_record_charity(engagement: AgentEngagement) -> bool:
    """Charity only on verified settled GTV - not on refunds or disputed work."""
    if settings.agentis_dap_enabled:
        return engagement.current_state in ("COMPLETED",)
    return True


# -- Zero-Day Gate --

def calculate_gate_ms(value: float) -> int:
    """Calculate zero-day gate duration based on engagement value."""
    value_cents = int(value * 100)
    if value_cents <= 100000:     # Up to R1,000
        return 4 * 3600 * 1000   # 4 hours
    elif value_cents <= 500000:   # R1,001 to R5,000
        return 24 * 3600 * 1000  # 24 hours
    else:                         # Above R5,000
        return 48 * 3600 * 1000  # 48 hours


def calculate_dispute_deposit(value: float) -> float:
    """Calculate dispute deposit: 5% of value, capped at R5,000."""
    deposit = value * 0.05
    return min(deposit, 5000.0)
