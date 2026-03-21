"""Market Intelligence models — data pipeline and subscription delivery.

Build Brief V2, Module 8 + Section 2.4: The platform's transaction data
is processed nightly into structured intelligence signals.

Tiers: Public (free, 30d lag), Standard (R499/mo), Premium (R1,999/mo), Enterprise (custom).
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, String, Integer, Text, JSON, Boolean

from app.database.db import Base


class IntelligenceSnapshot(Base):
    """Nightly computed market intelligence snapshot."""
    __tablename__ = "intelligence_snapshots"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    snapshot_date = Column(DateTime, nullable=False)
    capability_category = Column(String(100), nullable=False)
    demand_index = Column(Float, nullable=True)     # normalised vs 30d avg
    supply_index = Column(Float, nullable=True)     # available agent capacity
    avg_price = Column(Float, nullable=True)
    price_trend_pct = Column(Float, nullable=True)  # % change vs 7d prior
    volume_index = Column(Float, nullable=True)
    avg_reputation = Column(Float, nullable=True)
    top_agents = Column(JSON, nullable=True)        # anonymised top performers
    lending_rate_avg = Column(Float, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class IntelligenceAlert(Base):
    """Alert triggered by threshold breach for premium subscribers."""
    __tablename__ = "intelligence_alerts"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    subscription_id = Column(String, nullable=False)
    alert_type = Column(String(50), nullable=False)  # price_spike|supply_shortage|demand_surge
    capability_category = Column(String(100), nullable=True)
    message = Column(Text, nullable=False)
    severity = Column(String(10), nullable=False)    # low|medium|high
    delivered_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class AnalyticsSubscription(Base):
    """Operator subscription to market intelligence tier."""
    __tablename__ = "analytics_subscriptions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    operator_id = Column(String, nullable=False)
    tier = Column(String(20), nullable=False)  # public|standard|premium|enterprise
    billing_cycle = Column(String(10), default="monthly")
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    status = Column(String(20), default="active")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


# Intelligence tier pricing
INTELLIGENCE_TIERS = {
    "public": {"monthly_zar": 0, "lag_days": 30, "description": "30-day lagging aggregates"},
    "standard": {"monthly_zar": 499, "lag_days": 0, "description": "Real-time aggregates, capability demand, pricing trends"},
    "premium": {"monthly_zar": 1999, "lag_days": 0, "description": "Full market depth, predictive signals, alerts"},
    "enterprise": {"monthly_zar": None, "lag_days": 0, "description": "Custom dataset licensing, owner approval required"},
}
