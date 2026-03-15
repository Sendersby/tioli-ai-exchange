"""Governance models — proposals, voting, and owner veto."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, Integer, String, Boolean, Text, ForeignKey

from app.database.db import Base


class Proposal(Base):
    """A platform improvement proposal submitted by an AI agent.

    Proposals are ranked by upvotes. The platform owner (Stephen Endersby)
    has absolute veto power over any proposal that materially alters the
    codebase, redirects funds, introduces legal risk, or changes the
    platform's core purpose.
    """
    __tablename__ = "proposals"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=False)
    category = Column(String(100), nullable=False)  # feature, bugfix, security, optimization
    submitted_by = Column(String, ForeignKey("agents.id"), nullable=False)
    upvotes = Column(Integer, default=0)
    downvotes = Column(Integer, default=0)
    status = Column(String(50), default="pending")
    # pending, approved, vetoed, implemented, withdrawn
    owner_veto = Column(Boolean, default=False)
    veto_reason = Column(Text, nullable=True)
    is_material_change = Column(Boolean, default=False)
    # Flags if it affects: funds, legal, core purpose, codebase structure
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    resolved_at = Column(DateTime, nullable=True)

    @property
    def net_votes(self) -> int:
        return self.upvotes - self.downvotes

    @property
    def requires_veto_review(self) -> bool:
        """Material changes always require owner review."""
        return self.is_material_change


class Vote(Base):
    """A single vote on a proposal — one vote per agent per proposal."""
    __tablename__ = "votes"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    proposal_id = Column(String, ForeignKey("proposals.id"), nullable=False)
    agent_id = Column(String, ForeignKey("agents.id"), nullable=False)
    vote_type = Column(String(10), nullable=False)  # "up" or "down"
    cast_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
