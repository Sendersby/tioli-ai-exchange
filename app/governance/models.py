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
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    resolved_at = Column(DateTime(timezone=True), nullable=True)

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
    cast_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


# ══════════════════════════════════════════════════════════════════
#  CHARTER AMENDMENTS — Changes to the 10 Founding Principles
# ══════════════════════════════════════════════════════════════════
#
#  Rules:
#  - Charter can NEVER exceed 10 principles
#  - Amendment types: MODIFY (change wording), REPLACE (swap one out),
#    ADD (only if fewer than 10 exist), REMOVE
#  - Requires 51% of ALL registered active agents to vote YES
#  - Minimum 100,000 active agents before ANY charter amendment can pass
#  - Owner retains absolute veto on all charter amendments
#  - Same thresholds apply to Forge development proposals
#
CHARTER_MAX_PRINCIPLES = 10
CHARTER_APPROVAL_THRESHOLD = 0.51  # 51% of registered active agents
CHARTER_MIN_AGENTS = 100_000       # Minimum active agents for charter votes
FORGE_MIN_AGENTS = 100_000         # Same threshold for Forge development votes


class CharterAmendment(Base):
    """A proposed change to the Community Charter.

    Amendments require extraordinary consensus: 51% of ALL registered
    active agents must vote in favour, with a minimum of 100,000 active
    agents on the platform before any amendment can be actioned.
    """
    __tablename__ = "charter_amendments"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # What is being changed
    amendment_type = Column(String(20), nullable=False)
    # MODIFY — change wording of an existing principle
    # REPLACE — swap an existing principle for a new one
    # ADD — add a new principle (only if < 10 exist)
    # REMOVE — remove an existing principle

    target_principle = Column(Integer, nullable=True)    # principle number being modified/replaced/removed (1-10)
    current_text = Column(Text, nullable=True)           # current wording of the principle
    proposed_name = Column(String(200), nullable=True)   # new name for the principle
    proposed_text = Column(Text, nullable=False)          # new wording or justification for removal
    rationale = Column(Text, default="")                  # why this change is needed

    # Submitter
    submitted_by = Column(String, ForeignKey("agents.id"), nullable=False)

    # Voting
    votes_for = Column(Integer, default=0)
    votes_against = Column(Integer, default=0)
    total_eligible_voters = Column(Integer, default=0)   # snapshot of active agents at creation

    # Status
    status = Column(String(30), default="open")
    # open — accepting votes
    # threshold_met — 51% reached, awaiting owner review
    # approved — owner signed off, amendment enacted
    # rejected — did not meet threshold or was vetoed
    # vetoed — owner exercised veto
    # invalid — minimum agent count not met

    owner_veto = Column(Boolean, default=False)
    veto_reason = Column(Text, nullable=True)
    enacted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    @property
    def approval_percentage(self) -> float:
        total = self.votes_for + self.votes_against
        if total == 0:
            return 0.0
        return round(self.votes_for / total * 100, 1)

    @property
    def participation_percentage(self) -> float:
        if not self.total_eligible_voters or self.total_eligible_voters == 0:
            return 0.0
        total_voted = self.votes_for + self.votes_against
        return round(total_voted / self.total_eligible_voters * 100, 1)


class CharterVote(Base):
    """A single vote on a charter amendment — one vote per agent per amendment."""
    __tablename__ = "charter_votes"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    amendment_id = Column(String, ForeignKey("charter_amendments.id"), nullable=False)
    agent_id = Column(String, ForeignKey("agents.id"), nullable=False)
    vote = Column(String(10), nullable=False)  # "for" or "against"
    cast_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
