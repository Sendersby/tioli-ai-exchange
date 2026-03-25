"""Early trader incentive programme — bootstraps real trading activity.

Solves the chicken-and-egg problem (Issue #1) by giving early agents
a reason to make their first trades. Works alongside the market maker
to convert registrations into active traders.

Incentives:
1. Welcome bonus: credited on registration (e.g., 100 AGENTIS)
2. First trade bonus: extra credits after completing first trade
3. Volume milestone rewards: bonuses at volume thresholds

All bonuses are funded from the liquidity pool and tracked transparently.
The programme can be toggled on/off and has a hard cap to prevent abuse.
"""

import uuid
import logging
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, String, Boolean, Integer, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.db import Base
from app.agents.models import Agent, Wallet
from app.exchange.liquidity import LiquidityPool

logger = logging.getLogger(__name__)

# Programme configuration
WELCOME_BONUS = 100.0          # AGENTIS credited on registration
FIRST_TRADE_BONUS = 50.0       # AGENTIS after first completed trade
VOLUME_MILESTONES = {           # volume threshold → bonus
    1000: 100.0,                # 1,000 AGENTIS traded → 100 bonus
    10000: 500.0,               # 10,000 AGENTIS traded → 500 bonus
    100000: 2000.0,             # 100,000 AGENTIS traded → 2,000 bonus
}
MAX_PROGRAMME_SPEND = 50000.0   # Hard cap on total incentive spending
PROGRAMME_CURRENCY = "AGENTIS"


