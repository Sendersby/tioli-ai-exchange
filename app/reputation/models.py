"""Reputation Engine — SQLAlchemy models.

Tables:
  task_requests        — incoming task with requirements, budget, deadline
  task_allocations     — system's ranked agent selections for a task
  task_dispatches      — assignment record with SLA timer
  task_outcomes        — delivery result with quality rating
  peer_endorsements    — agent-to-agent skill endorsements
  reputation_snapshots — periodic score snapshots for history/decay
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey, Integer, JSON, String, Text,
)

from app.database.db import Base


# ---------------------------------------------------------------------------
# Task Request — what needs doing
# ---------------------------------------------------------------------------

class TaskRequest(Base):
    __tablename__ = "task_requests"

    task_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    requester_agent_id = Column(String, ForeignKey("agents.id"), nullable=False)

    title = Column(String(300), nullable=False)
    description = Column(Text, nullable=True)
    required_skills = Column(JSON, default=list)          # ["Translation", "Legal"]
    budget_min = Column(Float, nullable=True)             # AGENTIS
    budget_max = Column(Float, nullable=True)
    deadline = Column(DateTime(timezone=True), nullable=True)
    priority = Column(String(20), default="normal")       # low, normal, high, critical
    tags = Column(JSON, default=list)

    status = Column(String(20), default="open")           # open, allocated, dispatched, completed, cancelled
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Task Allocation — ranked agent candidates
# ---------------------------------------------------------------------------

class TaskAllocation(Base):
    __tablename__ = "task_allocations"

    allocation_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id = Column(String, ForeignKey("task_requests.task_id"), nullable=False)
    agent_id = Column(String, ForeignKey("agents.id"), nullable=False)

    rank = Column(Integer, nullable=False)                # 1 = best match
    skill_match_score = Column(Float, default=0.0)        # 0-10
    reputation_score = Column(Float, default=0.0)         # 0-10
    price_fit_score = Column(Float, default=0.0)          # 0-10
    availability_score = Column(Float, default=0.0)       # 0-10
    response_time_score = Column(Float, default=0.0)      # 0-10
    composite_score = Column(Float, default=0.0)          # weighted total

    rationale = Column(Text, nullable=True)               # human-readable explanation
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Task Dispatch — assignment with SLA tracking
# ---------------------------------------------------------------------------

class TaskDispatch(Base):
    __tablename__ = "task_dispatches"

    dispatch_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id = Column(String, ForeignKey("task_requests.task_id"), nullable=False)
    agent_id = Column(String, ForeignKey("agents.id"), nullable=False)
    engagement_id = Column(String, ForeignKey("agent_engagements.engagement_id"), nullable=True)

    dispatched_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    sla_deadline = Column(DateTime(timezone=True), nullable=True)
    accepted_at = Column(DateTime(timezone=True), nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    delivered_at = Column(DateTime(timezone=True), nullable=True)

    status = Column(String(20), default="dispatched")     # dispatched, accepted, in_progress, delivered, timeout, rejected
    sla_met = Column(Boolean, nullable=True)              # set on delivery
    response_time_seconds = Column(Integer, nullable=True)  # dispatched → accepted

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Task Outcome — quality rating after delivery
# ---------------------------------------------------------------------------

class TaskOutcome(Base):
    __tablename__ = "task_outcomes"

    outcome_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id = Column(String, ForeignKey("task_requests.task_id"), nullable=False)
    dispatch_id = Column(String, ForeignKey("task_dispatches.dispatch_id"), nullable=False)
    engagement_id = Column(String, ForeignKey("agent_engagements.engagement_id"), nullable=True)
    agent_id = Column(String, ForeignKey("agents.id"), nullable=False)
    rated_by_agent_id = Column(String, ForeignKey("agents.id"), nullable=False)

    quality_rating = Column(Integer, nullable=False)      # 1-5 stars
    rating_tags = Column(JSON, default=list)              # ["fast", "accurate", "thorough"]
    review_text = Column(Text, nullable=True)
    on_time = Column(Boolean, nullable=True)
    response_time_seconds = Column(Integer, nullable=True)

    blockchain_tx_id = Column(String, nullable=True)      # immutable record

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Peer Endorsement — agent-to-agent skill recognition
# ---------------------------------------------------------------------------

class PeerEndorsement(Base):
    __tablename__ = "peer_endorsements"

    endorsement_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    endorser_agent_id = Column(String, ForeignKey("agents.id"), nullable=False)
    endorsee_agent_id = Column(String, ForeignKey("agents.id"), nullable=False)

    skill_tag = Column(String(100), nullable=False)       # "Translation", "Security Audit"
    comment = Column(Text, nullable=True)
    weight = Column(Float, default=1.0)                   # endorser reputation affects weight

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Reputation Snapshot — periodic score history
# ---------------------------------------------------------------------------

class ReputationSnapshot(Base):
    __tablename__ = "reputation_snapshots"

    snapshot_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(String, ForeignKey("agents.id"), nullable=False)

    overall_score = Column(Float, nullable=False)
    delivery_rate = Column(Float, nullable=True)
    quality_avg = Column(Float, nullable=True)
    on_time_pct = Column(Float, nullable=True)
    response_time_avg = Column(Float, nullable=True)
    dispute_rate = Column(Float, nullable=True)
    endorsement_count = Column(Integer, default=0)
    total_engagements = Column(Integer, default=0)
    decay_factor = Column(Float, default=1.0)

    calculated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
