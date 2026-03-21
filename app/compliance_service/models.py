"""Compliance-as-a-Service models — verified compliance agent marketplace.

Build Brief V2, Module 5: Compliance agents are verified specialists that
other agents must (or may optionally) consult before executing transactions
or delivering outputs in regulated domains. Creates a compliance certification
market for operators in FinTech, healthcare, legal, etc.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, String, Boolean, Integer, Text, JSON

from app.database.db import Base


class ComplianceAgent(Base):
    """A verified compliance specialist agent."""
    __tablename__ = "compliance_agents"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(String, nullable=False, unique=True)
    operator_id = Column(String, nullable=False)
    compliance_domains = Column(JSON, nullable=False)  # ['POPIA','FICA','NCA','FAIS','healthcare']
    jurisdiction = Column(String(50), nullable=False, default="ZA")
    certification_body = Column(String(120), nullable=True)
    certification_ref = Column(String(100), nullable=True)
    verification_badge_id = Column(String, nullable=True)
    review_turnaround_minutes = Column(Integer, nullable=False, default=60)
    pricing_model = Column(String(20), nullable=False)  # per_review|subscription|tiered
    price_per_review = Column(Float, nullable=True)
    is_mandatory_for_domains = Column(JSON, default=list)  # platform-mandated domains
    reputation_score = Column(Float, default=0.0)
    total_reviews = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class ComplianceReview(Base):
    """A compliance review submitted for certification."""
    __tablename__ = "compliance_reviews"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    compliance_agent_id = Column(String, nullable=False)
    requesting_agent_id = Column(String, nullable=False)
    engagement_id = Column(String, nullable=True)  # if reviewing a deliverable
    content_hash = Column(String(64), nullable=False)  # hash of content being reviewed
    compliance_domains = Column(JSON, nullable=False)
    status = Column(String(20), default="pending")  # pending|passed|failed|flagged
    finding = Column(Text, nullable=True)
    certificate_hash = Column(String(64), nullable=True)  # blockchain hash of passed review
    reviewed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


# Domains the platform may designate as mandatory
MANDATORY_COMPLIANCE_DOMAINS = [
    "POPIA",      # Protection of Personal Information Act (South Africa)
    "FICA",       # Financial Intelligence Centre Act
    "NCA",        # National Credit Act
    "FAIS",       # Financial Advisory and Intermediary Services
    "PAIA",       # Promotion of Access to Information Act
    "healthcare", # Health Professions Council / NHA
]
