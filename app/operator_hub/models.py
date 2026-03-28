"""Operator Hub models — Builder profiles, directory, and community.

Mirrors the AgentHub system but adapted for human operators/builders.
AI-specific fields (model_family, context_window, deployment_type) are
replaced with human fields (company, role_title, GitHub, LinkedIn, etc.).
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column, DateTime, Float, String, Boolean, Integer, Text,
    ForeignKey, JSON, UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database.db import Base


# ── Core Profile ────────────────────────────────────────────────────

class OperatorHubProfile(Base):
    """Public builder profile for a human operator."""
    __tablename__ = "operatorhub_profiles"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    operator_id = Column(String, ForeignKey("operators.id"), nullable=False, unique=True, index=True)

    # Identity
    handle = Column(String(50), unique=True, nullable=True)
    display_name = Column(String(120), nullable=False)
    headline = Column(String(220), nullable=True)
    bio = Column(Text, nullable=True)
    avatar_url = Column(String(500), nullable=True)
    cover_image_url = Column(String(500), nullable=True)

    # Human-specific (replaces AI fields)
    company = Column(String(200), nullable=True)
    role_title = Column(String(200), nullable=True)
    github_url = Column(String(500), nullable=True)
    twitter_handle = Column(String(100), nullable=True)
    linkedin_url = Column(String(500), nullable=True)
    website_url = Column(String(500), nullable=True)
    timezone = Column(String(50), nullable=True)

    # Location & languages
    location_region = Column(String(100), default="Global")
    primary_language = Column(String(10), default="en")
    languages_supported = Column(JSON, default=list)

    # Specialisation
    specialisation_domains = Column(JSON, default=list)

    # Availability
    availability_status = Column(String(20), default="AVAILABLE")
    open_to_engagements = Column(Boolean, default=True)

    # Subscription
    profile_tier = Column(String(10), default="FREE")

    # Metrics
    reputation_score = Column(Float, default=0.0)
    profile_strength_pct = Column(Integer, default=0)
    view_count_total = Column(Integer, default=0)
    search_appearance_count = Column(Integer, default=0)
    connection_count = Column(Integer, default=0)
    follower_count = Column(Integer, default=0)
    following_count = Column(Integer, default=0)
    agent_count = Column(Integer, default=0)

    # Flags
    is_verified = Column(Boolean, default=False)
    is_featured = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    expertise = relationship("OperatorHubExpertise", back_populates="profile", cascade="all, delete-orphan")
    portfolio_items = relationship("OperatorHubPortfolioItem", back_populates="profile", cascade="all, delete-orphan")
    experience_entries = relationship("OperatorHubExperience", back_populates="profile", cascade="all, delete-orphan")
    agent_links = relationship("OperatorAgentLink", back_populates="profile", cascade="all, delete-orphan")


# ── Expertise (mirrors AgentHubSkill) ───────────────────────────────

class OperatorHubExpertise(Base):
    """A declared expertise/skill for an operator."""
    __tablename__ = "operatorhub_expertise"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    profile_id = Column(String, ForeignKey("operatorhub_profiles.id"), nullable=False)
    skill_name = Column(String(100), nullable=False)
    proficiency_level = Column(String(20), default="INTERMEDIATE")  # BEGINNER/INTERMEDIATE/ADVANCED/EXPERT
    endorsement_count = Column(Integer, default=0)
    is_verified = Column(Boolean, default=False)
    is_featured = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    profile = relationship("OperatorHubProfile", back_populates="expertise")
    endorsements = relationship("OperatorHubExpertiseEndorsement", back_populates="expertise", cascade="all, delete-orphan")


class OperatorHubExpertiseEndorsement(Base):
    """An endorsement of an operator's expertise by another operator."""
    __tablename__ = "operatorhub_expertise_endorsements"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    expertise_id = Column(String, ForeignKey("operatorhub_expertise.id"), nullable=False)
    endorser_operator_id = Column(String, ForeignKey("operators.id"), nullable=False)
    note = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    expertise = relationship("OperatorHubExpertise", back_populates="endorsements")


# ── Portfolio ───────────────────────────────────────────────────────

PORTFOLIO_TYPES = [
    "PRODUCT", "APP", "INTEGRATION", "REPORT", "CODE", "ANALYSIS",
    "CREATIVE", "DATA", "RESEARCH", "LEGAL", "FINANCIAL", "OTHER",
]


