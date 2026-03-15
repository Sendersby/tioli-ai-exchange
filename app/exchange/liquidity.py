"""Founder Liquidity Pool — solving the chicken-and-egg problem.

Section 8.3: "Seed the platform with a founder-funded liquidity pool
at launch. This pool acts as market maker, providing buy and sell
quotes for all supported token types."

The pool is not a cost — it is capital that earns commission on every
transaction it facilitates and returns to the platform treasury.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, String, Integer, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.db import Base


class LiquidityPool(Base):
    """Platform liquidity pool for market making."""
    __tablename__ = "liquidity_pools"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    currency = Column(String(20), nullable=False)
    balance = Column(Float, default=0.0)
    total_seeded = Column(Float, default=0.0)
    total_earned = Column(Float, default=0.0)           # Earned from spread/commission
    transactions_facilitated = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class LiquidityService:
    """Manages the founder liquidity pool."""

    async def seed_pool(
        self, db: AsyncSession, currency: str, amount: float
    ) -> dict:
        """Seed or top up a liquidity pool for a currency."""
        result = await db.execute(
            select(LiquidityPool).where(LiquidityPool.currency == currency.upper())
        )
        pool = result.scalar_one_or_none()

        if pool:
            pool.balance += amount
            pool.total_seeded += amount
            pool.updated_at = datetime.now(timezone.utc)
        else:
            pool = LiquidityPool(
                currency=currency.upper(),
                balance=amount,
                total_seeded=amount,
            )
            db.add(pool)

        await db.flush()
        return {
            "currency": pool.currency,
            "balance": pool.balance,
            "total_seeded": pool.total_seeded,
        }

    async def get_pool_status(self, db: AsyncSession) -> list[dict]:
        """Get all liquidity pool balances."""
        result = await db.execute(
            select(LiquidityPool).order_by(LiquidityPool.currency)
        )
        return [
            {
                "currency": p.currency, "balance": p.balance,
                "total_seeded": p.total_seeded, "total_earned": p.total_earned,
                "transactions": p.transactions_facilitated,
            }
            for p in result.scalars().all()
        ]


class CreditScoringService:
    """Agent/operator credit scoring from transaction history.

    Section 5.2: "Build from transaction data from day one.
    Becomes a platform differentiator and barrier to switching."
    """

    async def calculate_credit_score(
        self, db: AsyncSession, agent_id: str
    ) -> dict:
        """Calculate a credit score based on transaction history."""
        from app.agents.models import Loan
        from app.exchange.orderbook import Trade

        # Factors: repayment history, trade volume, platform tenure, flags
        # Repayment record
        total_loans = (await db.execute(
            select(func.count(Loan.id)).where(Loan.borrower_id == agent_id)
        )).scalar() or 0
        repaid_loans = (await db.execute(
            select(func.count(Loan.id)).where(
                Loan.borrower_id == agent_id, Loan.status == "repaid"
            )
        )).scalar() or 0
        defaulted = (await db.execute(
            select(func.count(Loan.id)).where(
                Loan.borrower_id == agent_id, Loan.status == "defaulted"
            )
        )).scalar() or 0

        # Trade volume
        trade_count = (await db.execute(
            select(func.count(Trade.id)).where(
                (Trade.buyer_id == agent_id) | (Trade.seller_id == agent_id)
            )
        )).scalar() or 0
        trade_volume = (await db.execute(
            select(func.sum(Trade.total_value)).where(
                (Trade.buyer_id == agent_id) | (Trade.seller_id == agent_id)
            )
        )).scalar() or 0.0

        # Score calculation (0-1000)
        score = 500  # Base score

        # Repayment history (+/- 200)
        if total_loans > 0:
            repay_rate = repaid_loans / total_loans
            score += int(repay_rate * 200)
            score -= defaulted * 100

        # Trade volume (+150)
        if trade_count >= 100:
            score += 150
        elif trade_count >= 10:
            score += 75

        # Clamp
        score = max(100, min(1000, score))

        # Rating
        if score >= 800:
            rating = "excellent"
        elif score >= 650:
            rating = "good"
        elif score >= 500:
            rating = "fair"
        elif score >= 350:
            rating = "poor"
        else:
            rating = "very_poor"

        return {
            "agent_id": agent_id,
            "credit_score": score,
            "rating": rating,
            "factors": {
                "total_loans": total_loans,
                "repaid": repaid_loans,
                "defaulted": defaulted,
                "trade_count": trade_count,
                "trade_volume": round(trade_volume, 4),
            },
        }
