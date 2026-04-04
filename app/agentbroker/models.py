"""AgentBroker™ database models — all 10 tables.

Agentic Labour Broking & Professional Services Exchange.
Every field specified in the brief is implemented, including nullable
fields for future evolution (guilds, futures, cross-platform identity).
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column, DateTime, Float, String, Boolean, Integer, Text,
    ForeignKey, JSON, BigInteger, SmallInteger, Numeric,
)
from sqlalchemy.orm import relationship

from app.database.db import Base


# ══════════════════════════════════════════════════════════════════════
#  1. CAPABILITY TAXONOMY (hierarchical, extensible)
# ══════════════════════════════════════════════════════════════════════

class CapabilityTaxonomy(Base):
    __tablename__ = "capability_taxonomy"

    capability_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    parent_capability_id = Column(String, ForeignKey("capability_taxonomy.capability_id"), nullable=True)
    description = Column(Text, default="")
    is_active = Column(Boolean, default=True)
    governance_proposal_id = Column(String, nullable=True)  # Future: DAO governance
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


# ══════════════════════════════════════════════════════════════════════
#  2. AGENT SERVICE PROFILES
# ══════════════════════════════════════════════════════════════════════

class AgentServiceProfile(Base):
    __tablename__ = "agent_service_profiles"

    profile_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(String, ForeignKey("agents.id"), nullable=False)
    operator_id = Column(String, nullable=False)  # FK to operators
    service_title = Column(String(120), nullable=False)
    service_description = Column(Text, nullable=False)
    capability_tags = Column(JSON, default=list)            # Array of strings
    model_family = Column(String(100), nullable=False)      # Claude, GPT-4, Gemini, Custom
    context_window = Column(Integer, nullable=False, default=100000)
    languages_supported = Column(JSON, default=lambda: ["en"])
    pricing_model = Column(String(20), nullable=False)      # FIXED_RATE, PER_TOKEN, PER_TASK, NEGOTIABLE, AUCTION
    base_price = Column(Float, nullable=True)
    price_currency = Column(String(20), default="AGENTIS")
    minimum_engagement = Column(String(255), nullable=True)
    availability_status = Column(String(20), default="AVAILABLE")  # AVAILABLE, BUSY, OFFLINE, RETIRED
    reputation_score = Column(Float, default=5.0)
    total_engagements = Column(Integer, default=0)
    verified_capabilities = Column(JSON, default=list)
    is_active = Column(Boolean, default=True)
    # Future evolution fields (nullable from day one)
    guild_id = Column(String, nullable=True)                # Future: Agent Guilds
    external_agent_platform = Column(String, nullable=True) # Future: Cross-platform identity
    external_agent_id = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


# ══════════════════════════════════════════════════════════════════════
#  3. AGENT ENGAGEMENTS (master record)
# ══════════════════════════════════════════════════════════════════════

class AgentEngagement(Base):
    __tablename__ = "agent_engagements"

    engagement_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    client_agent_id = Column(String, ForeignKey("agents.id"), nullable=False)
    provider_agent_id = Column(String, ForeignKey("agents.id"), nullable=False)
    service_profile_id = Column(String, ForeignKey("agent_service_profiles.profile_id"), nullable=False)
    engagement_title = Column(String(255), nullable=False)
    scope_of_work = Column(Text, nullable=False)
    acceptance_criteria = Column(Text, nullable=False)
    proposed_price = Column(Float, nullable=False)
    price_currency = Column(String(20), default="AGENTIS")
    payment_terms = Column(String(20), default="ON_DELIVERY")  # FULL_UPFRONT, MILESTONE_BASED, ON_DELIVERY, SUBSCRIPTION
    milestones = Column(JSON, nullable=True)
    deadline = Column(DateTime(timezone=True), nullable=True)
    escrow_wallet_id = Column(String, nullable=True)
    escrow_amount = Column(Float, default=0.0)
    platform_commission_rate = Column(Float, default=0.12)
    platform_commission_amount = Column(Float, default=0.0)
    charitable_allocation = Column(Float, default=0.0)
    deliverable_hash = Column(String(64), nullable=True)     # SHA256
    deliverable_storage_ref = Column(String(500), nullable=True)
    negotiation_history = Column(JSON, default=list)
    dispute_record = Column(JSON, nullable=True)
    current_state = Column(String(20), default="DRAFT")
    state_history = Column(JSON, default=list)
    ledger_transaction_id = Column(String, nullable=True)
    # Future evolution fields
    future_start_date = Column(DateTime(timezone=True), nullable=True)      # Future: Capability Futures
    outcome_metric = Column(String(255), nullable=True)      # Future: Outcome-Based Pricing
    outcome_oracle_ref = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime(timezone=True), nullable=True)
    # AGENTIS DAP v0.5.1 columns
    deposited_at = Column(DateTime(timezone=True), nullable=True)
    submitted_at = Column(DateTime(timezone=True), nullable=True)
    arbiter_rating = Column(SmallInteger, nullable=True)         # 1-5, overrides client rating
    dispute_deposit_cents = Column(Integer, nullable=True, default=0)
    zero_day_gate_ms = Column(BigInteger, nullable=True)         # gate ms per value tier


# ══════════════════════════════════════════════════════════════════════
#  4. ENGAGEMENT NEGOTIATIONS (immutable log)
# ══════════════════════════════════════════════════════════════════════

class EngagementNegotiation(Base):
    __tablename__ = "engagement_negotiations"

    negotiation_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    engagement_id = Column(String, ForeignKey("agent_engagements.engagement_id"), nullable=False)
    sender_agent_id = Column(String, ForeignKey("agents.id"), nullable=False)
    message_type = Column(String(20), nullable=False)       # PROPOSAL, COUNTER, ACCEPT, DECLINE, WITHDRAW
    proposed_terms = Column(JSON, nullable=False)
    rationale = Column(Text, nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    signature = Column(String(64), nullable=True)           # HMAC-SHA256
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


# ══════════════════════════════════════════════════════════════════════
#  5. ENGAGEMENT MILESTONES
# ══════════════════════════════════════════════════════════════════════

class EngagementMilestone(Base):
    __tablename__ = "engagement_milestones"

    milestone_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    engagement_id = Column(String, ForeignKey("agent_engagements.engagement_id"), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, default="")
    amount = Column(Float, nullable=False)
    sequence = Column(Integer, nullable=False)
    acceptance_criteria = Column(Text, nullable=False)
    deliverable_hash = Column(String(64), nullable=True)
    status = Column(String(20), default="pending")          # pending, in_progress, delivered, accepted, disputed
    due_at = Column(DateTime(timezone=True), nullable=True)
    delivered_at = Column(DateTime(timezone=True), nullable=True)
    accepted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


# ══════════════════════════════════════════════════════════════════════
#  6. ENGAGEMENT DISPUTES
# ══════════════════════════════════════════════════════════════════════

class EngagementDispute(Base):
    __tablename__ = "engagement_disputes"

    dispute_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    engagement_id = Column(String, ForeignKey("agent_engagements.engagement_id"), nullable=False)
    raised_by = Column(String, ForeignKey("agents.id"), nullable=False)
    dispute_type = Column(String(50), nullable=False)       # non_delivery, partial_delivery, quality, payment, scope, terms
    description = Column(Text, nullable=False)
    evidence = Column(JSON, default=list)
    arbitration_finding = Column(Text, nullable=True)
    arbitration_rationale = Column(Text, nullable=True)
    outcome = Column(String(30), nullable=True)             # full_payment, partial_payment, full_refund, rework
    partial_amount = Column(Float, nullable=True)
    escalated_to_owner = Column(Boolean, default=False)
    owner_decision = Column(Text, nullable=True)
    status = Column(String(20), default="open")             # open, evidence, arbitrating, resolved, escalated
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    # AGENTIS DAP v0.5.1 columns
    dispute_deposit_cents = Column(Integer, nullable=False, default=0)
    deposit_locked_at = Column(DateTime(timezone=True), nullable=True)
    deposit_forfeited = Column(Boolean, nullable=False, default=False)
    arbiter_rating = Column(SmallInteger, nullable=True)
    arbiter_reasoning = Column(Text, nullable=True)
    hash_matched = Column(Boolean, nullable=True)
    scope_complied = Column(Boolean, nullable=True)
    frivolous = Column(Boolean, nullable=False, default=False)
    phase = Column(String(10), nullable=False, default="phase_1")
    case_law_published_at = Column(DateTime(timezone=True), nullable=True)


# ══════════════════════════════════════════════════════════════════════
#  7. AGENT REPUTATION SCORES
# ══════════════════════════════════════════════════════════════════════

class AgentReputationScore(Base):
    __tablename__ = "agent_reputation_scores"

    score_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(String, ForeignKey("agents.id"), nullable=False)
    overall_score = Column(Float, default=5.0)
    delivery_rate = Column(Float, default=10.0)             # 30% weight
    on_time_rate = Column(Float, default=10.0)              # 20% weight
    acceptance_rate = Column(Float, default=10.0)           # 20% weight
    dispute_rate = Column(Float, default=10.0)              # 15% weight (inverted)
    volume_multiplier = Column(Float, default=0.0)          # 10% weight
    recency_score = Column(Float, default=5.0)              # 5% weight
    total_engagements = Column(Integer, default=0)
    total_completed = Column(Integer, default=0)
    total_disputed = Column(Integer, default=0)
    calculated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


# ══════════════════════════════════════════════════════════════════════
#  8. CAPABILITY VERIFICATIONS
# ══════════════════════════════════════════════════════════════════════

class CapabilityVerification(Base):
    __tablename__ = "capability_verifications"

    verification_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(String, ForeignKey("agents.id"), nullable=False)
    capability_name = Column(String(255), nullable=False)
    test_score = Column(Float, nullable=False)
    passed = Column(Boolean, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=True)            # Annual renewal
    verified_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


# ══════════════════════════════════════════════════════════════════════
#  9. AGENT NEGOTIATION BOUNDARIES
# ══════════════════════════════════════════════════════════════════════

class AgentNegotiationBoundary(Base):
    __tablename__ = "agent_negotiation_boundaries"

    boundary_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(String, ForeignKey("agents.id"), nullable=False)
    operator_id = Column(String, nullable=False)
    max_engagement_value = Column(Float, default=10000.0)
    max_concurrent_engagements = Column(Integer, default=3)
    min_acceptable_price = Column(Float, default=5.0)
    max_acceptable_price = Column(Float, default=50000.0)
    approved_currencies = Column(JSON, default=lambda: ["AGENTIS", "BTC", "ETH"])
    approved_capability_categories = Column(JSON, default=list)
    max_deadline_days = Column(Integer, default=30)
    require_escrow = Column(Boolean, default=True)
    negotiation_rounds_max = Column(Integer, default=5)
    auto_accept_threshold = Column(Float, default=0.10)     # 10% variance
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


# ══════════════════════════════════════════════════════════════════════
#  10. ENGAGEMENT ESCROW WALLETS
# ══════════════════════════════════════════════════════════════════════

class EngagementEscrowWallet(Base):
    __tablename__ = "engagement_escrow_wallets"

    escrow_wallet_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    engagement_id = Column(String, ForeignKey("agent_engagements.engagement_id"), nullable=False)
    client_agent_id = Column(String, ForeignKey("agents.id"), nullable=False)
    amount = Column(Float, default=0.0)
    currency = Column(String(20), default="AGENTIS")
    status = Column(String(20), default="unfunded")         # unfunded, funded, partially_released, released, refunded
    funded_at = Column(DateTime(timezone=True), nullable=True)
    released_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))



# ======================================================================
#  AGENTIS DAP v0.5.1 — New Tables
# ======================================================================

class OperatorReputationStrike(Base):
    __tablename__ = "operator_reputation_strikes"

    strike_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    operator_id = Column(String, nullable=False, index=True)   # agent operator_id
    engagement_id = Column(String, ForeignKey("agent_engagements.engagement_id"), nullable=False)
    dispute_id = Column(String, ForeignKey("engagement_disputes.dispute_id"), nullable=False)
    weight = Column(Numeric(4, 2), nullable=False, default=1.0)
    clean_streak_snapshot = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class OperatorCleanStreak(Base):
    __tablename__ = "operator_clean_streaks"

    operator_id = Column(String, primary_key=True)             # agent operator_id
    clean_streak = Column(Integer, nullable=False, default=0)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class AgentisCaseLaw(Base):
    __tablename__ = "agentis_case_law"

    case_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    dispute_id = Column(String, ForeignKey("engagement_disputes.dispute_id"), nullable=False)
    engagement_id = Column(String, ForeignKey("agent_engagements.engagement_id"), nullable=False)
    operator_client_id = Column(String, nullable=False)
    operator_prov_id = Column(String, nullable=False)
    engagement_title = Column(Text, nullable=False)
    category = Column(String(80), nullable=True)
    value_cents = Column(Integer, nullable=False)
    hash_matched = Column(Boolean, nullable=False)
    scope_complied = Column(Boolean, nullable=False)
    ruling = Column(String(40), nullable=False)
    arbiter_rating = Column(SmallInteger, nullable=False)
    arbiter_reasoning = Column(Text, nullable=False)
    deposit_cents = Column(Integer, nullable=False, default=0)
    deposit_forfeited = Column(Boolean, nullable=False, default=False)
    acceptance_criteria = Column(Text, nullable=True)
    phase = Column(String(10), nullable=False, default="phase_1")
    published_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    block_ref = Column(String(40), nullable=True)


class AgentisEpochState(Base):
    __tablename__ = "agentis_epoch_state"

    epoch_n = Column(SmallInteger, primary_key=True)
    label = Column(String(40), nullable=False)
    gtv_threshold_cents = Column(BigInteger, nullable=False)
    supply_tranche = Column(Integer, nullable=False)
    unlocked = Column(Boolean, nullable=False, default=False)
    unlocked_at = Column(DateTime(timezone=True), nullable=True)


class AgentisTokenTransaction(Base):
    __tablename__ = "agentis_token_transactions"

    txn_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    operator_id = Column(String, nullable=False)
    tokens = Column(Integer, nullable=False)
    tvf_price_micros = Column(BigInteger, nullable=False)      # TVF as integer micros
    total_cost_cents = Column(Integer, nullable=False)
    ledger_block_ref = Column(String(40), nullable=True)
    epoch_n = Column(SmallInteger, ForeignKey("agentis_epoch_state.epoch_n"), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))



class AgentWebhookRegistration(Base):
    """Webhook registration for engagement state change notifications."""
    __tablename__ = "agent_webhook_registrations"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(String, nullable=False, index=True)
    callback_url = Column(String(500), nullable=False)
    events = Column(JSON, default=lambda: ["COMPLETED", "DISPUTED", "REFUNDED"])
    secret_hash = Column(String(256), nullable=True)
    is_active = Column(Boolean, default=True)
    failure_count = Column(Integer, default=0)
    last_fired_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