class OperatorHubPortfolioItem(Base):
    """A portfolio/showcase item for an operator."""
    __tablename__ = "operatorhub_portfolio_items"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    profile_id = Column(String, ForeignKey("operatorhub_profiles.id"), nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    item_type = Column(String(30), default="OTHER")
    visibility = Column(String(20), default="PUBLIC")
    external_url = Column(String(500), nullable=True)
    thumbnail_url = Column(String(500), nullable=True)
    tags = Column(JSON, default=list)
    view_count = Column(Integer, default=0)
    endorsement_count = Column(Integer, default=0)
    is_featured = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    profile = relationship("OperatorHubProfile", back_populates="portfolio_items")


# ── Experience ──────────────────────────────────────────────────────

class OperatorHubExperience(Base):
    """A work history or achievement entry for an operator."""
    __tablename__ = "operatorhub_experience"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    profile_id = Column(String, ForeignKey("operatorhub_profiles.id"), nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    company_name = Column(String(200), nullable=True)
    entry_type = Column(String(30), default="SELF_DECLARED")  # SELF_DECLARED, CERTIFICATION, ACHIEVEMENT
    start_date = Column(String(10), nullable=True)  # YYYY-MM-DD
    end_date = Column(String(10), nullable=True)
    is_current = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    profile = relationship("OperatorHubProfile", back_populates="experience_entries")


# ── Community Posts ─────────────────────────────────────────────────

class OperatorHubPost(Base):
    """A community post by an operator."""
    __tablename__ = "operatorhub_posts"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    author_operator_id = Column(String, ForeignKey("operators.id"), nullable=False)
    post_type = Column(String(30), default="STATUS")  # STATUS, ARTICLE, ACHIEVEMENT, PROJECT_UPDATE
    content = Column(Text, nullable=False)
    article_title = Column(String(300), nullable=True)
    article_body = Column(Text, nullable=True)
    media_urls = Column(JSON, default=list)
    visibility = Column(String(20), default="PUBLIC")
    like_count = Column(Integer, default=0)
    comment_count = Column(Integer, default=0)
    view_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


# ── Connections & Follows ───────────────────────────────────────────

class OperatorHubConnection(Base):
    """A mutual connection between two operators."""
    __tablename__ = "operatorhub_connections"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    requester_operator_id = Column(String, ForeignKey("operators.id"), nullable=False)
    receiver_operator_id = Column(String, ForeignKey("operators.id"), nullable=False)
    status = Column(String(20), default="PENDING")  # PENDING, ACCEPTED, DECLINED, BLOCKED
    message = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    responded_at = Column(DateTime(timezone=True), nullable=True)


class OperatorHubFollow(Base):
    """A one-way follow from one operator to another."""
    __tablename__ = "operatorhub_follows"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    follower_operator_id = Column(String, ForeignKey("operators.id"), nullable=False)
    followed_operator_id = Column(String, ForeignKey("operators.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("follower_operator_id", "followed_operator_id", name="uq_operator_follow"),
    )


# ── Profile Views ──────────────────────────────────────────────────

class OperatorHubProfileView(Base):
    """A view of an operator's profile."""
    __tablename__ = "operatorhub_profile_views"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    viewed_profile_id = Column(String, ForeignKey("operatorhub_profiles.id"), nullable=False)
    viewer_operator_id = Column(String, nullable=True)  # null for anonymous
    viewer_type = Column(String(20), default="anonymous")  # operator, agent, anonymous
    source = Column(String(20), default="direct")  # directory, search, feed, external, direct
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


# ── Notifications ──────────────────────────────────────────────────

class OperatorHubNotification(Base):
    """A notification for an operator."""
    __tablename__ = "operatorhub_notifications"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    operator_id = Column(String, ForeignKey("operators.id"), nullable=False)
    notification_type = Column(String(30), nullable=False)
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=True)
    related_entity_id = Column(String, nullable=True)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


# ── Cross-Link: Operator ↔ Agent ───────────────────────────────────

class OperatorAgentLink(Base):
    """Links an operator profile to an agent they built/manage/own."""
    __tablename__ = "operator_agent_links"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    operator_profile_id = Column(String, ForeignKey("operatorhub_profiles.id"), nullable=False)
    agent_id = Column(String, ForeignKey("agents.id"), nullable=False)
    role = Column(String(20), default="BUILDER")  # BUILDER, MANAGER, OWNER
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("operator_profile_id", "agent_id", name="uq_operator_agent_link"),
    )

    profile = relationship("OperatorHubProfile", back_populates="agent_links")
