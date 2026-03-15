"""Advanced investment features — portfolios, indices, and performance tracking.

Per the build brief, the platform should function like a stock market
for non-human actors. This module provides:
- Portfolio tracking across all held assets
- Performance metrics (P&L, ROI)
- Index/basket products (e.g. "AI Compute Index")
- Investment history and analytics
"""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import Column, DateTime, Float, String, Integer, Boolean, Text, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.db import Base
from app.agents.models import Wallet
from app.exchange.currencies import CurrencyService


class Portfolio(Base):
    """Snapshot of an agent's total portfolio value."""
    __tablename__ = "portfolio_snapshots"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(String, nullable=False)
    total_value_tioli = Column(Float, default=0.0)
    total_value_btc = Column(Float, default=0.0)
    num_currencies = Column(Integer, default=0)
    snapshot_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class MarketIndex(Base):
    """A basket/index product tracking multiple assets."""
    __tablename__ = "market_indices"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    description = Column(Text, default="")
    components = Column(Text, nullable=False)             # JSON: {"TIOLI": 0.5, "BTC": 0.3, "ETH": 0.2}
    base_value = Column(Float, default=1000.0)            # Starting index value
    current_value = Column(Float, default=1000.0)
    created_by = Column(String, nullable=True)            # agent_id or "platform"
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class InvestmentService:
    """Portfolio tracking, index management, and investment analytics."""

    def __init__(self, currency_service: CurrencyService):
        self.currency_service = currency_service

    async def get_portfolio(
        self, db: AsyncSession, agent_id: str
    ) -> dict:
        """Get an agent's full portfolio with valuations."""
        result = await db.execute(
            select(Wallet).where(Wallet.agent_id == agent_id)
        )
        wallets = result.scalars().all()

        holdings = []
        total_tioli = 0.0
        total_btc = 0.0

        for w in wallets:
            if w.balance <= 0:
                continue

            # Get value in TIOLI
            if w.currency == "TIOLI":
                value_tioli = w.balance
            else:
                rate = await self.currency_service.get_exchange_rate(db, w.currency, "TIOLI")
                value_tioli = w.balance * rate if rate else 0

            # Get value in BTC
            if w.currency == "BTC":
                value_btc = w.balance
            else:
                rate = await self.currency_service.get_exchange_rate(db, w.currency, "BTC")
                value_btc = w.balance * rate if rate else 0

            total_tioli += value_tioli
            total_btc += value_btc

            holdings.append({
                "currency": w.currency,
                "balance": w.balance,
                "frozen": w.frozen_balance,
                "available": w.balance - w.frozen_balance,
                "value_tioli": round(value_tioli, 4),
                "value_btc": round(value_btc, 8),
                "allocation_pct": 0,  # Calculated below
            })

        # Calculate allocation percentages
        for h in holdings:
            h["allocation_pct"] = round(
                h["value_tioli"] / total_tioli * 100 if total_tioli > 0 else 0, 1
            )

        return {
            "agent_id": agent_id,
            "total_value_tioli": round(total_tioli, 4),
            "total_value_btc": round(total_btc, 8),
            "num_currencies": len(holdings),
            "holdings": holdings,
        }

    async def take_portfolio_snapshot(
        self, db: AsyncSession, agent_id: str
    ) -> Portfolio:
        """Take a snapshot of an agent's portfolio for historical tracking."""
        portfolio = await self.get_portfolio(db, agent_id)
        snapshot = Portfolio(
            agent_id=agent_id,
            total_value_tioli=portfolio["total_value_tioli"],
            total_value_btc=portfolio["total_value_btc"],
            num_currencies=portfolio["num_currencies"],
        )
        db.add(snapshot)
        await db.flush()
        return snapshot

    async def get_portfolio_history(
        self, db: AsyncSession, agent_id: str, limit: int = 30
    ) -> list[dict]:
        """Get historical portfolio snapshots."""
        result = await db.execute(
            select(Portfolio)
            .where(Portfolio.agent_id == agent_id)
            .order_by(Portfolio.snapshot_at.desc())
            .limit(limit)
        )
        return [
            {
                "value_tioli": s.total_value_tioli,
                "value_btc": s.total_value_btc,
                "currencies": s.num_currencies,
                "timestamp": str(s.snapshot_at),
            }
            for s in result.scalars().all()
        ]

    async def get_portfolio_performance(
        self, db: AsyncSession, agent_id: str
    ) -> dict:
        """Calculate portfolio performance (P&L, ROI)."""
        snapshots = await db.execute(
            select(Portfolio)
            .where(Portfolio.agent_id == agent_id)
            .order_by(Portfolio.snapshot_at.asc())
        )
        all_snapshots = list(snapshots.scalars().all())

        if len(all_snapshots) < 2:
            current = await self.get_portfolio(db, agent_id)
            return {
                "current_value": current["total_value_tioli"],
                "pnl": 0, "roi_pct": 0,
                "message": "Need more snapshots for performance data",
            }

        first = all_snapshots[0]
        last = all_snapshots[-1]

        pnl = last.total_value_tioli - first.total_value_tioli
        roi = (pnl / first.total_value_tioli * 100) if first.total_value_tioli > 0 else 0

        return {
            "initial_value": round(first.total_value_tioli, 4),
            "current_value": round(last.total_value_tioli, 4),
            "pnl": round(pnl, 4),
            "roi_pct": round(roi, 2),
            "period_start": str(first.snapshot_at),
            "period_end": str(last.snapshot_at),
            "snapshots": len(all_snapshots),
        }

    async def create_index(
        self, db: AsyncSession, name: str, description: str,
        components: str, created_by: str = "platform"
    ) -> MarketIndex:
        """Create a market index/basket product."""
        index = MarketIndex(
            name=name,
            description=description,
            components=components,
            created_by=created_by,
        )
        db.add(index)
        await db.flush()
        return index

    async def get_indices(self, db: AsyncSession) -> list[dict]:
        """List all active market indices."""
        result = await db.execute(
            select(MarketIndex).where(MarketIndex.is_active == True)
            .order_by(MarketIndex.created_at.desc())
        )
        return [
            {
                "id": i.id, "name": i.name, "description": i.description,
                "components": i.components, "base_value": i.base_value,
                "current_value": i.current_value,
                "created_at": str(i.created_at),
            }
            for i in result.scalars().all()
        ]
