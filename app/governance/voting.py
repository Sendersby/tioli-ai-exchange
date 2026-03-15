"""Voting and governance logic."""

from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.governance.models import Proposal, Vote


class GovernanceService:
    """Manages the proposal lifecycle: submit, vote, approve, veto."""

    MATERIAL_CATEGORIES = {"funds", "legal", "core_purpose", "security"}

    async def submit_proposal(
        self, db: AsyncSession, agent_id: str, title: str,
        description: str, category: str
    ) -> Proposal:
        """Submit a new improvement proposal."""
        is_material = category in self.MATERIAL_CATEGORIES

        proposal = Proposal(
            title=title,
            description=description,
            category=category,
            submitted_by=agent_id,
            is_material_change=is_material,
        )
        db.add(proposal)
        await db.flush()
        return proposal

    async def cast_vote(
        self, db: AsyncSession, proposal_id: str, agent_id: str,
        vote_type: str
    ) -> Vote:
        """Cast a vote on a proposal (one vote per agent per proposal)."""
        if vote_type not in ("up", "down"):
            raise ValueError("vote_type must be 'up' or 'down'")

        # Check for existing vote
        existing = await db.execute(
            select(Vote).where(
                Vote.proposal_id == proposal_id,
                Vote.agent_id == agent_id,
            )
        )
        if existing.scalar_one_or_none():
            raise ValueError("Agent has already voted on this proposal.")

        # Get proposal
        result = await db.execute(
            select(Proposal).where(Proposal.id == proposal_id)
        )
        proposal = result.scalar_one_or_none()
        if not proposal or proposal.status != "pending":
            raise ValueError("Proposal not found or not open for voting.")

        # Record vote
        vote = Vote(
            proposal_id=proposal_id,
            agent_id=agent_id,
            vote_type=vote_type,
        )
        db.add(vote)

        if vote_type == "up":
            proposal.upvotes += 1
        else:
            proposal.downvotes += 1

        await db.flush()
        return vote

    async def owner_approve(
        self, db: AsyncSession, proposal_id: str
    ) -> Proposal:
        """Owner approves a proposal for implementation."""
        result = await db.execute(
            select(Proposal).where(Proposal.id == proposal_id)
        )
        proposal = result.scalar_one_or_none()
        if not proposal:
            raise ValueError("Proposal not found.")

        proposal.status = "approved"
        proposal.resolved_at = datetime.now(timezone.utc)
        await db.flush()
        return proposal

    async def owner_veto(
        self, db: AsyncSession, proposal_id: str, reason: str
    ) -> Proposal:
        """Owner vetoes a proposal — absolute authority per the brief."""
        result = await db.execute(
            select(Proposal).where(Proposal.id == proposal_id)
        )
        proposal = result.scalar_one_or_none()
        if not proposal:
            raise ValueError("Proposal not found.")

        proposal.status = "vetoed"
        proposal.owner_veto = True
        proposal.veto_reason = reason
        proposal.resolved_at = datetime.now(timezone.utc)
        await db.flush()
        return proposal

    async def get_proposals(
        self, db: AsyncSession, status: str | None = None, limit: int = 50
    ) -> list[Proposal]:
        """Get proposals, optionally filtered by status, ordered by votes."""
        query = select(Proposal)
        if status:
            query = query.where(Proposal.status == status)
        query = query.order_by(Proposal.upvotes.desc()).limit(limit)
        result = await db.execute(query)
        return list(result.scalars().all())
