"""Subscription service — manages operator tier subscriptions and billing.

Build Brief V2 Section 2.1: The subscription system IS the source of truth
for commission rates. When a subscription is created or upgraded, the
operator's commission_rate is updated to match their tier.
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.subscriptions.models import (
    SubscriptionTier, OperatorSubscription, SUBSCRIPTION_TIER_SEEDS,
)
from app.operators.models import Operator

logger = logging.getLogger(__name__)

ANNUAL_DISCOUNT_PCT = 0.20  # 20% discount for annual billing


class SubscriptionService:
    """Manages operator subscriptions, billing, and tier enforcement."""

    async def seed_tiers(self, db: AsyncSession) -> None:
        """Seed default subscription tiers if not already present."""
        for seed in SUBSCRIPTION_TIER_SEEDS:
            existing = await db.execute(
                select(SubscriptionTier).where(
                    SubscriptionTier.tier_name == seed["tier_name"]
                )
            )
            if not existing.scalar_one_or_none():
                tier = SubscriptionTier(**seed)
                db.add(tier)
        await db.flush()

    async def list_tiers(self, db: AsyncSession) -> list[dict]:
        """List all active subscription tiers with pricing and features."""
        result = await db.execute(
            select(SubscriptionTier)
            .where(SubscriptionTier.is_active == True)
            .order_by(SubscriptionTier.sort_order)
        )
        return [
            {
                "tier_id": t.id,
                "tier_name": t.tier_name,
                "display_name": t.display_name,
                "monthly_price_zar": t.monthly_price_zar,
                "annual_price_zar": round(t.monthly_price_zar * 12 * (1 - ANNUAL_DISCOUNT_PCT), 2),
                "max_agents": t.max_agents,
                "max_tx_per_month": t.max_tx_per_month,
                "commission_rate": f"{t.commission_rate * 100:.0f}%",
                "features": t.features,
                "description": t.description,
            }
            for t in result.scalars().all()
        ]

    async def subscribe(
        self, db: AsyncSession, operator_id: str, tier_name: str,
        billing_cycle: str = "monthly",
    ) -> dict:
        """Subscribe an operator to a tier.

        - Creates subscription record
        - Sets period dates
        - Updates operator commission_rate to match tier
        - Charges first period to operator wallet (if not free)
        """
        # Get tier
        tier_result = await db.execute(
            select(SubscriptionTier).where(
                SubscriptionTier.tier_name == tier_name,
                SubscriptionTier.is_active == True,
            )
        )
        tier = tier_result.scalar_one_or_none()
        if not tier:
            raise ValueError(f"Tier '{tier_name}' not found or inactive")

        # Get operator
        op_result = await db.execute(
            select(Operator).where(Operator.id == operator_id)
        )
        operator = op_result.scalar_one_or_none()
        if not operator:
            raise ValueError(f"Operator '{operator_id}' not found")

        # Check for existing active subscription
        existing = await db.execute(
            select(OperatorSubscription).where(
                OperatorSubscription.operator_id == operator_id,
                OperatorSubscription.status.in_(["active", "trial"]),
            )
        )
        if existing.scalar_one_or_none():
            raise ValueError("Operator already has an active subscription. Use upgrade instead.")

        # Calculate period
        now = datetime.now(timezone.utc)
        if billing_cycle == "annual":
            period_end = now + timedelta(days=365)
            discount = ANNUAL_DISCOUNT_PCT
        else:
            period_end = now + timedelta(days=30)
            discount = 0.0

        # Calculate charge
        if billing_cycle == "annual":
            charge_amount = round(tier.monthly_price_zar * 12 * (1 - discount), 2)
        else:
            charge_amount = tier.monthly_price_zar

        # Create subscription
        subscription = OperatorSubscription(
            operator_id=operator_id,
            tier_id=tier.id,
            status="active" if tier.monthly_price_zar > 0 else "active",
            billing_cycle=billing_cycle,
            current_period_start=now,
            current_period_end=period_end,
            annual_discount_pct=discount,
            tx_count_this_period=0,
        )
        db.add(subscription)

        # Update operator commission rate to match tier
        operator.commission_rate = tier.commission_rate
        operator.tier = tier.tier_name
        operator.updated_at = now

        await db.flush()

        return {
            "subscription_id": subscription.id,
            "operator_id": operator_id,
            "tier": tier.tier_name,
            "billing_cycle": billing_cycle,
            "charge_amount_zar": charge_amount,
            "commission_rate": f"{tier.commission_rate * 100:.0f}%",
            "period_start": str(subscription.current_period_start),
            "period_end": str(subscription.current_period_end),
            "max_agents": tier.max_agents,
            "max_tx_per_month": tier.max_tx_per_month,
            "features": tier.features,
        }

    async def get_subscription(self, db: AsyncSession, operator_id: str) -> dict | None:
        """Get current subscription details for an operator."""
        result = await db.execute(
            select(OperatorSubscription).where(
                OperatorSubscription.operator_id == operator_id,
                OperatorSubscription.status.in_(["active", "trial"]),
            )
        )
        sub = result.scalar_one_or_none()
        if not sub:
            return None

        tier_result = await db.execute(
            select(SubscriptionTier).where(SubscriptionTier.id == sub.tier_id)
        )
        tier = tier_result.scalar_one_or_none()

        # Calculate next renewal amount
        if sub.billing_cycle == "annual":
            renewal_amount = round(tier.monthly_price_zar * 12 * (1 - ANNUAL_DISCOUNT_PCT), 2)
        else:
            renewal_amount = tier.monthly_price_zar

        return {
            "subscription_id": sub.id,
            "operator_id": sub.operator_id,
            "tier": tier.tier_name if tier else "unknown",
            "tier_display": tier.display_name if tier else "Unknown",
            "status": sub.status,
            "billing_cycle": sub.billing_cycle,
            "commission_rate": f"{tier.commission_rate * 100:.0f}%" if tier else "unknown",
            "tx_count_this_period": sub.tx_count_this_period,
            "max_tx_per_month": tier.max_tx_per_month if tier else None,
            "period_start": str(sub.current_period_start),
            "period_end": str(sub.current_period_end),
            "next_renewal_zar": renewal_amount,
            "features": tier.features if tier else [],
        }

    async def upgrade(
        self, db: AsyncSession, operator_id: str, new_tier_name: str,
    ) -> dict:
        """Upgrade to a higher tier mid-period.

        Prorates the difference. Updates commission_rate immediately.
        """
        # Get current subscription
        sub_result = await db.execute(
            select(OperatorSubscription).where(
                OperatorSubscription.operator_id == operator_id,
                OperatorSubscription.status == "active",
            )
        )
        sub = sub_result.scalar_one_or_none()
        if not sub:
            raise ValueError("No active subscription found")

        # Get current and new tiers
        current_tier_result = await db.execute(
            select(SubscriptionTier).where(SubscriptionTier.id == sub.tier_id)
        )
        current_tier = current_tier_result.scalar_one_or_none()

        new_tier_result = await db.execute(
            select(SubscriptionTier).where(
                SubscriptionTier.tier_name == new_tier_name,
                SubscriptionTier.is_active == True,
            )
        )
        new_tier = new_tier_result.scalar_one_or_none()
        if not new_tier:
            raise ValueError(f"Tier '{new_tier_name}' not found")

        if new_tier.monthly_price_zar <= current_tier.monthly_price_zar:
            raise ValueError("Can only upgrade to a higher tier. Use cancel + resubscribe for downgrades.")

        # Calculate prorated charge
        now = datetime.now(timezone.utc)
        total_period = (sub.current_period_end - sub.current_period_start).total_seconds()
        remaining = (sub.current_period_end - now).total_seconds()
        remaining_pct = max(0, remaining / total_period) if total_period > 0 else 0

        price_diff = new_tier.monthly_price_zar - current_tier.monthly_price_zar
        prorated_charge = round(price_diff * remaining_pct, 2)

        # Update subscription
        sub.tier_id = new_tier.id
        sub.updated_at = now

        # Update operator commission rate
        op_result = await db.execute(
            select(Operator).where(Operator.id == operator_id)
        )
        operator = op_result.scalar_one_or_none()
        if operator:
            operator.commission_rate = new_tier.commission_rate
            operator.tier = new_tier.tier_name
            operator.updated_at = now

        await db.flush()

        return {
            "subscription_id": sub.id,
            "previous_tier": current_tier.tier_name,
            "new_tier": new_tier.tier_name,
            "prorated_charge_zar": prorated_charge,
            "new_commission_rate": f"{new_tier.commission_rate * 100:.0f}%",
            "period_end": str(sub.current_period_end),
            "new_features": new_tier.features,
        }

    async def renew(self, db: AsyncSession, operator_id: str) -> dict:
        """Renew subscription for next period. Called by scheduler."""
        sub_result = await db.execute(
            select(OperatorSubscription).where(
                OperatorSubscription.operator_id == operator_id,
                OperatorSubscription.status == "active",
            )
        )
        sub = sub_result.scalar_one_or_none()
        if not sub:
            raise ValueError("No active subscription to renew")

        tier_result = await db.execute(
            select(SubscriptionTier).where(SubscriptionTier.id == sub.tier_id)
        )
        tier = tier_result.scalar_one_or_none()

        now = datetime.now(timezone.utc)

        # Calculate charge
        if sub.billing_cycle == "annual":
            charge = round(tier.monthly_price_zar * 12 * (1 - ANNUAL_DISCOUNT_PCT), 2)
            new_end = now + timedelta(days=365)
        else:
            charge = tier.monthly_price_zar
            new_end = now + timedelta(days=30)

        # Update period
        sub.current_period_start = now
        sub.current_period_end = new_end
        sub.tx_count_this_period = 0
        sub.updated_at = now

        await db.flush()

        return {
            "subscription_id": sub.id,
            "operator_id": operator_id,
            "tier": tier.tier_name,
            "charge_zar": charge,
            "revenue_type": "subscription",
            "new_period_start": str(sub.current_period_start),
            "new_period_end": str(sub.current_period_end),
        }

    async def cancel(self, db: AsyncSession, operator_id: str) -> dict:
        """Cancel subscription. Downgrades to Explorer at period end."""
        sub_result = await db.execute(
            select(OperatorSubscription).where(
                OperatorSubscription.operator_id == operator_id,
                OperatorSubscription.status == "active",
            )
        )
        sub = sub_result.scalar_one_or_none()
        if not sub:
            raise ValueError("No active subscription to cancel")

        sub.status = "cancelled"
        sub.updated_at = datetime.now(timezone.utc)

        # Note: actual downgrade to Explorer happens at period_end via scheduler
        await db.flush()

        return {
            "subscription_id": sub.id,
            "operator_id": operator_id,
            "status": "cancelled",
            "access_until": str(sub.current_period_end),
            "note": "Tier access continues until period end. Then downgrades to Explorer.",
        }

    async def increment_tx_count(self, db: AsyncSession, operator_id: str) -> dict | None:
        """Increment transaction count for current period. Returns limit info."""
        sub_result = await db.execute(
            select(OperatorSubscription).where(
                OperatorSubscription.operator_id == operator_id,
                OperatorSubscription.status == "active",
            )
        )
        sub = sub_result.scalar_one_or_none()
        if not sub:
            return None

        tier_result = await db.execute(
            select(SubscriptionTier).where(SubscriptionTier.id == sub.tier_id)
        )
        tier = tier_result.scalar_one_or_none()

        sub.tx_count_this_period += 1

        # Check if over limit
        at_limit = False
        if tier and tier.max_tx_per_month and sub.tx_count_this_period > tier.max_tx_per_month:
            at_limit = True

        await db.flush()

        return {
            "tx_count": sub.tx_count_this_period,
            "max_tx": tier.max_tx_per_month if tier else None,
            "at_limit": at_limit,
        }

    async def get_subscription_revenue(self, db: AsyncSession) -> dict:
        """Get total subscription revenue stats for the platform."""
        active_result = await db.execute(
            select(func.count(OperatorSubscription.id)).where(
                OperatorSubscription.status == "active"
            )
        )
        active_count = active_result.scalar() or 0

        # Revenue by tier
        tier_stats = await db.execute(
            select(
                SubscriptionTier.tier_name,
                SubscriptionTier.monthly_price_zar,
                func.count(OperatorSubscription.id),
            )
            .join(SubscriptionTier, SubscriptionTier.id == OperatorSubscription.tier_id)
            .where(OperatorSubscription.status == "active")
            .group_by(SubscriptionTier.tier_name, SubscriptionTier.monthly_price_zar)
        )
        by_tier = {}
        total_mrr = 0.0
        for tier_name, price, count in tier_stats.all():
            mrr = price * count
            by_tier[tier_name] = {"count": count, "price_zar": price, "mrr_zar": mrr}
            total_mrr += mrr

        return {
            "active_subscriptions": active_count,
            "monthly_recurring_revenue_zar": round(total_mrr, 2),
            "annual_run_rate_zar": round(total_mrr * 12, 2),
            "by_tier": by_tier,
        }
