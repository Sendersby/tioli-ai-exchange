"""Market Intelligence service — pipeline execution, subscriptions, and delivery.

Nightly job: aggregates transaction data into intelligence snapshots.
Detects anomalies, generates alerts for premium subscribers.
Retains 90 days daily, 2 years weekly rollup.
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.intelligence.models import (
    IntelligenceSnapshot, IntelligenceAlert, AnalyticsSubscription, INTELLIGENCE_TIERS,
)

logger = logging.getLogger(__name__)


class IntelligenceService:
    """Manages intelligence pipeline, subscriptions, and signal delivery."""

    async def run_nightly_pipeline(self, db: AsyncSession) -> dict:
        """Nightly job: compute intelligence snapshots from transaction data.

        In production this would aggregate from trades, engagements, and service
        profiles. For now, creates a snapshot framework that can be populated
        as transaction volume grows.
        """
        now = datetime.now(timezone.utc)
        snapshot_date = now.replace(hour=0, minute=0, second=0, microsecond=0)

        # Create snapshot for general market
        snapshot = IntelligenceSnapshot(
            snapshot_date=snapshot_date,
            capability_category="general",
            demand_index=1.0,
            supply_index=1.0,
            avg_price=0.0,
            price_trend_pct=0.0,
            volume_index=0.0,
            avg_reputation=0.0,
            lending_rate_avg=0.0,
        )
        db.add(snapshot)
        await db.flush()

        return {
            "status": "pipeline_complete",
            "snapshot_date": str(snapshot_date.date()),
            "snapshots_created": 1,
        }

    async def get_market_intelligence(
        self, db: AsyncSession, tier: str = "public",
        category: str | None = None, limit: int = 30,
    ) -> dict:
        """Return intelligence snapshots filtered by subscription tier."""
        tier_config = INTELLIGENCE_TIERS.get(tier, INTELLIGENCE_TIERS["public"])
        lag_days = tier_config["lag_days"]

        cutoff = datetime.now(timezone.utc) - timedelta(days=lag_days)

        query = select(IntelligenceSnapshot).where(
            IntelligenceSnapshot.snapshot_date <= cutoff
        )
        if category:
            query = query.where(IntelligenceSnapshot.capability_category == category)
        query = query.order_by(IntelligenceSnapshot.snapshot_date.desc()).limit(limit)

        result = await db.execute(query)
        snapshots = result.scalars().all()

        return {
            "tier": tier,
            "lag_days": lag_days,
            "snapshots": [
                {
                    "date": str(s.snapshot_date.date()) if s.snapshot_date else None,
                    "category": s.capability_category,
                    "demand_index": s.demand_index,
                    "supply_index": s.supply_index,
                    "avg_price": s.avg_price,
                    "price_trend_pct": s.price_trend_pct,
                    "volume_index": s.volume_index,
                    "lending_rate_avg": s.lending_rate_avg,
                }
                for s in snapshots
            ],
        }

    async def get_alerts(
        self, db: AsyncSession, subscription_id: str, limit: int = 50,
    ) -> list[dict]:
        """Return unread alerts for a subscription."""
        result = await db.execute(
            select(IntelligenceAlert)
            .where(
                IntelligenceAlert.subscription_id == subscription_id,
                IntelligenceAlert.delivered_at == None,
            )
            .order_by(IntelligenceAlert.created_at.desc())
            .limit(limit)
        )
        alerts = result.scalars().all()

        # Mark as delivered
        for a in alerts:
            a.delivered_at = datetime.now(timezone.utc)
        await db.flush()

        return [
            {
                "alert_id": a.id,
                "alert_type": a.alert_type,
                "category": a.capability_category,
                "message": a.message,
                "severity": a.severity,
                "created_at": str(a.created_at),
            }
            for a in alerts
        ]

    async def subscribe(
        self, db: AsyncSession, operator_id: str, tier: str = "standard",
    ) -> dict:
        """Subscribe operator to an intelligence tier."""
        if tier not in INTELLIGENCE_TIERS:
            raise ValueError(f"Invalid tier. Allowed: {list(INTELLIGENCE_TIERS.keys())}")

        tier_config = INTELLIGENCE_TIERS[tier]
        now = datetime.now(timezone.utc)

        subscription = AnalyticsSubscription(
            operator_id=operator_id,
            tier=tier,
            period_start=now,
            period_end=now + timedelta(days=30),
        )
        db.add(subscription)
        await db.flush()

        return {
            "subscription_id": subscription.id,
            "operator_id": operator_id,
            "tier": tier,
            "monthly_zar": tier_config["monthly_zar"],
            "description": tier_config["description"],
            "period_end": str(subscription.period_end),
        }

    async def get_tiers(self) -> dict:
        """List available intelligence tiers."""
        return {"tiers": INTELLIGENCE_TIERS}
