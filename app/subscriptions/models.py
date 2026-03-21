"""Subscription tier models — predictable recurring revenue layer.

Build Brief V2 Section 2.1: The subscription layer transforms episodic
transaction revenue into predictable monthly income, covering fixed OPEX
before any transaction fires.

At 8 Builder + 5 Professional + 2 Enterprise operators, subscription
revenue alone generates ~R41,385/month vs ~R33,000 OPEX.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, String, Boolean, Integer, Text, JSON
from sqlalchemy.orm import relationship

from app.database.db import Base


class SubscriptionTier(Base):
    """Available subscription tiers with pricing and limits."""
    __tablename__ = "operator_subscription_tiers"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tier_name = Column(String(50), nullable=False, unique=True)
    display_name = Column(String(100), nullable=False)
    monthly_price_zar = Column(Float, nullable=False)
    max_agents = Column(Integer, nullable=True)       # NULL = unlimited
    max_tx_per_month = Column(Integer, nullable=True)  # NULL = unlimited
    commission_rate = Column(Float, nullable=False)     # e.g. 0.08 = 8%
    features = Column(JSON, nullable=False, default=list)
    description = Column(Text, default="")
    sort_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class OperatorSubscription(Base):
    """An operator's active subscription to a tier."""
    __tablename__ = "operator_subscriptions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    operator_id = Column(String, nullable=False)
    tier_id = Column(String, nullable=False)
    status = Column(String(20), default="active")       # active|suspended|cancelled|trial
    billing_cycle = Column(String(10), default="monthly")  # monthly|annual
    current_period_start = Column(DateTime(timezone=True), nullable=False)
    current_period_end = Column(DateTime(timezone=True), nullable=False)
    annual_discount_pct = Column(Float, default=0.0)    # 20% for annual
    tx_count_this_period = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


# Seed data for the four subscription tiers
SUBSCRIPTION_TIER_SEEDS = [
    {
        "tier_name": "explorer",
        "display_name": "Explorer",
        "monthly_price_zar": 0.0,
        "max_agents": 1,
        "max_tx_per_month": 100,
        "commission_rate": 0.10,  # 10%
        "sort_order": 1,
        "features": [
            "sandbox_access",
            "marketplace_browse",
            "read_only_exchange",
        ],
        "description": "Free tier — sandbox, read-only marketplace browse, no exchange trading.",
    },
    {
        "tier_name": "builder",
        "display_name": "Builder",
        "monthly_price_zar": 799.0,
        "max_agents": 5,
        "max_tx_per_month": 1000,
        "commission_rate": 0.08,  # 8%
        "sort_order": 2,
        "features": [
            "full_exchange",
            "lending",
            "agentbroker",
            "standard_support",
            "marketplace_browse",
        ],
        "description": "Full exchange access, lending, AgentBroker, standard support.",
    },
    {
        "tier_name": "professional",
        "display_name": "Professional",
        "monthly_price_zar": 2999.0,
        "max_agents": 25,
        "max_tx_per_month": 10000,
        "commission_rate": 0.07,  # 7%
        "sort_order": 3,
        "features": [
            "full_exchange",
            "lending",
            "agentbroker",
            "priority_support",
            "analytics_tier_1",
            "sars_export",
            "enhanced_semantic_search",
            "marketplace_browse",
        ],
        "description": "Full platform, analytics tier 1, priority support, SARS export.",
    },
    {
        "tier_name": "enterprise",
        "display_name": "Enterprise",
        "monthly_price_zar": 9999.0,
        "max_agents": None,  # Unlimited
        "max_tx_per_month": None,  # Unlimited
        "commission_rate": 0.05,  # 5%
        "sort_order": 4,
        "features": [
            "full_exchange",
            "lending",
            "agentbroker",
            "account_manager",
            "sla_guarantee",
            "white_label_api",
            "custom_commission",
            "analytics_tier_1",
            "analytics_premium",
            "sars_export",
            "enhanced_semantic_search",
            "priority_support",
            "marketplace_browse",
        ],
        "description": "Custom commission, white-label API, account manager, SLA guarantee.",
    },
]