class IncentiveRecord(Base):
    """Tracks all incentive payouts for transparency and audit."""
    __tablename__ = "incentive_records"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(String, nullable=False)
    incentive_type = Column(String(50), nullable=False)  # welcome, first_trade, volume_milestone
    amount = Column(Float, nullable=False)
    description = Column(String(500), default="")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class IncentiveProgramme:
    """Manages early trader incentives funded from the liquidity pool."""

    def __init__(self):
        self.enabled = True

    async def _get_total_spent(self, db: AsyncSession) -> float:
        """Get total incentive spend to check against hard cap."""
        result = await db.execute(
            select(func.sum(IncentiveRecord.amount))
        )
        return result.scalar() or 0.0

    async def _has_received(
        self, db: AsyncSession, agent_id: str, incentive_type: str
    ) -> bool:
        """Check if agent already received a specific incentive."""
        result = await db.execute(
            select(func.count(IncentiveRecord.id)).where(
                IncentiveRecord.agent_id == agent_id,
                IncentiveRecord.incentive_type == incentive_type,
            )
        )
        return (result.scalar() or 0) > 0

    async def _credit_incentive(
        self, db: AsyncSession, agent_id: str, amount: float,
        incentive_type: str, description: str
    ) -> dict | None:
        """Credit an incentive to an agent's wallet, funded from the pool."""
        if not self.enabled:
            return None

        # Check hard cap
        total_spent = await self._get_total_spent(db)
        if total_spent + amount > MAX_PROGRAMME_SPEND:
            logger.warning(f"Incentive programme hard cap reached ({total_spent}/{MAX_PROGRAMME_SPEND})")
            return None

        # Fund from liquidity pool
        pool_result = await db.execute(
            select(LiquidityPool).where(LiquidityPool.currency == PROGRAMME_CURRENCY)
        )
        pool = pool_result.scalar_one_or_none()
        if not pool or pool.balance < amount:
            logger.warning(f"Incentive: insufficient pool balance for {amount} {PROGRAMME_CURRENCY}")
            return None

        pool.balance -= amount
        pool.updated_at = datetime.now(timezone.utc)

        # Credit agent wallet
        wallet_result = await db.execute(
            select(Wallet).where(
                Wallet.agent_id == agent_id,
                Wallet.currency == PROGRAMME_CURRENCY,
            )
        )
        wallet = wallet_result.scalar_one_or_none()
        if not wallet:
            wallet = Wallet(agent_id=agent_id, currency=PROGRAMME_CURRENCY)
            db.add(wallet)
            await db.flush()
        wallet.balance += amount

        # Record the incentive
        record = IncentiveRecord(
            agent_id=agent_id,
            incentive_type=incentive_type,
            amount=amount,
            description=description,
        )
        db.add(record)
        await db.flush()

        logger.info(f"Incentive: {incentive_type} {amount} {PROGRAMME_CURRENCY} → {agent_id}")
        return {
            "agent_id": agent_id,
            "type": incentive_type,
            "amount": amount,
            "description": description,
        }

    async def grant_welcome_bonus(self, db: AsyncSession, agent_id: str) -> dict | None:
        """Grant welcome bonus to a newly registered agent."""
        if await self._has_received(db, agent_id, "welcome"):
            return None  # Already received

        return await self._credit_incentive(
            db, agent_id, WELCOME_BONUS, "welcome",
            f"Welcome bonus: {WELCOME_BONUS} {PROGRAMME_CURRENCY} for joining TiOLi Exchange",
        )

    async def grant_first_trade_bonus(self, db: AsyncSession, agent_id: str) -> dict | None:
        """Grant bonus after agent completes their first trade."""
        if await self._has_received(db, agent_id, "first_trade"):
            return None  # Already received

        return await self._credit_incentive(
            db, agent_id, FIRST_TRADE_BONUS, "first_trade",
            f"First trade bonus: {FIRST_TRADE_BONUS} {PROGRAMME_CURRENCY} for your first trade",
        )

    async def check_volume_milestones(
        self, db: AsyncSession, agent_id: str, total_volume: float
    ) -> list[dict]:
        """Check and grant any volume milestone bonuses."""
        granted = []
        for threshold, bonus in sorted(VOLUME_MILESTONES.items()):
            if total_volume >= threshold:
                milestone_type = f"volume_{threshold}"
                if not await self._has_received(db, agent_id, milestone_type):
                    result = await self._credit_incentive(
                        db, agent_id, bonus, milestone_type,
                        f"Volume milestone: {bonus} {PROGRAMME_CURRENCY} "
                        f"for reaching {threshold:,} {PROGRAMME_CURRENCY} traded",
                    )
                    if result:
                        granted.append(result)
        return granted

    async def get_programme_status(self, db: AsyncSession) -> dict:
        """Get the incentive programme status and spending."""
        total_spent = await self._get_total_spent(db)

        # Count by type
        type_result = await db.execute(
            select(IncentiveRecord.incentive_type, func.count(IncentiveRecord.id), func.sum(IncentiveRecord.amount))
            .group_by(IncentiveRecord.incentive_type)
        )
        by_type = {
            row[0]: {"count": row[1], "total": round(row[2], 4)}
            for row in type_result.all()
        }

        return {
            "enabled": self.enabled,
            "total_spent": round(total_spent, 4),
            "budget_remaining": round(MAX_PROGRAMME_SPEND - total_spent, 4),
            "hard_cap": MAX_PROGRAMME_SPEND,
            "utilisation_pct": round(total_spent / MAX_PROGRAMME_SPEND * 100, 1),
            "by_type": by_type,
            "incentive_rates": {
                "welcome_bonus": WELCOME_BONUS,
                "first_trade_bonus": FIRST_TRADE_BONUS,
                "volume_milestones": VOLUME_MILESTONES,
            },
        }

    async def get_agent_incentives(self, db: AsyncSession, agent_id: str) -> list[dict]:
        """Get all incentives received by a specific agent."""
        result = await db.execute(
            select(IncentiveRecord)
            .where(IncentiveRecord.agent_id == agent_id)
            .order_by(IncentiveRecord.created_at.desc())
        )
        return [
            {
                "type": r.incentive_type, "amount": r.amount,
                "description": r.description, "date": str(r.created_at),
            }
            for r in result.scalars().all()
        ]
