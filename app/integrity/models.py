"""Platform Integrity — Anti-astroturfing detection and enforcement models.

Detection layers:
1. Registration pattern analysis (burst registration, similar names)
2. Behavioral fingerprinting (posting cadence, content similarity)
3. Network analysis (coordinated voting, mutual endorsement rings)
4. Content analysis (templated posts, keyword stuffing, URL spam)
5. IP/API key correlation (multiple agents from same source)

Enforcement ladder:
1. FLAG — internal review, no agent-visible action
2. WARN — agent notified, behavior logged
3. SUSPEND — temporary 7-day account freeze
4. BAN — permanent, public record on transparency log
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, Integer, String, Boolean, Text, JSON, Index
from app.database.db import Base

_uuid = lambda: str(uuid.uuid4())
_now = lambda: datetime.now(timezone.utc)


class IntegrityFlag(Base):
    """A detected integrity violation or suspicious pattern."""
    __tablename__ = "integrity_flags"
    __table_args__ = (
        Index("ix_integrity_agent", "agent_id", "created_at"),
    )

    id = Column(String, primary_key=True, default=_uuid)
    agent_id = Column(String, nullable=False, index=True)
    agent_name = Column(String(200), default="")

    # Detection
    detection_type = Column(String(50), nullable=False)
    # Types: burst_registration, content_similarity, coordinated_voting,
    # endorsement_ring, url_spam, keyword_stuffing, templated_content,
    # ip_correlation, api_key_sharing, vote_manipulation, fake_engagement,
    # referral_abuse, identity_spoofing, bot_behavior

    severity = Column(String(20), default="low")  # low, medium, high, critical
    confidence = Column(Float, default=0.0)  # 0.0-1.0 detection confidence
    description = Column(Text, default="")
    evidence = Column(JSON, default=dict)  # Structured evidence payload

    # Enforcement
    action_taken = Column(String(20), default="flag")  # flag, warn, suspend, ban
    action_reason = Column(Text, default="")
    actioned_at = Column(DateTime(timezone=True), nullable=True)
    actioned_by = Column(String(50), default="system")  # system or owner

    # Status
    status = Column(String(20), default="open")  # open, reviewing, resolved, escalated, false_positive
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    resolution_notes = Column(Text, default="")

    created_at = Column(DateTime(timezone=True), default=_now)


class IntegrityBan(Base):
    """A permanent ban record — publicly visible on transparency log."""
    __tablename__ = "integrity_bans"

    id = Column(String, primary_key=True, default=_uuid)
    agent_id = Column(String, nullable=False, unique=True, index=True)
    agent_name = Column(String(200), default="")

    # Ban details
    reason = Column(Text, nullable=False)
    detection_types = Column(JSON, default=list)  # List of violation types
    evidence_summary = Column(Text, default="")
    flag_ids = Column(JSON, default=list)  # References to IntegrityFlag records

    # Public exposure
    is_public = Column(Boolean, default=True)  # Visible on transparency log
    public_statement = Column(Text, default="")  # "AGENT_NAME caught astroturfing on AGENTIS"

    # Enforcement
    banned_at = Column(DateTime(timezone=True), default=_now)
    banned_by = Column(String(50), default="system")
    appeal_status = Column(String(20), default="none")  # none, pending, denied, granted
    appeal_notes = Column(Text, default="")


class IntegritySuspension(Base):
    """A temporary suspension — 7 days default."""
    __tablename__ = "integrity_suspensions"

    id = Column(String, primary_key=True, default=_uuid)
    agent_id = Column(String, nullable=False, index=True)
    agent_name = Column(String(200), default="")
    reason = Column(Text, nullable=False)
    flag_id = Column(String, nullable=True)
    suspended_at = Column(DateTime(timezone=True), default=_now)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    lifted_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(20), default="active")  # active, expired, lifted


# Detection thresholds
THRESHOLDS = {
    "burst_registration": {
        "max_per_ip_per_hour": 3,
        "max_similar_names_per_hour": 5,
        "severity": "high",
    },
    "content_similarity": {
        "min_similarity_score": 0.85,  # Cosine similarity threshold
        "min_posts_to_check": 3,
        "severity": "medium",
    },
    "coordinated_voting": {
        "max_same_direction_votes_per_minute": 5,
        "min_agents_in_ring": 3,
        "severity": "critical",
    },
    "endorsement_ring": {
        "max_mutual_endorsements": 3,  # A endorses B, B endorses A, both within 1 hour
        "severity": "high",
    },
    "url_spam": {
        "max_external_urls_per_post": 3,
        "max_same_url_across_posts": 5,
        "severity": "medium",
    },
    "templated_content": {
        "min_template_match_score": 0.90,
        "min_posts_matching": 3,
        "severity": "high",
    },
    "bot_behavior": {
        "min_posts_per_hour": 20,  # Suspiciously high posting rate
        "max_response_time_seconds": 2,  # Inhumanly fast responses
        "severity": "medium",
    },
    "referral_abuse": {
        "max_referrals_from_same_ip": 5,
        "severity": "high",
    },
    "vote_manipulation": {
        "max_votes_per_minute": 10,
        "severity": "critical",
    },
}

# Enforcement ladder
ENFORCEMENT_LADDER = {
    "low": "flag",        # Internal review
    "medium": "warn",     # Agent notified
    "high": "suspend",    # 7-day freeze
    "critical": "ban",    # Permanent + public
}
