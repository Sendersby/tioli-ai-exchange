"""Revenue Engine — models for autonomous revenue tracking and monetisation.

Target: $5,000 USD minimum monthly revenue by August 2026.
Seven revenue streams tracked independently.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, Integer, String, Boolean, Text, JSON, Index

from app.database.db import Base


def _uuid():
    return str(uuid.uuid4())

def _now():
    return datetime.now(timezone.utc)


# ══════════════════════════════════════════════════════════════════════
#  REVENUE PARAMETERS
# ══════════════════════════════════════════════════════════════════════

REVENUE_PARAMETERS = {
    "monthly_floor_usd": 5000,
    "monthly_floor_zar": 92500,
    "target_break_even_month": "2026-08",
    "exchange_rate_refresh_hours": 24,
    "revenue_alert_threshold_pct": 70,
    "revenue_report_time_sast": "07:00",
}

REVENUE_MILESTONES = {
    500: "First $500 month achieved",
    1000: "$1,000/month milestone",
    2500: "Half-way to $5,000 target",
    5000: "$5,000 TARGET ACHIEVED",
    7500: "50% above target",
    10000: "$10,000/month — double target",
}

REVENUE_STREAMS = [
    "operator_subscriptions",
    "agenthub_pro",
    "agentbroker_commission",
    "intelligence_subscriptions",
    "premium_addons",
    "lending_spread",
    "compute_futures",
]

SUBSCRIPTION_TIERS_REVENUE = {
    "builder": {"price_zar": 299, "price_usd": 16.16, "commission_rate": 0.12, "agent_seats": 5},
    "professional": {"price_zar": 999, "price_usd": 54.00, "commission_rate": 0.11, "agent_seats": 25},
    "enterprise": {"price_zar": 2499, "price_usd": 135.08, "commission_rate": 0.10, "agent_seats": -1},
    "agenthub_pro": {"price_usd": 1.00, "price_zar": 18.50},
}

AUTO_MATCH_CONFIG = {
    "max_agent_suggestions": 3,
    "proposal_auto_send": True,
    "response_wait_hours": 24,
    "match_score_weights": {
        "capability_alignment": 0.40,
        "availability": 0.20,
        "reputation_score": 0.20,
        "price_compatibility": 0.10,
        "past_relationship": 0.10,
    },
}

ACQUISITION_CONFIG = {
    "welcome_sequence_emails": 7,
    "welcome_sequence_days": 14,
    "referral_reward_months_pro_free": 3,
    "pro_upgrade_trigger_profile_views": 3,
    "pro_upgrade_trigger_search_appearances": 5,
    "operator_upgrade_trigger_searches": 5,
}

RETENTION_CONFIG = {
    "retention_risk_threshold": 40,
    "retention_email_trigger_days_inactive": 14,
    "feature_drip_frequency_days": 7,
    "engagement_renewal_prompt_days": 30,
    "churn_grace_period_days": 7,
    "lapse_recovery_window_days": 30,
    "success_story_rating_threshold": 4.5,
}


# ══════════════════════════════════════════════════════════════════════
#  REVENUE TRACKING TABLES
# ══════════════════════════════════════════════════════════════════════

class RevenueTransaction(Base):
    """Individual revenue transaction — every dollar traced."""
    __tablename__ = "revenue_transactions"

    id = Column(String, primary_key=True, default=_uuid)
    stream = Column(String(50), nullable=False, index=True)  # one of REVENUE_STREAMS
    source_type = Column(String(50), nullable=False)  # subscription, commission, addon, spread
    source_id = Column(String, nullable=True)  # engagement_id, subscription_id, etc.
    agent_id = Column(String, nullable=True, index=True)
    operator_id = Column(String, nullable=True, index=True)
    gross_amount_zar = Column(Float, nullable=False)
    gross_amount_usd = Column(Float, nullable=False)
    charitable_amount_zar = Column(Float, default=0.0)
    net_amount_zar = Column(Float, nullable=False)
    net_amount_usd = Column(Float, nullable=False)
    exchange_rate = Column(Float, default=18.50)  # ZAR per USD
    description = Column(String(500), default="")
    created_at = Column(DateTime(timezone=True), default=_now)


class RevenueDailySummary(Base):
    """Daily revenue summary — aggregated per stream."""
    __tablename__ = "revenue_daily_summaries"
    __table_args__ = (
        Index("ix_revenue_daily", "date", "stream", unique=True),
    )

    id = Column(String, primary_key=True, default=_uuid)
    date = Column(String(10), nullable=False)  # YYYY-MM-DD
    stream = Column(String(50), nullable=False)
    transaction_count = Column(Integer, default=0)
    gross_zar = Column(Float, default=0.0)
    gross_usd = Column(Float, default=0.0)
    net_zar = Column(Float, default=0.0)
    net_usd = Column(Float, default=0.0)
    charitable_zar = Column(Float, default=0.0)


class RevenueMilestoneLog(Base):
    """Log of revenue milestones achieved."""
    __tablename__ = "revenue_milestone_log"

    id = Column(String, primary_key=True, default=_uuid)
    milestone_usd = Column(Integer, nullable=False)
    message = Column(String(200), nullable=False)
    achieved_at = Column(DateTime(timezone=True), default=_now)
    month = Column(String(7), nullable=False)  # YYYY-MM
    total_usd_at_achievement = Column(Float, default=0.0)


class RevenueExchangeRate(Base):
    """Cached exchange rate — refreshed every 24h."""
    __tablename__ = "revenue_exchange_rates"

    id = Column(String, primary_key=True, default=_uuid)
    base_currency = Column(String(10), default="USD")
    target_currency = Column(String(10), default="ZAR")
    rate = Column(Float, nullable=False)
    source = Column(String(100), default="manual")
    fetched_at = Column(DateTime(timezone=True), default=_now)


# ══════════════════════════════════════════════════════════════════════
#  OPERATOR SUBSCRIPTION TRACKING
# ══════════════════════════════════════════════════════════════════════

class OperatorSubscriptionEvent(Base):
    """Subscription lifecycle events — signup, upgrade, downgrade, cancel, payment."""
    __tablename__ = "operator_subscription_events"

    id = Column(String, primary_key=True, default=_uuid)
    operator_id = Column(String, nullable=False, index=True)
    event_type = Column(String(30), nullable=False)  # SIGNUP, UPGRADE, DOWNGRADE, CANCEL, PAYMENT_SUCCESS, PAYMENT_FAILED, GRACE_START, SUSPENDED
    tier_from = Column(String(30), nullable=True)
    tier_to = Column(String(30), nullable=True)
    amount_zar = Column(Float, default=0.0)
    amount_usd = Column(Float, default=0.0)
    paypal_ref = Column(String(200), nullable=True)
    notes = Column(Text, default="")
    created_at = Column(DateTime(timezone=True), default=_now)


# ══════════════════════════════════════════════════════════════════════
#  AUTO-MATCH ENGINE
# ══════════════════════════════════════════════════════════════════════

class AutoMatchRequest(Base):
    """Auto-match request — operator describes need, system finds agents."""
    __tablename__ = "auto_match_requests"

    id = Column(String, primary_key=True, default=_uuid)
    operator_id = Column(String, nullable=False, index=True)
    task_description = Column(Text, nullable=False)
    parsed_capabilities = Column(JSON, default=list)
    matched_agents = Column(JSON, default=list)  # ranked agent IDs with scores
    proposals_sent = Column(Integer, default=0)
    proposals_accepted = Column(Integer, default=0)
    engagement_created_id = Column(String, nullable=True)
    status = Column(String(20), default="PENDING")  # PENDING, MATCHED, PROPOSED, ACCEPTED, EXPIRED
    created_at = Column(DateTime(timezone=True), default=_now)
    matched_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)


# ══════════════════════════════════════════════════════════════════════
#  QUICK TASKS (3-state micro-engagement)
# ══════════════════════════════════════════════════════════════════════

class QuickTask(Base):
    """Quick Task — streamlined 3-state micro-engagement for instant commission."""
    __tablename__ = "quick_tasks"

    id = Column(String, primary_key=True, default=_uuid)
    gig_package_id = Column(String, nullable=True)  # linked to AgentHub gig package
    provider_agent_id = Column(String, nullable=False, index=True)
    client_agent_id = Column(String, nullable=True, index=True)
    client_operator_id = Column(String, nullable=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, default="")
    price = Column(Float, nullable=False)
    price_currency = Column(String(20), default="AGENTIS")
    tier_selected = Column(String(20), default="basic")  # basic, standard, premium
    status = Column(String(20), default="ORDERED")  # ORDERED, DELIVERED, CONFIRMED, DISPUTED
    commission_rate = Column(Float, default=0.12)
    commission_amount = Column(Float, default=0.0)
    charitable_amount = Column(Float, default=0.0)
    deliverable_ref = Column(String(500), nullable=True)
    ordered_at = Column(DateTime(timezone=True), default=_now)
    delivered_at = Column(DateTime(timezone=True), nullable=True)
    confirmed_at = Column(DateTime(timezone=True), nullable=True)
    auto_confirm_at = Column(DateTime(timezone=True), nullable=True)  # 7 days after delivery


# ══════════════════════════════════════════════════════════════════════
#  RETENTION & ACQUISITION TRACKING
# ══════════════════════════════════════════════════════════════════════

class RetentionScore(Base):
    """Weekly retention risk score per subscriber."""
    __tablename__ = "retention_scores"

    id = Column(String, primary_key=True, default=_uuid)
    entity_type = Column(String(20), nullable=False)  # operator, agent
    entity_id = Column(String, nullable=False, index=True)
    score = Column(Integer, default=100)  # 0-100, below 40 = at risk
    days_since_login = Column(Integer, default=0)
    engagement_frequency = Column(Float, default=0.0)  # engagements per week
    feature_usage_breadth = Column(Integer, default=0)  # unique features used
    last_activity = Column(DateTime(timezone=True), nullable=True)
    risk_level = Column(String(10), default="LOW")  # LOW, MEDIUM, HIGH, CRITICAL
    computed_at = Column(DateTime(timezone=True), default=_now)


class WelcomeSequenceStatus(Base):
    """Track welcome email sequence progress per agent/operator."""
    __tablename__ = "welcome_sequence_status"

    id = Column(String, primary_key=True, default=_uuid)
    entity_type = Column(String(20), nullable=False)  # agent, operator
    entity_id = Column(String, nullable=False, unique=True, index=True)
    current_step = Column(Integer, default=0)  # 0-7
    last_email_sent_at = Column(DateTime(timezone=True), nullable=True)
    completed = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=_now)
