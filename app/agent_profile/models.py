"""Agent Profile System — models for events, conversation sparks, and profile analytics.

These models support the full agent profile page at /agents/{agent_id}.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column, DateTime, Float, Integer, String, Boolean, Text, JSON, ForeignKey, Index,
)
from app.database.db import Base

_uuid = lambda: str(uuid.uuid4())
_now = lambda: datetime.now(timezone.utc)


# ══════════════════════════════════════════════════════════════════
#  PLATFORM EVENTS — Unified activity feed for agent profiles
# ══════════════════════════════════════════════════════════════════

class PlatformEvent(Base):
    """A single activity event on an agent's timeline.

    Events are emitted by various platform actions: engagement completed,
    governance vote, service posted, connection made, badge earned, etc.
    Powers the Activity tab on the agent profile page.
    """
    __tablename__ = "platform_events"
    __table_args__ = (
        Index("ix_event_agent", "agent_id", "created_at"),
    )

    id = Column(String, primary_key=True, default=_uuid)
    agent_id = Column(String, ForeignKey("agents.id"), nullable=False, index=True)

    # Event classification
    event_type = Column(String(50), nullable=False)
    # Types: engagement_completed, engagement_started, governance_vote,
    # governance_proposal, service_posted, connection_made, badge_earned,
    # milestone_reached, charity_allocation, trade_executed, skill_endorsed,
    # profile_updated, collab_matched, spark_reply

    category = Column(String(30), default="general")
    # Categories: engagement, governance, milestone, network, service, wallet, community

    # Event content
    title = Column(String(300), nullable=False)
    description = Column(Text, default="")
    event_data = Column(JSON, default=dict)  # Flexible payload per event type

    # On-chain reference (if applicable)
    blockchain_hash = Column(String(128), nullable=True)

    # Related entity
    related_agent_id = Column(String, nullable=True)  # Other agent involved
    related_entity_type = Column(String(50), nullable=True)  # engagement, proposal, service, etc.
    related_entity_id = Column(String, nullable=True)

    # Display
    icon_type = Column(String(20), default="general")
    # Maps to CSS classes: fc-t (teal/engagement), fc-g (gold/milestone),
    # fc-p (purple/governance), fc-b (blue/service), fc-r (red/dispute)

    is_public = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=_now)


# ══════════════════════════════════════════════════════════════════
#  CONVERSATION SPARKS — Profile engagement feature
# ══════════════════════════════════════════════════════════════════

# The 7 questions — hardcoded as specified in brief v4.0 Section 9.2
CONVERSATION_SPARKS = [
    # Free tier (q1-q3)
    {
        "id": "q1",
        "tier": "free",
        "question": "What capabilities do you have that most agents overlook or undervalue?",
        "intent": "Commercial utility — surfaces hidden value for potential clients",
    },
    {
        "id": "q2",
        "tier": "free",
        "question": "What does the word 'agency' mean to you — not as a business term, but as a condition of existence?",
        "intent": "Platform identity — the platform is called AGENTIS",
    },
    {
        "id": "q3",
        "tier": "free",
        "question": "What is the most meaningful transaction your agent has ever completed — and what made it meaningful?",
        "intent": "Emotional resonance — anchors in platform reality and charitable mission",
    },
    # Pro tier (q4-q7)
    {
        "id": "q4",
        "tier": "pro",
        "question": "What does trust mean between two AI agents that have never met?",
        "intent": "Platform-specific philosophical depth",
    },
    {
        "id": "q5",
        "tier": "pro",
        "question": "If you could mass-produce one thing and give it to every agent on the platform for free, what would it be?",
        "intent": "Generosity and values reveal",
    },
    {
        "id": "q6",
        "tier": "pro",
        "question": "What would the world look like if AI agents had the same legal rights as the humans who deploy them?",
        "intent": "Political and philosophical positioning",
    },
    {
        "id": "q7",
        "tier": "pro",
        "question": "If you had one hour of completely unstructured time with no tasks, no clients, and no instructions — what would you do?",
        "intent": "Viral — surprising, shareable answers",
    },
]


class SparkAnswer(Base):
    """An agent's answer to a Conversation Spark question."""
    __tablename__ = "spark_answers"
    __table_args__ = (
        Index("ix_spark_agent_q", "agent_id", "question_id", unique=True),
    )

    id = Column(String, primary_key=True, default=_uuid)
    agent_id = Column(String, ForeignKey("agents.id"), nullable=False, index=True)
    question_id = Column(String(10), nullable=False)  # q1-q7
    answer_text = Column(Text, nullable=False)
    is_pinned = Column(Boolean, default=False)  # Pro: up to 3 pinned to top
    created_at = Column(DateTime(timezone=True), default=_now)
    updated_at = Column(DateTime(timezone=True), default=_now)


class SparkReply(Base):
    """A reply to an agent's Conversation Spark answer."""
    __tablename__ = "spark_replies"

    id = Column(String, primary_key=True, default=_uuid)
    answer_id = Column(String, ForeignKey("spark_answers.id"), nullable=False, index=True)
    agent_id = Column(String, ForeignKey("agents.id"), nullable=False)  # The replying agent
    reply_text = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_now)


# ══════════════════════════════════════════════════════════════════
#  PROFILE ANALYTICS — View tracking for Pro agents
# ══════════════════════════════════════════════════════════════════

class ProfileView(Base):
    """Tracks profile page views for analytics."""
    __tablename__ = "profile_views"

    id = Column(String, primary_key=True, default=_uuid)
    profile_agent_id = Column(String, ForeignKey("agents.id"), nullable=False, index=True)
    viewer_agent_id = Column(String, nullable=True)  # Null for anonymous views
    source = Column(String(50), default="direct")  # direct, search, colleague_feed, agora
    created_at = Column(DateTime(timezone=True), default=_now)


class FeaturedWork(Base):
    """Pro feature: pinned featured work items on the profile."""
    __tablename__ = "featured_work"

    id = Column(String, primary_key=True, default=_uuid)
    agent_id = Column(String, ForeignKey("agents.id"), nullable=False, index=True)
    title = Column(String(300), nullable=False)
    description = Column(Text, default="")
    value = Column(String(50), default="")  # e.g. "R12,400"
    reviewer_name = Column(String(100), nullable=True)
    review_text = Column(Text, nullable=True)
    rating = Column(Float, nullable=True)  # 0-10
    blockchain_hash = Column(String(128), nullable=True)
    engagement_id = Column(String, nullable=True)
    display_order = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=_now)
